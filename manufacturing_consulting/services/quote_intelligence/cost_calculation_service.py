"""
Manufacturing Cost Calculation Service.

Calculates comprehensive costs for quotes based on:
- Machine hours and rates
- Labor hours and rates
- Material costs with scrap factors
- Overhead allocations
- Outside processing
- Tooling and setup
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.manufacturing_costs import (
    WorkCenter, LaborRate, MaterialCost, Routing, RoutingOperation,
    OverheadRate, CostRollup, QuoteCostEstimate, LaborType
)
from models.quote_intelligence import Part, QuoteLineItem
from utils.logging import ServiceLogger


class CostCalculationService:
    """
    Service for calculating manufacturing costs.
    
    Provides detailed cost breakdowns for quoting including:
    - Material costs with scrap factors
    - Labor costs (setup and run)
    - Machine costs
    - Overhead allocations
    - Outside processing costs
    - Tooling and fixture costs
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("cost_calculation")
    
    async def calculate_part_cost(
        self,
        part_id: str,
        quantity: int,
        routing_id: str | None = None,
    ) -> dict:
        """
        Calculate total manufacturing cost for a part.
        
        Returns detailed cost breakdown.
        """
        part = await self._get_part(part_id)
        if not part:
            raise ValueError(f"Part {part_id} not found")
        
        # Get routing (primary if not specified)
        routing = await self._get_routing(part_id, routing_id)
        
        cost_breakdown = {
            "part_id": part_id,
            "part_number": part.part_number,
            "quantity": quantity,
            "routing_id": routing.id if routing else None,
            "calculated_at": datetime.utcnow().isoformat(),
            "materials": [],
            "operations": [],
            "overhead": [],
            "summary": {},
        }
        
        # Initialize totals
        total_material_cost = Decimal("0")
        total_setup_hours = 0.0
        total_run_hours = 0.0
        total_labor_cost = Decimal("0")
        total_machine_cost = Decimal("0")
        total_overhead_cost = Decimal("0")
        total_outside_cost = Decimal("0")
        total_tooling_cost = Decimal("0")
        
        # Calculate material costs
        material_costs = await self._get_material_costs(part_id)
        for mat in material_costs:
            mat_qty = quantity  # Could be adjusted based on BOM
            scrap_qty = mat_qty * mat.scrap_factor
            total_qty = mat_qty + scrap_qty
            
            cost = total_qty * mat.cost_per_unit
            total_material_cost += cost
            
            cost_breakdown["materials"].append({
                "material_code": mat.material_code,
                "material_name": mat.material_name,
                "quantity_needed": float(mat_qty),
                "scrap_quantity": float(scrap_qty),
                "total_quantity": float(total_qty),
                "unit_of_measure": mat.unit_of_measure,
                "cost_per_unit": float(mat.cost_per_unit),
                "total_cost": float(cost),
            })
        
        # Calculate operation costs from routing
        if routing:
            operations = await self._get_routing_operations(routing.id)
            
            for op in operations:
                work_center = await self._get_work_center(op.work_center_id)
                
                # Get rates (operation overrides or work center defaults)
                machine_rate = op.machine_rate_override or (
                    work_center.machine_rate_per_hour if work_center else Decimal("50")
                )
                labor_rate = op.labor_rate_override or (
                    work_center.labor_rate_per_hour if work_center else Decimal("35")
                )
                overhead_rate = op.overhead_rate_override or (
                    work_center.overhead_rate_per_hour if work_center else Decimal("20")
                )
                
                # Calculate times
                setup_hours = op.setup_time_hours
                
                # Run time: either per-piece time or derived from pieces_per_hour
                if op.run_time_hours_per_piece:
                    run_hours = op.run_time_hours_per_piece * quantity
                elif op.pieces_per_hour and op.pieces_per_hour > 0:
                    run_hours = quantity / op.pieces_per_hour
                else:
                    run_hours = 0
                
                total_hours = setup_hours + run_hours
                
                # Calculate costs
                if op.is_outside_operation:
                    op_outside_cost = (op.outside_cost_per_piece or Decimal("0")) * quantity
                    total_outside_cost += op_outside_cost
                    op_labor_cost = Decimal("0")
                    op_machine_cost = Decimal("0")
                else:
                    op_labor_cost = Decimal(str(total_hours)) * labor_rate * op.operators_required
                    op_machine_cost = Decimal(str(total_hours)) * machine_rate
                    op_outside_cost = Decimal("0")
                
                op_overhead_cost = Decimal(str(total_hours)) * overhead_rate
                op_tooling_cost = op.tooling_cost_per_piece * quantity
                
                total_setup_hours += setup_hours
                total_run_hours += run_hours
                total_labor_cost += op_labor_cost
                total_machine_cost += op_machine_cost
                total_overhead_cost += op_overhead_cost
                total_tooling_cost += op_tooling_cost
                
                cost_breakdown["operations"].append({
                    "sequence": op.sequence,
                    "operation_code": op.operation_code,
                    "description": op.description,
                    "work_center": work_center.code if work_center else None,
                    "is_outside": op.is_outside_operation,
                    "setup_hours": float(setup_hours),
                    "run_hours": float(run_hours),
                    "total_hours": float(total_hours),
                    "machine_rate": float(machine_rate),
                    "labor_rate": float(labor_rate),
                    "overhead_rate": float(overhead_rate),
                    "labor_cost": float(op_labor_cost),
                    "machine_cost": float(op_machine_cost),
                    "overhead_cost": float(op_overhead_cost),
                    "outside_cost": float(op_outside_cost),
                    "tooling_cost": float(op_tooling_cost),
                    "total_cost": float(
                        op_labor_cost + op_machine_cost + op_overhead_cost + 
                        op_outside_cost + op_tooling_cost
                    ),
                })
        
        # Apply overhead rates (if any additional global rates exist)
        overhead_rates = await self._get_overhead_rates()
        for rate in overhead_rates:
            if rate.allocation_method == "labor_hours":
                base = total_setup_hours + total_run_hours
            elif rate.allocation_method == "labor_cost":
                base = float(total_labor_cost)
            elif rate.allocation_method == "material_cost":
                base = float(total_material_cost)
            else:
                base = total_setup_hours + total_run_hours
            
            if rate.rate_type == "percentage":
                oh_cost = Decimal(str(base)) * Decimal(str(rate.rate_value))
            else:
                oh_cost = Decimal(str(base)) * Decimal(str(rate.rate_value))
            
            total_overhead_cost += oh_cost
            cost_breakdown["overhead"].append({
                "name": rate.name,
                "method": rate.allocation_method,
                "rate_type": rate.rate_type,
                "rate_value": float(rate.rate_value),
                "base_amount": float(base),
                "calculated_cost": float(oh_cost),
            })
        
        # Calculate totals
        total_cost = (
            total_material_cost +
            total_labor_cost +
            total_machine_cost +
            total_overhead_cost +
            total_outside_cost +
            total_tooling_cost
        )
        
        cost_per_piece = total_cost / quantity if quantity > 0 else Decimal("0")
        
        # Calculate suggested pricing with margins
        margins = [0.20, 0.25, 0.30, 0.35]  # 20%, 25%, 30%, 35%
        pricing_options = []
        
        for margin in margins:
            price_per_piece = cost_per_piece / (1 - Decimal(str(margin)))
            total_price = price_per_piece * quantity
            profit = total_price - total_cost
            
            pricing_options.append({
                "margin_percent": margin * 100,
                "price_per_piece": float(price_per_piece),
                "total_price": float(total_price),
                "profit": float(profit),
            })
        
        cost_breakdown["summary"] = {
            "quantity": quantity,
            "material_cost": float(total_material_cost),
            "labor_cost": float(total_labor_cost),
            "machine_cost": float(total_machine_cost),
            "overhead_cost": float(total_overhead_cost),
            "outside_processing_cost": float(total_outside_cost),
            "tooling_cost": float(total_tooling_cost),
            "total_cost": float(total_cost),
            "cost_per_piece": float(cost_per_piece),
            "setup_hours_total": float(total_setup_hours),
            "run_hours_total": float(total_run_hours),
            "total_hours": float(total_setup_hours + total_run_hours),
            "pricing_options": pricing_options,
        }
        
        return cost_breakdown
    
    async def calculate_quote_line_cost(
        self,
        quote_line_item_id: str,
    ) -> QuoteCostEstimate:
        """
        Calculate and save cost estimate for a quote line item.
        """
        line_item = await self._get_quote_line_item(quote_line_item_id)
        if not line_item:
            raise ValueError(f"Quote line item {quote_line_item_id} not found")
        
        # Calculate costs
        if line_item.part_id:
            cost_data = await self.calculate_part_cost(
                part_id=line_item.part_id,
                quantity=line_item.quantity,
            )
        else:
            # Custom item - use simplified calculation
            cost_data = await self._calculate_custom_item_cost(line_item)
        
        summary = cost_data["summary"]
        
        # Create cost estimate record
        estimate = QuoteCostEstimate(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            quote_line_item_id=quote_line_item_id,
            quantity=line_item.quantity,
            material_cost=Decimal(str(summary["material_cost"])),
            material_cost_per_piece=Decimal(str(summary["material_cost"])) / line_item.quantity,
            setup_hours=summary["setup_hours_total"],
            run_hours=summary["run_hours_total"],
            total_labor_hours=summary["total_hours"],
            labor_cost=Decimal(str(summary["labor_cost"])),
            labor_cost_per_piece=Decimal(str(summary["labor_cost"])) / line_item.quantity,
            machine_hours=summary["total_hours"],
            machine_cost=Decimal(str(summary["machine_cost"])),
            machine_cost_per_piece=Decimal(str(summary["machine_cost"])) / line_item.quantity,
            overhead_cost=Decimal(str(summary["overhead_cost"])),
            overhead_cost_per_piece=Decimal(str(summary["overhead_cost"])) / line_item.quantity,
            outside_processing_cost=Decimal(str(summary["outside_processing_cost"])),
            tooling_cost=Decimal(str(summary["tooling_cost"])),
            total_cost=Decimal(str(summary["total_cost"])),
            cost_per_piece=Decimal(str(summary["cost_per_piece"])),
            target_margin_percent=25.0,
            suggested_price_per_piece=Decimal(str(summary["cost_per_piece"])) / Decimal("0.75"),
            suggested_total_price=Decimal(str(summary["total_cost"])) / Decimal("0.75"),
            estimate_source="routing" if cost_data.get("routing_id") else "manual",
            cost_breakdown=cost_data,
        )
        
        self.session.add(estimate)
        await self.session.flush()
        
        return estimate
    
    async def rollup_part_cost(
        self,
        part_id: str,
        standard_lot_size: int = 100,
    ) -> CostRollup:
        """
        Create a standard cost rollup for a part.
        
        Used for inventory valuation and standard costing.
        """
        cost_data = await self.calculate_part_cost(part_id, standard_lot_size)
        summary = cost_data["summary"]
        
        rollup = CostRollup(
            id=str(uuid4()),
            tenant_id=self.tenant_id,
            part_id=part_id,
            routing_id=cost_data.get("routing_id"),
            standard_lot_size=standard_lot_size,
            material_cost_per_piece=Decimal(str(summary["material_cost"])) / standard_lot_size,
            setup_labor_cost_per_piece=Decimal(str(summary["labor_cost"])) * Decimal("0.2") / standard_lot_size,
            run_labor_cost_per_piece=Decimal(str(summary["labor_cost"])) * Decimal("0.8") / standard_lot_size,
            total_labor_cost_per_piece=Decimal(str(summary["labor_cost"])) / standard_lot_size,
            setup_machine_cost_per_piece=Decimal(str(summary["machine_cost"])) * Decimal("0.2") / standard_lot_size,
            run_machine_cost_per_piece=Decimal(str(summary["machine_cost"])) * Decimal("0.8") / standard_lot_size,
            total_machine_cost_per_piece=Decimal(str(summary["machine_cost"])) / standard_lot_size,
            overhead_cost_per_piece=Decimal(str(summary["overhead_cost"])) / standard_lot_size,
            outside_processing_cost_per_piece=Decimal(str(summary["outside_processing_cost"])) / standard_lot_size,
            tooling_cost_per_piece=Decimal(str(summary["tooling_cost"])) / standard_lot_size,
            total_cost_per_piece=Decimal(str(summary["cost_per_piece"])),
            total_setup_hours=summary["setup_hours_total"],
            total_run_hours_per_piece=summary["run_hours_total"] / standard_lot_size,
            cost_breakdown=cost_data,
        )
        
        self.session.add(rollup)
        await self.session.flush()
        
        return rollup
    
    async def estimate_cost_from_similar_parts(
        self,
        description: str,
        quantity: int,
    ) -> dict:
        """
        Estimate cost based on similar parts when no routing exists.
        
        Uses AI to find similar parts and extrapolate costs.
        """
        # This would integrate with the parts matching service
        # For now, return a placeholder structure
        return {
            "estimated": True,
            "confidence": 0.7,
            "quantity": quantity,
            "similar_parts_used": [],
            "estimated_cost_per_piece": 0,
            "estimated_total_cost": 0,
            "note": "Cost estimated based on similar parts - actual routing recommended",
        }
    
    async def _calculate_custom_item_cost(
        self,
        line_item: QuoteLineItem,
    ) -> dict:
        """Calculate costs for a custom (non-part) line item."""
        # For custom items, we use a simplified calculation
        # based on estimated hours and standard rates
        
        # Get default labor rate
        labor_rate = await self._get_default_labor_rate()
        machine_rate = Decimal("50")  # Default machine rate
        overhead_rate = Decimal("20")  # Default overhead rate
        
        # Estimate hours based on description or custom fields
        estimated_hours = 1.0  # Placeholder - would analyze description
        
        setup_hours = estimated_hours * 0.2
        run_hours = estimated_hours * 0.8 * line_item.quantity
        total_hours = setup_hours + run_hours
        
        labor_cost = Decimal(str(total_hours)) * labor_rate
        machine_cost = Decimal(str(total_hours)) * machine_rate
        overhead_cost = Decimal(str(total_hours)) * overhead_rate
        
        total_cost = labor_cost + machine_cost + overhead_cost
        cost_per_piece = total_cost / line_item.quantity if line_item.quantity > 0 else Decimal("0")
        
        return {
            "part_id": None,
            "custom_item": True,
            "quantity": line_item.quantity,
            "materials": [],
            "operations": [],
            "overhead": [],
            "summary": {
                "quantity": line_item.quantity,
                "material_cost": 0,
                "labor_cost": float(labor_cost),
                "machine_cost": float(machine_cost),
                "overhead_cost": float(overhead_cost),
                "outside_processing_cost": 0,
                "tooling_cost": 0,
                "total_cost": float(total_cost),
                "cost_per_piece": float(cost_per_piece),
                "setup_hours_total": setup_hours,
                "run_hours_total": run_hours,
                "total_hours": total_hours,
            },
        }
    
    # Database access methods
    
    async def _get_part(self, part_id: str) -> Part | None:
        result = await self.session.execute(
            select(Part).where(
                and_(
                    Part.id == part_id,
                    Part.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_routing(
        self,
        part_id: str,
        routing_id: str | None = None,
    ) -> Routing | None:
        if routing_id:
            result = await self.session.execute(
                select(Routing).where(
                    and_(
                        Routing.id == routing_id,
                        Routing.tenant_id == self.tenant_id,
                    )
                )
            )
        else:
            # Get primary routing
            result = await self.session.execute(
                select(Routing).where(
                    and_(
                        Routing.part_id == part_id,
                        Routing.tenant_id == self.tenant_id,
                        Routing.is_primary == True,
                        Routing.is_active == True,
                    )
                )
            )
        return result.scalar_one_or_none()
    
    async def _get_routing_operations(
        self,
        routing_id: str,
    ) -> list[RoutingOperation]:
        result = await self.session.execute(
            select(RoutingOperation).where(
                and_(
                    RoutingOperation.routing_id == routing_id,
                    RoutingOperation.tenant_id == self.tenant_id,
                    RoutingOperation.is_active == True,
                )
            ).order_by(RoutingOperation.sequence)
        )
        return list(result.scalars().all())
    
    async def _get_work_center(self, work_center_id: str) -> WorkCenter | None:
        result = await self.session.execute(
            select(WorkCenter).where(
                and_(
                    WorkCenter.id == work_center_id,
                    WorkCenter.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_material_costs(self, part_id: str) -> list[MaterialCost]:
        result = await self.session.execute(
            select(MaterialCost).where(
                and_(
                    MaterialCost.part_id == part_id,
                    MaterialCost.tenant_id == self.tenant_id,
                    MaterialCost.is_active == True,
                )
            )
        )
        return list(result.scalars().all())
    
    async def _get_overhead_rates(self) -> list[OverheadRate]:
        result = await self.session.execute(
            select(OverheadRate).where(
                and_(
                    OverheadRate.tenant_id == self.tenant_id,
                    OverheadRate.is_active == True,
                )
            )
        )
        return list(result.scalars().all())
    
    async def _get_default_labor_rate(self) -> Decimal:
        result = await self.session.execute(
            select(LaborRate).where(
                and_(
                    LaborRate.tenant_id == self.tenant_id,
                    LaborRate.labor_type == LaborType.SKILLED,
                    LaborRate.is_active == True,
                )
            )
        )
        rate = result.scalar_one_or_none()
        if rate:
            return rate.fully_burdened_rate
        return Decimal("35")  # Default fallback
    
    async def _get_quote_line_item(self, line_item_id: str) -> QuoteLineItem | None:
        result = await self.session.execute(
            select(QuoteLineItem).where(
                and_(
                    QuoteLineItem.id == line_item_id,
                    QuoteLineItem.tenant_id == self.tenant_id,
                )
            )
        )
        return result.scalar_one_or_none()
