"""
Manufacturing Cost Import Service.

Imports machine hours, labor rates, routings, and material costs
from any ERP system or spreadsheet.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, BinaryIO
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.manufacturing_costs import (
    WorkCenter, LaborRate, MaterialCost, Routing, RoutingOperation,
    OverheadRate, MachineType, LaborType
)
from models.quote_intelligence import Part
from services.integrations.erp_connector import (
    ERPConnector, ERPConnectionConfig, FileBasedConnector, ImportResult
)
from utils.logging import ServiceLogger


class ManufacturingCostImporter:
    """
    Service for importing manufacturing cost data.
    
    Supports importing:
    - Work centers / machines with hourly rates
    - Labor rates by skill level
    - Material costs with supplier info
    - Routings and operations
    - Overhead allocation rates
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("cost_import")
    
    async def import_work_centers(
        self,
        file: BinaryIO,
        filename: str,
        config: ERPConnectionConfig,
        update_existing: bool = True,
    ) -> ImportResult:
        """
        Import work centers / machines from file.
        
        Expected columns (or mapped equivalents):
        - code: Work center code (required)
        - name: Description (required)
        - machine_rate_per_hour: Machine hourly rate
        - labor_rate_per_hour: Labor hourly rate
        - overhead_rate_per_hour: Overhead hourly rate
        - setup_time_hours: Default setup time
        - machine_type: Type classification
        """
        start_time = datetime.utcnow()
        connector = FileBasedConnector(config)
        records = await connector.parse_file(file, filename)
        
        result = ImportResult(
            success=True,
            records_processed=len(records),
            records_imported=0,
            records_updated=0,
            records_skipped=0,
            errors=[],
            warnings=[],
            import_time_seconds=0,
        )
        
        for idx, record in enumerate(records, 1):
            try:
                code = self._get_value(record, ['code', 'work_center', 'resource', 'machine'])
                if not code:
                    result.errors.append({
                        "row": idx,
                        "error": "Missing work center code",
                    })
                    result.records_skipped += 1
                    continue
                
                # Check for existing
                existing = await self._get_work_center_by_code(str(code))
                
                work_center_data = {
                    "code": str(code),
                    "name": self._get_value(record, ['name', 'description'], str(code)),
                    "machine_rate_per_hour": self._to_decimal(
                        self._get_value(record, ['machine_rate', 'machine_rate_per_hour', 'hourly_rate'], 0)
                    ),
                    "labor_rate_per_hour": self._to_decimal(
                        self._get_value(record, ['labor_rate', 'labor_rate_per_hour'], 0)
                    ),
                    "overhead_rate_per_hour": self._to_decimal(
                        self._get_value(record, ['overhead_rate', 'overhead_rate_per_hour', 'burden_rate'], 0)
                    ),
                    "default_setup_time_hours": self._to_float(
                        self._get_value(record, ['setup_time', 'setup_hours', 'default_setup'], 0.5)
                    ),
                    "department": self._get_value(record, ['department', 'dept']),
                    "machine_type": self._parse_machine_type(
                        self._get_value(record, ['machine_type', 'type'])
                    ),
                }
                
                if existing:
                    if update_existing:
                        for key, value in work_center_data.items():
                            if value is not None:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        result.records_updated += 1
                    else:
                        result.records_skipped += 1
                else:
                    work_center = WorkCenter(
                        id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        **work_center_data,
                    )
                    self.session.add(work_center)
                    result.records_imported += 1
                    
            except Exception as e:
                result.errors.append({
                    "row": idx,
                    "error": str(e),
                    "record": record,
                })
                result.records_skipped += 1
        
        await self.session.flush()
        
        result.import_time_seconds = (datetime.utcnow() - start_time).total_seconds()
        result.success = len(result.errors) == 0
        
        return result
    
    async def import_labor_rates(
        self,
        file: BinaryIO,
        filename: str,
        config: ERPConnectionConfig,
        update_existing: bool = True,
    ) -> ImportResult:
        """
        Import labor rates by skill level.
        
        Expected columns:
        - labor_type: Skill classification (unskilled, skilled, technician, etc.)
        - name: Rate name/description
        - base_rate: Hourly base rate
        - burden_rate: Benefits/burden rate
        """
        start_time = datetime.utcnow()
        connector = FileBasedConnector(config)
        records = await connector.parse_file(file, filename)
        
        result = ImportResult(
            success=True,
            records_processed=len(records),
            records_imported=0,
            records_updated=0,
            records_skipped=0,
            errors=[],
            warnings=[],
            import_time_seconds=0,
        )
        
        for idx, record in enumerate(records, 1):
            try:
                labor_type = self._parse_labor_type(
                    self._get_value(record, ['labor_type', 'type', 'skill_level'])
                )
                base_rate = self._to_decimal(
                    self._get_value(record, ['base_rate', 'hourly_rate', 'rate'])
                )
                
                if base_rate is None or base_rate == 0:
                    result.errors.append({
                        "row": idx,
                        "error": "Missing or invalid base rate",
                    })
                    result.records_skipped += 1
                    continue
                
                labor_rate = LaborRate(
                    id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    labor_type=labor_type,
                    name=self._get_value(record, ['name', 'description'], labor_type.value),
                    base_rate_per_hour=base_rate,
                    burden_rate_per_hour=self._to_decimal(
                        self._get_value(record, ['burden_rate', 'burden', 'benefits'], 0)
                    ),
                    overtime_multiplier=self._to_float(
                        self._get_value(record, ['overtime_multiplier', 'ot_rate'], 1.5)
                    ),
                )
                
                self.session.add(labor_rate)
                result.records_imported += 1
                
            except Exception as e:
                result.errors.append({
                    "row": idx,
                    "error": str(e),
                })
                result.records_skipped += 1
        
        await self.session.flush()
        
        result.import_time_seconds = (datetime.utcnow() - start_time).total_seconds()
        result.success = len(result.errors) == 0
        
        return result
    
    async def import_material_costs(
        self,
        file: BinaryIO,
        filename: str,
        config: ERPConnectionConfig,
        update_existing: bool = True,
    ) -> ImportResult:
        """
        Import material costs and pricing.
        
        Expected columns:
        - material_code: Unique identifier (required)
        - name: Material description (required)
        - cost_per_unit: Unit cost (required)
        - unit_of_measure: UOM (LB, KG, FT, etc.)
        - scrap_factor: Expected scrap percentage
        - supplier: Primary supplier name
        - lead_time: Lead time in days
        """
        start_time = datetime.utcnow()
        connector = FileBasedConnector(config)
        records = await connector.parse_file(file, filename)
        
        result = ImportResult(
            success=True,
            records_processed=len(records),
            records_imported=0,
            records_updated=0,
            records_skipped=0,
            errors=[],
            warnings=[],
            import_time_seconds=0,
        )
        
        for idx, record in enumerate(records, 1):
            try:
                material_code = self._get_value(record, ['material_code', 'code', 'item', 'sku'])
                if not material_code:
                    result.errors.append({
                        "row": idx,
                        "error": "Missing material code",
                    })
                    result.records_skipped += 1
                    continue
                
                cost = self._to_decimal(
                    self._get_value(record, ['cost_per_unit', 'cost', 'unit_cost', 'price'])
                )
                if cost is None:
                    result.errors.append({
                        "row": idx,
                        "error": "Missing cost per unit",
                    })
                    result.records_skipped += 1
                    continue
                
                material = MaterialCost(
                    id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    material_code=str(material_code),
                    material_name=self._get_value(record, ['name', 'description', 'material_name'], str(material_code)),
                    cost_per_unit=cost,
                    unit_of_measure=self._get_value(record, ['uom', 'unit_of_measure', 'unit'], "EA"),
                    material_type=self._get_value(record, ['material_type', 'type']),
                    material_grade=self._get_value(record, ['grade', 'material_grade']),
                    scrap_factor=self._to_float(
                        self._get_value(record, ['scrap_factor', 'scrap', 'waste'], 0.05)
                    ),
                    primary_supplier=self._get_value(record, ['supplier', 'vendor', 'primary_supplier']),
                    lead_time_days=self._to_int(
                        self._get_value(record, ['lead_time', 'lead_time_days'])
                    ),
                )
                
                self.session.add(material)
                result.records_imported += 1
                
            except Exception as e:
                result.errors.append({
                    "row": idx,
                    "error": str(e),
                })
                result.records_skipped += 1
        
        await self.session.flush()
        
        result.import_time_seconds = (datetime.utcnow() - start_time).total_seconds()
        result.success = len(result.errors) == 0
        
        return result
    
    async def import_routings(
        self,
        file: BinaryIO,
        filename: str,
        config: ERPConnectionConfig,
        update_existing: bool = True,
    ) -> ImportResult:
        """
        Import manufacturing routings with operations.
        
        Expected columns:
        - part_number: Part this routing is for (required)
        - sequence: Operation sequence number (required)
        - work_center: Work center code (required)
        - operation: Operation description
        - setup_time: Setup time in hours
        - run_time: Run time per piece in hours (or pieces_per_hour)
        - outside_cost: Cost for outside operations
        """
        start_time = datetime.utcnow()
        connector = FileBasedConnector(config)
        records = await connector.parse_file(file, filename)
        
        result = ImportResult(
            success=True,
            records_processed=len(records),
            records_imported=0,
            records_updated=0,
            records_skipped=0,
            errors=[],
            warnings=[],
            import_time_seconds=0,
        )
        
        # Group by part number
        routings_by_part: dict[str, list[dict]] = {}
        for record in records:
            part_number = self._get_value(record, ['part_number', 'part', 'item'])
            if part_number:
                if part_number not in routings_by_part:
                    routings_by_part[part_number] = []
                routings_by_part[part_number].append(record)
        
        for part_number, operations in routings_by_part.items():
            try:
                # Find part
                part = await self._get_part_by_number(part_number)
                if not part:
                    result.warnings.append(f"Part {part_number} not found, skipping routing")
                    result.records_skipped += len(operations)
                    continue
                
                # Create routing
                routing = Routing(
                    id=str(uuid4()),
                    tenant_id=self.tenant_id,
                    part_id=part.id,
                    routing_number=f"RTG-{part_number}",
                    is_primary=True,
                )
                self.session.add(routing)
                
                # Sort operations by sequence
                operations.sort(key=lambda x: self._to_int(
                    self._get_value(x, ['sequence', 'seq', 'op_seq']), 10
                ))
                
                for seq, op_record in enumerate(operations, 1):
                    work_center_code = self._get_value(op_record, ['work_center', 'resource', 'machine'])
                    work_center = await self._get_work_center_by_code(work_center_code) if work_center_code else None
                    
                    if not work_center:
                        result.warnings.append(
                            f"Work center {work_center_code} not found for part {part_number}"
                        )
                        # Create a default work center
                        work_center = WorkCenter(
                            id=str(uuid4()),
                            tenant_id=self.tenant_id,
                            code=work_center_code or f"WC-{seq}",
                            name=work_center_code or f"Work Center {seq}",
                        )
                        self.session.add(work_center)
                        await self.session.flush()
                    
                    # Calculate run time
                    run_time = self._to_float(
                        self._get_value(op_record, ['run_time', 'cycle_time', 'run_time_hours'])
                    )
                    pieces_per_hour = self._to_float(
                        self._get_value(op_record, ['pieces_per_hour', 'pph', 'parts_per_hour'])
                    )
                    
                    if pieces_per_hour and pieces_per_hour > 0:
                        run_time = 1.0 / pieces_per_hour
                    
                    operation = RoutingOperation(
                        id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        routing_id=routing.id,
                        work_center_id=work_center.id,
                        sequence=seq,
                        operation_code=self._get_value(op_record, ['operation_code', 'op_code'], f"OP{seq:02d}"),
                        description=self._get_value(op_record, ['description', 'operation', 'op_desc'], ""),
                        setup_time_hours=self._to_float(
                            self._get_value(op_record, ['setup_time', 'setup_hours', 'setup'], 0)
                        ),
                        run_time_hours_per_piece=run_time or 0,
                        is_outside_operation=bool(
                            self._get_value(op_record, ['outside', 'is_outside', 'subcontract'])
                        ),
                        outside_cost_per_piece=self._to_decimal(
                            self._get_value(op_record, ['outside_cost', 'subcontract_cost'])
                        ),
                    )
                    self.session.add(operation)
                    result.records_imported += 1
                    
            except Exception as e:
                result.errors.append({
                    "part_number": part_number,
                    "error": str(e),
                })
                result.records_skipped += len(operations)
        
        await self.session.flush()
        
        result.import_time_seconds = (datetime.utcnow() - start_time).total_seconds()
        result.success = len(result.errors) == 0
        
        return result
    
    # Helper methods
    
    def _get_value(
        self,
        record: dict,
        keys: list[str],
        default: Any = None,
    ) -> Any:
        """Get value from record trying multiple key names."""
        for key in keys:
            # Try exact match
            if key in record and record[key] is not None and record[key] != "":
                return record[key]
            # Try case-insensitive
            for k, v in record.items():
                if k.lower() == key.lower() and v is not None and v != "":
                    return v
        return default
    
    def _to_decimal(self, value: Any, default: Decimal = Decimal("0")) -> Decimal:
        """Convert value to Decimal."""
        if value is None:
            return default
        try:
            # Remove currency symbols and commas
            if isinstance(value, str):
                value = value.replace("$", "").replace(",", "").strip()
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return default
    
    def _to_float(self, value: Any, default: float = 0.0) -> float:
        """Convert value to float."""
        if value is None:
            return default
        try:
            if isinstance(value, str):
                value = value.replace(",", "").strip()
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def _to_int(self, value: Any, default: int = 0) -> int:
        """Convert value to int."""
        if value is None:
            return default
        try:
            return int(float(str(value).replace(",", "")))
        except (ValueError, TypeError):
            return default
    
    def _parse_machine_type(self, value: Any) -> MachineType:
        """Parse machine type from string."""
        if not value:
            return MachineType.OTHER
        
        value_lower = str(value).lower()
        
        type_mappings = {
            "cnc mill": MachineType.CNC_MILL,
            "cnc lathe": MachineType.CNC_LATHE,
            "mill": MachineType.MANUAL_MILL,
            "lathe": MachineType.MANUAL_LATHE,
            "drill": MachineType.DRILL_PRESS,
            "grind": MachineType.GRINDER,
            "edm": MachineType.EDM,
            "laser": MachineType.LASER_CUTTER,
            "plasma": MachineType.PLASMA_CUTTER,
            "waterjet": MachineType.WATERJET,
            "press brake": MachineType.PRESS_BRAKE,
            "punch": MachineType.PUNCH_PRESS,
            "weld": MachineType.WELDING,
            "assembly": MachineType.ASSEMBLY,
            "inspect": MachineType.INSPECTION,
            "paint": MachineType.PAINT_FINISH,
            "heat treat": MachineType.HEAT_TREAT,
        }
        
        for key, machine_type in type_mappings.items():
            if key in value_lower:
                return machine_type
        
        return MachineType.OTHER
    
    def _parse_labor_type(self, value: Any) -> LaborType:
        """Parse labor type from string."""
        if not value:
            return LaborType.SKILLED
        
        value_lower = str(value).lower()
        
        if "unskill" in value_lower:
            return LaborType.UNSKILLED
        elif "semi" in value_lower:
            return LaborType.SEMI_SKILLED
        elif "tech" in value_lower:
            return LaborType.TECHNICIAN
        elif "engineer" in value_lower:
            return LaborType.ENGINEER
        elif "super" in value_lower:
            return LaborType.SUPERVISOR
        else:
            return LaborType.SKILLED
    
    async def _get_work_center_by_code(self, code: str) -> WorkCenter | None:
        """Get work center by code."""
        result = await self.session.execute(
            select(WorkCenter).where(
                and_(
                    WorkCenter.tenant_id == self.tenant_id,
                    WorkCenter.code == code,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_part_by_number(self, part_number: str) -> Part | None:
        """Get part by part number."""
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.tenant_id == self.tenant_id,
                    Part.part_number == part_number,
                )
            )
        )
        return result.scalar_one_or_none()
