"""
Predictions Router

Provides access to ML predictions and trending data.
"""
from typing import List, Optional
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
import uuid

from api.database import get_db
from api.routers.auth import get_current_active_user
from models.user import User
from models.prediction import Prediction, PredictionType
from models.asset import Asset

router = APIRouter()


# Pydantic Models
class PredictionResponse(BaseModel):
    id: uuid.UUID
    asset_id: uuid.UUID
    prediction_type: PredictionType
    model_name: str
    model_version: str
    generated_at: datetime
    prediction_value: float
    prediction_unit: Optional[str]
    confidence_score: float
    confidence_lower: Optional[float]
    confidence_upper: Optional[float]
    rul_days: Optional[int]
    predicted_failure_date: Optional[datetime]
    anomaly_score: Optional[float]
    is_anomaly: Optional[bool]
    health_score: Optional[float]
    health_trend: Optional[str]
    top_features: Optional[dict]
    alert_generated: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PredictionListResponse(BaseModel):
    items: List[PredictionResponse]
    total: int


class RULSummary(BaseModel):
    asset_id: uuid.UUID
    asset_name: str
    asset_type: str
    current_rul_days: Optional[int]
    confidence_score: float
    predicted_failure_date: Optional[datetime]
    trend: str
    requires_attention: bool


class HealthTrend(BaseModel):
    timestamp: datetime
    health_score: float
    anomaly_score: Optional[float]


class AssetTrendResponse(BaseModel):
    asset_id: uuid.UUID
    asset_name: str
    trends: List[HealthTrend]
    avg_health_score: float
    trend_direction: str  # improving, stable, degrading


# Routes
@router.get("/asset/{asset_id}", response_model=PredictionListResponse)
async def get_asset_predictions(
    asset_id: uuid.UUID,
    prediction_type: Optional[PredictionType] = None,
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get predictions for a specific asset."""
    # Verify asset access
    asset_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Asset not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = (
        select(Prediction)
        .where(Prediction.asset_id == asset_id)
        .where(Prediction.generated_at >= cutoff)
    )

    if prediction_type:
        query = query.where(Prediction.prediction_type == prediction_type)

    query = query.order_by(Prediction.generated_at.desc()).limit(limit)

    result = await db.execute(query)
    predictions = result.scalars().all()

    return PredictionListResponse(
        items=predictions,
        total=len(predictions)
    )


@router.get("/latest/{asset_id}", response_model=PredictionResponse)
async def get_latest_prediction(
    asset_id: uuid.UUID,
    prediction_type: PredictionType = PredictionType.HEALTH_SCORE,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get the latest prediction for an asset."""
    # Verify asset access
    asset_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    if not asset_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Asset not found")

    result = await db.execute(
        select(Prediction)
        .where(Prediction.asset_id == asset_id)
        .where(Prediction.prediction_type == prediction_type)
        .order_by(Prediction.generated_at.desc())
        .limit(1)
    )
    prediction = result.scalar_one_or_none()

    if not prediction:
        raise HTTPException(status_code=404, detail="No predictions found")

    return prediction


@router.get("/rul-summary", response_model=List[RULSummary])
async def get_rul_summary(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get RUL summary for all assets requiring attention."""
    # Get assets with their latest RUL predictions
    assets_result = await db.execute(
        select(Asset)
        .where(Asset.organization_id == current_user.organization_id)
        .where(Asset.predicted_rul_days.isnot(None))
        .order_by(Asset.predicted_rul_days.asc())
    )
    assets = assets_result.scalars().all()

    summaries = []
    for asset in assets:
        # Determine trend based on recent predictions
        trend = "stable"
        if asset.predicted_rul_days:
            if asset.predicted_rul_days < 7:
                trend = "critical"
            elif asset.predicted_rul_days < 30:
                trend = "degrading"

        summaries.append(RULSummary(
            asset_id=asset.id,
            asset_name=asset.name,
            asset_type=asset.asset_type.value,
            current_rul_days=asset.predicted_rul_days,
            confidence_score=float(asset.confidence_score or 0),
            predicted_failure_date=(
                datetime.now(timezone.utc) + timedelta(days=asset.predicted_rul_days)
                if asset.predicted_rul_days else None
            ),
            trend=trend,
            requires_attention=(asset.predicted_rul_days or 999) < 30
        ))

    return summaries


@router.get("/trends/{asset_id}", response_model=AssetTrendResponse)
async def get_asset_trends(
    asset_id: uuid.UUID,
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get health score trends for an asset."""
    # Verify asset access
    asset_result = await db.execute(
        select(Asset).where(
            and_(
                Asset.id == asset_id,
                Asset.organization_id == current_user.organization_id
            )
        )
    )
    asset = asset_result.scalar_one_or_none()
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get health score predictions
    predictions_result = await db.execute(
        select(Prediction)
        .where(Prediction.asset_id == asset_id)
        .where(Prediction.prediction_type == PredictionType.HEALTH_SCORE)
        .where(Prediction.generated_at >= cutoff)
        .order_by(Prediction.generated_at.asc())
    )
    predictions = predictions_result.scalars().all()

    trends = [
        HealthTrend(
            timestamp=p.generated_at,
            health_score=float(p.health_score or p.prediction_value),
            anomaly_score=float(p.anomaly_score) if p.anomaly_score else None
        )
        for p in predictions
    ]

    # Calculate average and trend direction
    if trends:
        scores = [t.health_score for t in trends]
        avg_score = sum(scores) / len(scores)

        # Compare first half to second half for trend
        mid = len(scores) // 2
        if mid > 0:
            first_half_avg = sum(scores[:mid]) / mid
            second_half_avg = sum(scores[mid:]) / (len(scores) - mid)

            if second_half_avg > first_half_avg + 5:
                trend_direction = "improving"
            elif second_half_avg < first_half_avg - 5:
                trend_direction = "degrading"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "stable"
    else:
        avg_score = float(asset.health_score or 100)
        trend_direction = "stable"

    return AssetTrendResponse(
        asset_id=asset.id,
        asset_name=asset.name,
        trends=trends,
        avg_health_score=avg_score,
        trend_direction=trend_direction
    )


@router.get("/anomalies", response_model=PredictionListResponse)
async def get_recent_anomalies(
    hours: int = Query(24, ge=1, le=168),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get recent anomaly detections across all assets."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

    result = await db.execute(
        select(Prediction)
        .join(Asset)
        .where(Asset.organization_id == current_user.organization_id)
        .where(Prediction.prediction_type == PredictionType.ANOMALY_DETECTION)
        .where(Prediction.is_anomaly == True)
        .where(Prediction.generated_at >= cutoff)
        .order_by(Prediction.generated_at.desc())
    )
    predictions = result.scalars().all()

    return PredictionListResponse(
        items=predictions,
        total=len(predictions)
    )
