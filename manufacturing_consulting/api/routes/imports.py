"""
Data Import API Routes.

Provides endpoints for importing manufacturing data from
any ERP system or spreadsheet source.
"""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_permission, require_service
from models.user import User
from models.tenant import ServiceType
from services.integrations import (
    ERPConnector, ERPConnectionConfig, DataImportService, ManufacturingCostImporter
)
from services.integrations.erp_connector import ConnectionType, DataFormat


router = APIRouter(prefix="/api/v1/imports", tags=["imports"])


class ImportConfigRequest(BaseModel):
    """Configuration for import operations."""
    erp_system: str = "generic"
    file_format: str = "csv"
    file_delimiter: str = ","
    file_encoding: str = "utf-8"
    field_mappings: dict[str, str] = {}
    update_existing: bool = True


class ImportResponse(BaseModel):
    """Response from import operation."""
    success: bool
    records_processed: int
    records_imported: int
    records_updated: int
    records_skipped: int
    errors: list[dict]
    warnings: list[str]
    import_time_seconds: float


class ValidationResponse(BaseModel):
    """Response from file validation."""
    valid: bool
    record_count: int
    columns_detected: list[str]
    suggested_mappings: dict[str, str]
    missing_required_fields: list[str]
    sample_records: list[dict]
    warnings: list[str]


# Parts Import

@router.post("/parts", response_model=ImportResponse)
async def import_parts(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """
    Import parts from file (CSV, Excel, JSON, XML).
    
    Supports data from any ERP system with automatic field mapping.
    """
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = DataImportService(session, current_user.tenant_id)
    
    result = await service.import_parts(
        file=file.file,
        filename=file.filename or "import.csv",
        config=erp_config,
        update_existing=import_config.update_existing,
    )
    
    await session.commit()
    
    return ImportResponse(
        success=result.success,
        records_processed=result.records_processed,
        records_imported=result.records_imported,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        errors=result.errors,
        warnings=result.warnings,
        import_time_seconds=result.import_time_seconds,
    )


@router.post("/parts/validate", response_model=ValidationResponse)
async def validate_parts_file(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
):
    """
    Validate parts import file without importing.
    
    Returns preview of data and suggested field mappings.
    """
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = DataImportService(session, current_user.tenant_id)
    
    result = await service.validate_import_file(
        file=file.file,
        filename=file.filename or "import.csv",
        entity_type="parts",
        config=erp_config,
    )
    
    return ValidationResponse(**result)


# Customers Import

@router.post("/customers", response_model=ImportResponse)
async def import_customers(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """Import customers from file."""
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = DataImportService(session, current_user.tenant_id)
    
    result = await service.import_customers(
        file=file.file,
        filename=file.filename or "import.csv",
        config=erp_config,
        update_existing=import_config.update_existing,
    )
    
    await session.commit()
    
    return ImportResponse(
        success=result.success,
        records_processed=result.records_processed,
        records_imported=result.records_imported,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        errors=result.errors,
        warnings=result.warnings,
        import_time_seconds=result.import_time_seconds,
    )


# Work Centers / Machine Rates Import

@router.post("/work-centers", response_model=ImportResponse)
async def import_work_centers(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """
    Import work centers with machine hour rates.
    
    Imports machine definitions including:
    - Machine/work center code and name
    - Machine hourly rate
    - Labor hourly rate
    - Overhead hourly rate
    - Default setup times
    """
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = ManufacturingCostImporter(session, current_user.tenant_id)
    
    result = await service.import_work_centers(
        file=file.file,
        filename=file.filename or "import.csv",
        config=erp_config,
        update_existing=import_config.update_existing,
    )
    
    await session.commit()
    
    return ImportResponse(
        success=result.success,
        records_processed=result.records_processed,
        records_imported=result.records_imported,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        errors=result.errors,
        warnings=result.warnings,
        import_time_seconds=result.import_time_seconds,
    )


# Labor Rates Import

@router.post("/labor-rates", response_model=ImportResponse)
async def import_labor_rates(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """
    Import labor rates by skill level.
    
    Imports labor classifications with:
    - Labor type (unskilled, skilled, technician, etc.)
    - Base hourly rate
    - Burden rate (benefits, insurance)
    - Overtime multiplier
    """
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = ManufacturingCostImporter(session, current_user.tenant_id)
    
    result = await service.import_labor_rates(
        file=file.file,
        filename=file.filename or "import.csv",
        config=erp_config,
        update_existing=import_config.update_existing,
    )
    
    await session.commit()
    
    return ImportResponse(
        success=result.success,
        records_processed=result.records_processed,
        records_imported=result.records_imported,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        errors=result.errors,
        warnings=result.warnings,
        import_time_seconds=result.import_time_seconds,
    )


# Material Costs Import

@router.post("/materials", response_model=ImportResponse)
async def import_material_costs(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """
    Import material costs and pricing.
    
    Imports material definitions with:
    - Material code and description
    - Cost per unit
    - Unit of measure
    - Scrap/waste factors
    - Supplier information
    - Lead times
    """
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = ManufacturingCostImporter(session, current_user.tenant_id)
    
    result = await service.import_material_costs(
        file=file.file,
        filename=file.filename or "import.csv",
        config=erp_config,
        update_existing=import_config.update_existing,
    )
    
    await session.commit()
    
    return ImportResponse(
        success=result.success,
        records_processed=result.records_processed,
        records_imported=result.records_imported,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        errors=result.errors,
        warnings=result.warnings,
        import_time_seconds=result.import_time_seconds,
    )


# Routings Import

@router.post("/routings", response_model=ImportResponse)
async def import_routings(
    file: UploadFile = File(...),
    config: str = Form("{}"),
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_service(ServiceType.QUOTE_INTELLIGENCE)),
    _: bool = Depends(require_permission("quote.write")),
):
    """
    Import manufacturing routings with operations.
    
    Imports process plans with:
    - Part number association
    - Operation sequence
    - Work center assignments
    - Setup and run times
    - Outside processing costs
    """
    import json
    
    try:
        config_data = json.loads(config)
        import_config = ImportConfigRequest(**config_data)
    except Exception:
        import_config = ImportConfigRequest()
    
    erp_config = ERPConnectionConfig(
        connection_type=ConnectionType.FILE_IMPORT,
        erp_system=import_config.erp_system,
        file_format=DataFormat(import_config.file_format),
        file_delimiter=import_config.file_delimiter,
        file_encoding=import_config.file_encoding,
        field_mappings=import_config.field_mappings,
    )
    
    service = ManufacturingCostImporter(session, current_user.tenant_id)
    
    result = await service.import_routings(
        file=file.file,
        filename=file.filename or "import.csv",
        config=erp_config,
        update_existing=import_config.update_existing,
    )
    
    await session.commit()
    
    return ImportResponse(
        success=result.success,
        records_processed=result.records_processed,
        records_imported=result.records_imported,
        records_updated=result.records_updated,
        records_skipped=result.records_skipped,
        errors=result.errors,
        warnings=result.warnings,
        import_time_seconds=result.import_time_seconds,
    )


# Get Field Mappings for ERP Systems

@router.get("/mappings/{erp_system}")
async def get_erp_field_mappings(
    erp_system: str,
    current_user: User = Depends(get_current_user),
) -> dict[str, dict[str, str]]:
    """
    Get suggested field mappings for a specific ERP system.
    
    Supports mappings for:
    - SAP (S/4HANA, Business One, ECC)
    - Oracle NetSuite
    - Epicor
    - JobBOSS
    - E2 Shop System
    - Generic (universal)
    """
    from services.integrations.erp_connector import ERPConnector
    
    return ERPConnector.get_standard_mappings(erp_system)


@router.get("/supported-systems")
async def get_supported_erp_systems(
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get list of supported ERP systems with integration details.
    """
    return {
        "universal": {
            "file_formats": ["CSV", "Excel (XLSX)", "JSON", "XML"],
            "note": "Works with any system that can export to these formats",
        },
        "systems_with_mappings": [
            {
                "name": "SAP",
                "versions": ["S/4HANA", "Business One", "ECC"],
                "integration_type": "File Import, API",
            },
            {
                "name": "Oracle NetSuite",
                "versions": ["All versions"],
                "integration_type": "File Import, REST API",
            },
            {
                "name": "Microsoft Dynamics",
                "versions": ["365", "NAV", "GP"],
                "integration_type": "File Import, OData",
            },
            {
                "name": "Epicor",
                "versions": ["Prophet 21", "Kinetic"],
                "integration_type": "File Import, REST API",
            },
            {
                "name": "SYSPRO",
                "versions": ["All versions"],
                "integration_type": "File Import",
            },
            {
                "name": "Infor",
                "versions": ["CloudSuite", "SyteLine", "VISUAL"],
                "integration_type": "File Import, API",
            },
            {
                "name": "Sage",
                "versions": ["100", "300", "X3"],
                "integration_type": "File Import",
            },
            {
                "name": "JobBOSS",
                "versions": ["All versions"],
                "integration_type": "File Import, ODBC",
            },
            {
                "name": "E2 Shop System",
                "versions": ["All versions"],
                "integration_type": "File Import",
            },
            {
                "name": "Global Shop Solutions",
                "versions": ["All versions"],
                "integration_type": "File Import",
            },
            {
                "name": "ECi M1",
                "versions": ["All versions"],
                "integration_type": "File Import",
            },
            {
                "name": "Plex",
                "versions": ["All versions"],
                "integration_type": "File Import, REST API",
            },
            {
                "name": "IQMS/DELMIAworks",
                "versions": ["All versions"],
                "integration_type": "File Import",
            },
        ],
        "custom": {
            "note": "For systems not listed, use 'generic' mappings and customize field names",
            "process": [
                "1. Export data from your ERP as CSV or Excel",
                "2. Use /imports/validate endpoint to preview and map fields",
                "3. Import with custom field_mappings in config",
            ],
        },
    }
