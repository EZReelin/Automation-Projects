"""
Manufacturing cost models.

Provides comprehensive cost tracking for:
- Machine hours and rates
- Labor rates by skill level
- Material costs and waste factors
- Overhead allocation
- Routing and operations
- Cost rollups for quoting
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean, DateTime, Enum as SQLEnum, ForeignKey,
    Integer, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import TenantBase

if TYPE_CHECKING:
    from models.quote_intelligence import Part


class CostType(str, Enum):
    """Types of manufacturing costs."""
    MATERIAL = "material"
    LABOR = "labor"
    MACHINE = "machine"
    TOOLING = "tooling"
    SETUP = "setup"
    OVERHEAD = "overhead"
    OUTSIDE_PROCESSING = "outside_processing"
    SHIPPING = "shipping"
    OTHER = "other"


class LaborType(str, Enum):
    """Labor skill classifications."""
    UNSKILLED = "unskilled"
    SEMI_SKILLED = "semi_skilled"
    SKILLED = "skilled"
    TECHNICIAN = "technician"
    ENGINEER = "engineer"
    SUPERVISOR = "supervisor"


class MachineType(str, Enum):
    """Common manufacturing machine types."""
    CNC_MILL = "cnc_mill"
    CNC_LATHE = "cnc_lathe"
    MANUAL_MILL = "manual_mill"
    MANUAL_LATHE = "manual_lathe"
    DRILL_PRESS = "drill_press"
    GRINDER = "grinder"
    EDM = "edm"
    LASER_CUTTER = "laser_cutter"
    PLASMA_CUTTER = "plasma_cutter"
    WATERJET = "waterjet"
    PRESS_BRAKE = "press_brake"
    PUNCH_PRESS = "punch_press"
    WELDING = "welding"
    ASSEMBLY = "assembly"
    INSPECTION = "inspection"
    PAINT_FINISH = "paint_finish"
    HEAT_TREAT = "heat_treat"
    OTHER = "other"


class WorkCenter(TenantBase):
    """
    Work center / machine definition.
    
    Represents a production resource with associated costs.
    """
    
    __tablename__ = "work_centers"
    
    # Identification
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Classification
    machine_type: Mapped[MachineType] = mapped_column(
        SQLEnum(MachineType),
        default=MachineType.OTHER,
    )
    department: Mapped[str | None] = mapped_column(String(100))
    
    # Capacity
    available_hours_per_day: Mapped[float] = mapped_column(Numeric(5, 2), default=8.0)
    available_days_per_week: Mapped[int] = mapped_column(Integer, default=5)
    efficiency_factor: Mapped[float] = mapped_column(Numeric(5, 4), default=0.85)
    
    # Hourly Rates (primary cost drivers)
    machine_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    labor_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    overhead_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    
    # Combined rate for convenience
    @property
    def total_rate_per_hour(self) -> Decimal:
        """Total hourly rate including machine, labor, and overhead."""
        return self.machine_rate_per_hour + self.labor_rate_per_hour + self.overhead_rate_per_hour
    
    # Setup costs
    default_setup_time_hours: Mapped[float] = mapped_column(Numeric(6, 2), default=0.5)
    setup_labor_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    
    # Capabilities
    capabilities: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    max_part_length: Mapped[float | None] = mapped_column(Numeric(10, 3))
    max_part_width: Mapped[float | None] = mapped_column(Numeric(10, 3))
    max_part_height: Mapped[float | None] = mapped_column(Numeric(10, 3))
    max_part_weight: Mapped[float | None] = mapped_column(Numeric(10, 3))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    operations: Mapped[list["RoutingOperation"]] = relationship(
        "RoutingOperation",
        back_populates="work_center",
    )
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_work_center_code"),
    )


class LaborRate(TenantBase):
    """
    Labor rate definitions by skill level.
    
    Used for calculating labor costs in routings and quotes.
    """
    
    __tablename__ = "labor_rates"
    
    # Classification
    labor_type: Mapped[LaborType] = mapped_column(
        SQLEnum(LaborType),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Rates
    base_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    burden_rate_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    """Burden includes benefits, insurance, etc."""
    
    overtime_multiplier: Mapped[float] = mapped_column(Numeric(4, 2), default=1.5)
    
    @property
    def fully_burdened_rate(self) -> Decimal:
        """Total labor cost including burden."""
        return self.base_rate_per_hour + self.burden_rate_per_hour
    
    # Effective dates
    effective_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "labor_type", "effective_date", name="uq_labor_rate"),
    )


class MaterialCost(TenantBase):
    """
    Material cost tracking with supplier pricing.
    
    Links to parts for material cost calculations.
    """
    
    __tablename__ = "material_costs"
    
    # Part Link (optional - can be standalone material)
    part_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("parts.id", ondelete="SET NULL"),
    )
    
    # Material Identification
    material_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    material_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Material Properties
    material_type: Mapped[str | None] = mapped_column(String(100))
    """e.g., Steel, Aluminum, Plastic, etc."""
    material_grade: Mapped[str | None] = mapped_column(String(100))
    """e.g., 6061-T6, 304SS, etc."""
    
    # Unit of Measure
    unit_of_measure: Mapped[str] = mapped_column(String(20), default="LB")
    """LB, KG, FT, M, EA, etc."""
    
    # Pricing
    cost_per_unit: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    minimum_order_qty: Mapped[float] = mapped_column(Numeric(15, 4), default=1)
    price_break_qty_1: Mapped[float | None] = mapped_column(Numeric(15, 4))
    price_break_cost_1: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    price_break_qty_2: Mapped[float | None] = mapped_column(Numeric(15, 4))
    price_break_cost_2: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    
    # Waste/Scrap Factors
    scrap_factor: Mapped[float] = mapped_column(Numeric(5, 4), default=0.05)
    """Expected scrap percentage (0.05 = 5%)"""
    kerf_loss_factor: Mapped[float] = mapped_column(Numeric(5, 4), default=0.0)
    """Material lost in cutting"""
    
    # Supplier
    primary_supplier: Mapped[str | None] = mapped_column(String(255))
    supplier_part_number: Mapped[str | None] = mapped_column(String(100))
    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    
    # Effective dates
    effective_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "material_code", "effective_date", name="uq_material_cost"),
    )


class Routing(TenantBase):
    """
    Manufacturing routing / process plan.
    
    Defines the sequence of operations to produce a part.
    """
    
    __tablename__ = "routings"
    
    # Part Link
    part_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Routing Identification
    routing_number: Mapped[str] = mapped_column(String(50), nullable=False)
    revision: Mapped[str] = mapped_column(String(20), default="A")
    description: Mapped[str | None] = mapped_column(Text)
    
    # Status
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True)
    """Primary routing used for standard costing"""
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Calculated Totals (cached)
    total_setup_hours: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    total_run_hours_per_piece: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    total_labor_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    total_machine_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    total_overhead_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Relationships
    operations: Mapped[list["RoutingOperation"]] = relationship(
        "RoutingOperation",
        back_populates="routing",
        cascade="all, delete-orphan",
        order_by="RoutingOperation.sequence",
    )
    
    __table_args__ = (
        UniqueConstraint("tenant_id", "part_id", "routing_number", "revision", name="uq_routing"),
    )


class RoutingOperation(TenantBase):
    """
    Individual operation within a routing.
    
    Defines work center, times, and costs for each step.
    """
    
    __tablename__ = "routing_operations"
    
    # Routing Link
    routing_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("routings.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Work Center
    work_center_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("work_centers.id"),
        nullable=False,
    )
    
    # Operation Details
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Time Standards (hours)
    setup_time_hours: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    run_time_hours_per_piece: Mapped[float] = mapped_column(Numeric(8, 4), default=0)
    """Time to produce one piece after setup"""
    
    pieces_per_hour: Mapped[float | None] = mapped_column(Numeric(10, 4))
    """Alternative to run_time - pieces produced per hour"""
    
    # Labor
    labor_type: Mapped[LaborType] = mapped_column(
        SQLEnum(LaborType),
        default=LaborType.SKILLED,
    )
    operators_required: Mapped[int] = mapped_column(Integer, default=1)
    
    # Rate Overrides (if different from work center defaults)
    machine_rate_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    labor_rate_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    overhead_rate_override: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    
    # Outside Processing
    is_outside_operation: Mapped[bool] = mapped_column(Boolean, default=False)
    outside_cost_per_piece: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    outside_vendor: Mapped[str | None] = mapped_column(String(255))
    outside_lead_time_days: Mapped[int | None] = mapped_column(Integer)
    
    # Tooling
    tooling_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    fixture_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    """One-time fixture cost, amortized over quantity"""
    
    # Instructions
    work_instructions: Mapped[str | None] = mapped_column(Text)
    quality_requirements: Mapped[str | None] = mapped_column(Text)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    routing: Mapped["Routing"] = relationship("Routing", back_populates="operations")
    work_center: Mapped["WorkCenter"] = relationship("WorkCenter", back_populates="operations")
    
    def calculate_labor_cost(self, quantity: int, labor_rate: Decimal) -> Decimal:
        """Calculate labor cost for given quantity."""
        total_hours = self.setup_time_hours + (self.run_time_hours_per_piece * quantity)
        return Decimal(str(total_hours)) * labor_rate * self.operators_required
    
    def calculate_machine_cost(self, quantity: int, machine_rate: Decimal) -> Decimal:
        """Calculate machine cost for given quantity."""
        total_hours = self.setup_time_hours + (self.run_time_hours_per_piece * quantity)
        return Decimal(str(total_hours)) * machine_rate


class OverheadRate(TenantBase):
    """
    Overhead allocation rates.
    
    Can be applied as percentage or fixed rate per hour.
    """
    
    __tablename__ = "overhead_rates"
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    
    # Allocation Method
    allocation_method: Mapped[str] = mapped_column(String(50), default="labor_hours")
    """labor_hours, machine_hours, labor_cost, material_cost"""
    
    # Rate
    rate_type: Mapped[str] = mapped_column(String(20), default="percentage")
    """percentage or fixed"""
    rate_value: Mapped[float] = mapped_column(Numeric(10, 4), nullable=False)
    """If percentage, 0.35 = 35%. If fixed, hourly rate."""
    
    # Scope
    applies_to_department: Mapped[str | None] = mapped_column(String(100))
    """If set, only applies to this department"""
    
    # Effective dates
    effective_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expiration_date: Mapped[datetime | None] = mapped_column(DateTime)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CostRollup(TenantBase):
    """
    Calculated cost rollup for a part.
    
    Consolidates all costs from routing, materials, and overhead.
    """
    
    __tablename__ = "cost_rollups"
    
    # Part Link
    part_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("parts.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Routing used
    routing_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("routings.id", ondelete="SET NULL"),
    )
    
    # Quantity basis
    standard_lot_size: Mapped[int] = mapped_column(Integer, default=100)
    
    # Material Costs
    material_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    material_scrap_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Labor Costs
    setup_labor_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    run_labor_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    total_labor_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Machine Costs
    setup_machine_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    run_machine_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    total_machine_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Overhead Costs
    overhead_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Outside Processing
    outside_processing_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Tooling (amortized)
    tooling_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Totals
    total_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Time Summaries
    total_setup_hours: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    total_run_hours_per_piece: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    
    # Calculation metadata
    calculated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    calculation_notes: Mapped[str | None] = mapped_column(Text)
    
    # Cost breakdown (detailed JSON)
    cost_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    """
    {
        "materials": [...],
        "operations": [...],
        "overhead": [...],
        "summary": {...}
    }
    """


class QuoteCostEstimate(TenantBase):
    """
    Detailed cost estimate for a quote line item.
    
    Captures all cost components for pricing decisions.
    """
    
    __tablename__ = "quote_cost_estimates"
    
    # Quote Line Item Link
    quote_line_item_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("quote_line_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Quantity
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # Material Costs
    material_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    material_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Labor Costs
    setup_hours: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    run_hours: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    total_labor_hours: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    labor_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    labor_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Machine Costs
    machine_hours: Mapped[float] = mapped_column(Numeric(10, 4), default=0)
    machine_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    machine_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Overhead
    overhead_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    overhead_cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Outside Services
    outside_processing_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    
    # Tooling
    tooling_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    
    # Totals
    total_cost: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    cost_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    
    # Markup/Margin
    target_margin_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=25)
    suggested_price_per_piece: Mapped[Decimal] = mapped_column(Numeric(15, 4), default=0)
    suggested_total_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=0)
    
    # Source of estimate
    estimate_source: Mapped[str] = mapped_column(String(50), default="manual")
    """manual, routing, ai, historical"""
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 4))
    
    # Detailed breakdown
    cost_breakdown: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    estimated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    estimated_by_id: Mapped[str | None] = mapped_column(UUID(as_uuid=False))
