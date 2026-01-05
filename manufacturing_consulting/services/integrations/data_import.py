"""
General Data Import Service.

Provides universal import capabilities for parts, customers,
and historical data from any ERP or data source.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, BinaryIO
from uuid import uuid4

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.quote_intelligence import Part, Customer, PartCategory
from services.integrations.erp_connector import (
    ERPConnectionConfig, FileBasedConnector, ImportResult
)
from utils.logging import ServiceLogger


class DataImportService:
    """
    Universal data import service.
    
    Supports importing data from any ERP system through:
    - CSV files (universal)
    - Excel files
    - JSON exports
    - XML exports
    - Direct API connections
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("data_import")
    
    async def import_parts(
        self,
        file: BinaryIO,
        filename: str,
        config: ERPConnectionConfig,
        update_existing: bool = True,
    ) -> ImportResult:
        """
        Import parts from file.
        
        Automatically maps common field names from various ERP systems:
        - SAP: MATNR, MAKTX, MTART
        - NetSuite: itemid, displayname
        - Epicor: PartNum, PartDescription
        - Generic: part_number, name, description
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
                # Try multiple field name patterns
                part_number = self._get_value(record, [
                    'part_number', 'part_no', 'partnum', 'item_number', 
                    'item_id', 'itemid', 'sku', 'matnr', 'product_code'
                ])
                
                if not part_number:
                    result.errors.append({
                        "row": idx,
                        "error": "Missing part number",
                        "record": record,
                    })
                    result.records_skipped += 1
                    continue
                
                # Check for existing part
                existing = await self._get_part_by_number(str(part_number))
                
                part_data = {
                    "part_number": str(part_number),
                    "name": self._get_value(record, [
                        'name', 'description', 'part_description', 'partdescription',
                        'displayname', 'maktx', 'item_name', 'title'
                    ], str(part_number)),
                    "description": self._get_value(record, [
                        'description', 'long_description', 'notes', 'details'
                    ]),
                    "category": self._parse_category(
                        self._get_value(record, ['category', 'type', 'class', 'mtart'])
                    ),
                    "unit_cost": self._to_decimal(
                        self._get_value(record, [
                            'unit_cost', 'cost', 'standard_cost', 'stprs', 'avgcost'
                        ])
                    ),
                    "list_price": self._to_decimal(
                        self._get_value(record, [
                            'list_price', 'price', 'sell_price', 'baseprice', 'unitprice'
                        ])
                    ),
                    "minimum_order_qty": self._to_int(
                        self._get_value(record, ['min_qty', 'moq', 'minimum_order'], 1)
                    ),
                    "lead_time_days": self._to_int(
                        self._get_value(record, ['lead_time', 'leadtime', 'days_to_ship'])
                    ),
                }
                
                # Handle tags/keywords
                tags_value = self._get_value(record, ['tags', 'keywords', 'search_terms'])
                if tags_value:
                    if isinstance(tags_value, str):
                        part_data["tags"] = [t.strip() for t in tags_value.split(',')]
                    elif isinstance(tags_value, list):
                        part_data["tags"] = tags_value
                
                if existing:
                    if update_existing:
                        for key, value in part_data.items():
                            if value is not None:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        result.records_updated += 1
                    else:
                        result.records_skipped += 1
                else:
                    part = Part(
                        id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        **part_data,
                    )
                    self.session.add(part)
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
        
        self.logger.log_operation_complete(
            "import_parts",
            tenant_id=self.tenant_id,
            imported=result.records_imported,
            updated=result.records_updated,
            skipped=result.records_skipped,
        )
        
        return result
    
    async def import_customers(
        self,
        file: BinaryIO,
        filename: str,
        config: ERPConnectionConfig,
        update_existing: bool = True,
    ) -> ImportResult:
        """
        Import customers from file.
        
        Supports field mappings from various ERP systems.
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
                # Get customer identifier
                code = self._get_value(record, [
                    'customer_code', 'customer_id', 'code', 'id', 'custnum', 'kunnr'
                ])
                name = self._get_value(record, [
                    'name', 'customer_name', 'company', 'companyname', 'name1'
                ])
                
                if not name:
                    result.errors.append({
                        "row": idx,
                        "error": "Missing customer name",
                    })
                    result.records_skipped += 1
                    continue
                
                customer_data = {
                    "code": str(code) if code else None,
                    "name": str(name),
                    "company": self._get_value(record, ['company', 'organization']),
                    "email": self._get_value(record, ['email', 'email_address', 'e_mail']),
                    "phone": self._get_value(record, ['phone', 'telephone', 'tel']),
                    "price_tier": self._get_value(record, ['price_tier', 'pricing_level'], "standard"),
                    "discount_percentage": self._to_decimal(
                        self._get_value(record, ['discount', 'discount_percent'], 0)
                    ),
                    "payment_terms": self._get_value(record, ['payment_terms', 'terms'], "Net 30"),
                }
                
                # Handle address
                address = {}
                addr_fields = ['address', 'street', 'address1', 'line1']
                for field in addr_fields:
                    if field in record or field.lower() in [k.lower() for k in record.keys()]:
                        address['line1'] = self._get_value(record, [field])
                        break
                
                address['city'] = self._get_value(record, ['city', 'town'])
                address['state'] = self._get_value(record, ['state', 'province', 'region'])
                address['postal_code'] = self._get_value(record, ['postal_code', 'zip', 'postcode'])
                address['country'] = self._get_value(record, ['country'], "USA")
                
                if any(address.values()):
                    customer_data['address'] = address
                
                # Check for existing customer
                existing = await self._get_customer_by_code(customer_data.get('code'))
                
                if existing:
                    if update_existing:
                        for key, value in customer_data.items():
                            if value is not None:
                                setattr(existing, key, value)
                        existing.updated_at = datetime.utcnow()
                        result.records_updated += 1
                    else:
                        result.records_skipped += 1
                else:
                    customer = Customer(
                        id=str(uuid4()),
                        tenant_id=self.tenant_id,
                        **customer_data,
                    )
                    self.session.add(customer)
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
    
    async def validate_import_file(
        self,
        file: BinaryIO,
        filename: str,
        entity_type: str,
        config: ERPConnectionConfig,
    ) -> dict:
        """
        Validate import file without importing.
        
        Returns preview of data and any validation issues.
        """
        connector = FileBasedConnector(config)
        records = await connector.parse_file(file, filename)
        
        # Get sample records
        sample_records = records[:5] if len(records) > 5 else records
        
        # Detect columns
        columns = set()
        for record in records:
            columns.update(record.keys())
        
        # Check for required fields
        required_fields = {
            "parts": ["part_number", "name"],
            "customers": ["name"],
            "work_centers": ["code"],
            "routings": ["part_number", "sequence", "work_center"],
        }
        
        entity_required = required_fields.get(entity_type, [])
        missing_required = []
        
        # Build column mapping suggestions
        column_mappings = self._suggest_mappings(columns, entity_type)
        
        for required in entity_required:
            if required not in column_mappings.values():
                missing_required.append(required)
        
        return {
            "valid": len(missing_required) == 0,
            "record_count": len(records),
            "columns_detected": list(columns),
            "suggested_mappings": column_mappings,
            "missing_required_fields": missing_required,
            "sample_records": sample_records,
            "warnings": [],
        }
    
    def _suggest_mappings(self, columns: set, entity_type: str) -> dict:
        """Suggest field mappings based on detected columns."""
        mapping_patterns = {
            "parts": {
                "part_number": ["part_number", "part_no", "partnum", "item_number", "sku", "matnr"],
                "name": ["name", "description", "part_description", "displayname", "maktx"],
                "unit_cost": ["cost", "unit_cost", "standard_cost", "avgcost"],
                "list_price": ["price", "list_price", "sell_price", "baseprice"],
            },
            "work_centers": {
                "code": ["code", "work_center", "resource", "machine", "arbpl"],
                "name": ["name", "description", "ktext"],
                "machine_rate_per_hour": ["rate", "hourly_rate", "machine_rate"],
            },
        }
        
        patterns = mapping_patterns.get(entity_type, {})
        mappings = {}
        
        for our_field, possible_names in patterns.items():
            for col in columns:
                if col.lower() in [p.lower() for p in possible_names]:
                    mappings[col] = our_field
                    break
        
        return mappings
    
    # Helper methods
    
    def _get_value(
        self,
        record: dict,
        keys: list[str],
        default: Any = None,
    ) -> Any:
        """Get value from record trying multiple key names."""
        for key in keys:
            if key in record and record[key] is not None and record[key] != "":
                return record[key]
            for k, v in record.items():
                if k.lower() == key.lower() and v is not None and v != "":
                    return v
        return default
    
    def _to_decimal(self, value: Any, default: Decimal | None = None) -> Decimal | None:
        """Convert value to Decimal."""
        if value is None:
            return default
        try:
            if isinstance(value, str):
                value = value.replace("$", "").replace(",", "").strip()
            return Decimal(str(value))
        except Exception:
            return default
    
    def _to_int(self, value: Any, default: int | None = None) -> int | None:
        """Convert value to int."""
        if value is None:
            return default
        try:
            return int(float(str(value).replace(",", "")))
        except Exception:
            return default
    
    def _parse_category(self, value: Any) -> PartCategory:
        """Parse part category from string."""
        if not value:
            return PartCategory.COMPONENT
        
        value_lower = str(value).lower()
        
        if "raw" in value_lower or "material" in value_lower:
            return PartCategory.RAW_MATERIAL
        elif "assembl" in value_lower:
            return PartCategory.ASSEMBLY
        elif "finish" in value_lower:
            return PartCategory.FINISHED_GOOD
        elif "tool" in value_lower:
            return PartCategory.TOOLING
        elif "consumab" in value_lower:
            return PartCategory.CONSUMABLE
        elif "service" in value_lower:
            return PartCategory.SERVICE
        else:
            return PartCategory.COMPONENT
    
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
    
    async def _get_customer_by_code(self, code: str | None) -> Customer | None:
        """Get customer by code."""
        if not code:
            return None
        result = await self.session.execute(
            select(Customer).where(
                and_(
                    Customer.tenant_id == self.tenant_id,
                    Customer.code == code,
                )
            )
        )
        return result.scalar_one_or_none()
