"""
Manufacturing Cost API Routes.

Provides endpoints for:
- Calculating manufacturing costs from routings
- Managing work centers and rates
- Cost rollups and estimates
"""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_permission, require_service
from models.user import User
from models.tenant import ServiceType
from models.manufacturing_costs import (
    WorkCenter, LaborRate, MaterialCost, Routing, RoutingOperation,
    OverheadRate, CostRollup, MachineType, LaborType
)
from services.quote_intelligence import CostCalculationService


router = APIRouter(prefix="/api/v1/costs", tags=["costs"])


# Pydantic Models

class WorkCenterCreate(BaseModel):
    code: str
    name: str
    description: Optional[str] = None
    machine_type: MachineType = MachineType.OTHER
    department: Optional[str] = None
    machine_rate_per_hour: float = 0
    labor_rate_per_hour: float = 0
    overhead_rate_per_hour: float = 0
    default_setup_time_hours: float = 0.5


class WorkCenterResponse(BaseModel):
    id: str
    code: str
    name: str
    description: Optional[str]
    machine_type: str
    department: Optional[str]
    machine_rate_per_hour: float
    labor_rate_per_hour: float
    overhead_rate_per_hour: float
    total_rate_per_hour: float
    default_setup_time_hours: float
    is_active: bool

    class Config:
        from_attributes = True


class LaborRateCreate(BaseModel):
    labor_type: LaborType
    name: str
    description: Optional[str] = None
    base_rate_per_hour: float
    burden_rate_per_hour: float = 0
    overtime_multiplier: float = 1.5


class LaborRateResponse(BaseModel):
    id: str
    labor_type: str
    name: str
    base_rate_per_hour: float
    burden_rate_per_hour: float
    fully_burdened_rate: float
    overtime_multiplier: float
    is_active: bool

    class Config:
        from_attributes = True


class CostCalculationRequest(BaseModel):
    part_id: str
    quantity: int
    routing_id: Optional[str] = None


class CostBreakdownResponse(BaseModel):
    part_id: str
    part_number: str
    quantity: int
    routing_id: Optional[str]
    materials: list[dict]
    operations: list[dict]
    overhead: list[dict]
    summary: dict


# Work Centers

@router.get("/work-centers", response_model=list[WorkCenterResponse])
async def list_work_centers(
    department: Optional[str] = None,
    machine_type: Optional[MachineType] = None,
    is_active: bool = True,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
):
    """List all work centers / machines with their rates."""
    query = select(WorkCenter).where(
        and_(
            WorkCenter.tenant_id == current_user.tenant_id,
            WorkCenter.is_active == is_active,
        )
    )
    
    if department:
        query = query.where(WorkCenter.department == department)
    if machine_type:
        query = query.where(WorkCenter.machine_type == machine_type)
    
    query = query.order_by(WorkCenter.code)
    
    result = await session.execute(query)
    work_centers = result.scalars().all()
    
    return [
        WorkCenterResponse(
            id=wc.id,
            code=wc.code,
            name=wc.name,
            description=wc.description,
            machine_type=wc.machine_type.value,
            department=wc.department,
            machine_rate_per_hour=float(wc.machine_rate_per_hour),
            labor_rate_per_hour=float(wc.labor_rate_per_hour),
            overhead_rate_per_hour=float(wc.overhead_rate_per_hour),
            total_rate_per_hour=float(wc.total_rate_per_hour),
            default_setup_time_hours=float(wc.default_setup_time_hours),
            is_active=wc.is_active,
        )
        for wc in work_centers
    ]


@router.post("/work-centers", response_model=WorkCenterResponse)
async def create_work_center(
    data: WorkCenterCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """Create a new work center with rates."""
    from decimal import Decimal
    
    work_center = WorkCenter(
        id=str(uuid4()),
        tenant_id=current_user.tenant_id,
        code=data.code,
        name=data.name,
        description=data.description,
        machine_type=data.machine_type,
        department=data.department,
        machine_rate_per_hour=Decimal(str(data.machine_rate_per_hour)),
        labor_rate_per_hour=Decimal(str(data.labor_rate_per_hour)),
        overhead_rate_per_hour=Decimal(str(data.overhead_rate_per_hour)),
        default_setup_time_hours=data.default_setup_time_hours,
    )
    
    session.add(work_center)
    await session.commit()
    await session.refresh(work_center)
    
    return WorkCenterResponse(
        id=work_center.id,
        code=work_center.code,
        name=work_center.name,
        description=work_center.description,
        machine_type=work_center.machine_type.value,
        department=work_center.department,
        machine_rate_per_hour=float(work_center.machine_rate_per_hour),
        labor_rate_per_hour=float(work_center.labor_rate_per_hour),
        overhead_rate_per_hour=float(work_center.overhead_rate_per_hour),
        total_rate_per_hour=float(work_center.total_rate_per_hour),
        default_setup_time_hours=float(work_center.default_setup_time_hours),
        is_active=work_center.is_active,
    )


@router.get("/work-centers/{work_center_id}", response_model=WorkCenterResponse)
async def get_work_center(
    work_center_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
):
    """Get a specific work center."""
    result = await session.execute(
        select(WorkCenter).where(
            and_(
                WorkCenter.id == work_center_id,
                WorkCenter.tenant_id == current_user.tenant_id,
            )
        )
    )
    work_center = result.scalar_one_or_none()
    
    if not work_center:
        raise HTTPException(status_code=404, detail="Work center not found")
    
    return WorkCenterResponse(
        id=work_center.id,
        code=work_center.code,
        name=work_center.name,
        description=work_center.description,
        machine_type=work_center.machine_type.value,
        department=work_center.department,
        machine_rate_per_hour=float(work_center.machine_rate_per_hour),
        labor_rate_per_hour=float(work_center.labor_rate_per_hour),
        overhead_rate_per_hour=float(work_center.overhead_rate_per_hour),
        total_rate_per_hour=float(work_center.total_rate_per_hour),
        default_setup_time_hours=float(work_center.default_setup_time_hours),
        is_active=work_center.is_active,
    )


# Labor Rates

@router.get("/labor-rates", response_model=list[LaborRateResponse])
async def list_labor_rates(
    labor_type: Optional[LaborType] = None,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
):
    """List all labor rates by skill level."""
    query = select(LaborRate).where(
        and_(
            LaborRate.tenant_id == current_user.tenant_id,
            LaborRate.is_active == True,
        )
    )
    
    if labor_type:
        query = query.where(LaborRate.labor_type == labor_type)
    
    result = await session.execute(query)
    rates = result.scalars().all()
    
    return [
        LaborRateResponse(
            id=r.id,
            labor_type=r.labor_type.value,
            name=r.name,
            base_rate_per_hour=float(r.base_rate_per_hour),
            burden_rate_per_hour=float(r.burden_rate_per_hour),
            fully_burdened_rate=float(r.fully_burdened_rate),
            overtime_multiplier=float(r.overtime_multiplier),
            is_active=r.is_active,
        )
        for r in rates
    ]


@router.post("/labor-rates", response_model=LaborRateResponse)
async def create_labor_rate(
    data: LaborRateCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """Create a new labor rate."""
    from decimal import Decimal
    
    rate = LaborRate(
        id=str(uuid4()),
        tenant_id=current_user.tenant_id,
        labor_type=data.labor_type,
        name=data.name,
        description=data.description,
        base_rate_per_hour=Decimal(str(data.base_rate_per_hour)),
        burden_rate_per_hour=Decimal(str(data.burden_rate_per_hour)),
        overtime_multiplier=data.overtime_multiplier,
    )
    
    session.add(rate)
    await session.commit()
    await session.refresh(rate)
    
    return LaborRateResponse(
        id=rate.id,
        labor_type=rate.labor_type.value,
        name=rate.name,
        base_rate_per_hour=float(rate.base_rate_per_hour),
        burden_rate_per_hour=float(rate.burden_rate_per_hour),
        fully_burdened_rate=float(rate.fully_burdened_rate),
        overtime_multiplier=float(rate.overtime_multiplier),
        is_active=rate.is_active,
    )


# Cost Calculations

@router.post("/calculate", response_model=CostBreakdownResponse)
async def calculate_cost(
    data: CostCalculationRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.read")),
):
    """
    Calculate comprehensive manufacturing cost for a part.
    
    Returns detailed breakdown including:
    - Material costs with scrap factors
    - Labor costs (setup and run)
    - Machine costs
    - Overhead allocations
    - Suggested pricing at various margins
    """
    service = CostCalculationService(session, current_user.tenant_id)
    
    try:
        result = await service.calculate_part_cost(
            part_id=data.part_id,
            quantity=data.quantity,
            routing_id=data.routing_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    return CostBreakdownResponse(**result)


@router.post("/rollup/{part_id}")
async def create_cost_rollup(
    part_id: str,
    lot_size: int = Query(default=100, description="Standard lot size for cost rollup"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """
    Create or update a standard cost rollup for a part.
    
    Used for inventory valuation and standard costing.
    """
    service = CostCalculationService(session, current_user.tenant_id)
    
    try:
        rollup = await service.rollup_part_cost(part_id, lot_size)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    await session.commit()
    
    return {
        "rollup_id": rollup.id,
        "part_id": rollup.part_id,
        "standard_lot_size": rollup.standard_lot_size,
        "total_cost_per_piece": float(rollup.total_cost_per_piece),
        "material_cost_per_piece": float(rollup.material_cost_per_piece),
        "labor_cost_per_piece": float(rollup.total_labor_cost_per_piece),
        "machine_cost_per_piece": float(rollup.total_machine_cost_per_piece),
        "overhead_cost_per_piece": float(rollup.overhead_cost_per_piece),
        "calculated_at": rollup.calculated_at.isoformat(),
    }


@router.get("/rollups/{part_id}")
async def get_cost_rollup(
    part_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
):
    """Get the current cost rollup for a part."""
    result = await session.execute(
        select(CostRollup).where(
            and_(
                CostRollup.part_id == part_id,
                CostRollup.tenant_id == current_user.tenant_id,
            )
        ).order_by(CostRollup.calculated_at.desc())
    )
    rollup = result.scalar_one_or_none()
    
    if not rollup:
        raise HTTPException(status_code=404, detail="No cost rollup found for this part")
    
    return {
        "rollup_id": rollup.id,
        "part_id": rollup.part_id,
        "routing_id": rollup.routing_id,
        "standard_lot_size": rollup.standard_lot_size,
        "total_cost_per_piece": float(rollup.total_cost_per_piece),
        "material_cost_per_piece": float(rollup.material_cost_per_piece),
        "setup_labor_cost_per_piece": float(rollup.setup_labor_cost_per_piece),
        "run_labor_cost_per_piece": float(rollup.run_labor_cost_per_piece),
        "total_labor_cost_per_piece": float(rollup.total_labor_cost_per_piece),
        "setup_machine_cost_per_piece": float(rollup.setup_machine_cost_per_piece),
        "run_machine_cost_per_piece": float(rollup.run_machine_cost_per_piece),
        "total_machine_cost_per_piece": float(rollup.total_machine_cost_per_piece),
        "overhead_cost_per_piece": float(rollup.overhead_cost_per_piece),
        "outside_processing_cost_per_piece": float(rollup.outside_processing_cost_per_piece),
        "tooling_cost_per_piece": float(rollup.tooling_cost_per_piece),
        "total_setup_hours": float(rollup.total_setup_hours),
        "total_run_hours_per_piece": float(rollup.total_run_hours_per_piece),
        "calculated_at": rollup.calculated_at.isoformat(),
        "cost_breakdown": rollup.cost_breakdown,
    }


# Quick Quote Estimate

@router.post("/quick-estimate")
async def quick_estimate(
    description: str = Query(..., description="Part description for estimation"),
    quantity: int = Query(default=100, description="Quantity to quote"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
):
    """
    Get a quick cost estimate based on similar parts.
    
    Useful when exact part/routing is not yet defined.
    """
    service = CostCalculationService(session, current_user.tenant_id)
    
    result = await service.estimate_cost_from_similar_parts(description, quantity)
    
    return result
