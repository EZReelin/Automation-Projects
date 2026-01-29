"""
Universal ERP Connector.

Provides a flexible integration layer supporting multiple connection methods
to work with virtually any manufacturing ERP system.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, BinaryIO
import csv
import io
import json

from sqlalchemy.ext.asyncio import AsyncSession

from utils.logging import ServiceLogger


class ConnectionType(str, Enum):
    """Types of ERP connections."""
    FILE_IMPORT = "file_import"  # CSV, Excel, XML
    REST_API = "rest_api"
    SOAP_API = "soap_api"
    ODATA = "odata"
    DATABASE = "database"  # ODBC/JDBC
    WEBHOOK = "webhook"
    CUSTOM = "custom"


class DataFormat(str, Enum):
    """Supported data formats."""
    CSV = "csv"
    EXCEL = "excel"
    JSON = "json"
    XML = "xml"
    FIXED_WIDTH = "fixed_width"


@dataclass
class ERPConnectionConfig:
    """
    Configuration for ERP connection.
    
    Flexible enough to support any ERP system.
    """
    connection_type: ConnectionType
    erp_system: str  # Free-form name
    erp_version: str | None = None
    
    # API Settings
    api_base_url: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    oauth_token_url: str | None = None
    
    # Database Settings
    db_connection_string: str | None = None
    db_driver: str | None = None
    
    # File Settings
    file_format: DataFormat = DataFormat.CSV
    file_encoding: str = "utf-8"
    file_delimiter: str = ","
    
    # Field Mappings (ERP field name -> our field name)
    field_mappings: dict[str, str] = field(default_factory=dict)
    
    # Custom settings
    custom_settings: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportResult:
    """Result of a data import operation."""
    success: bool
    records_processed: int
    records_imported: int
    records_updated: int
    records_skipped: int
    errors: list[dict]
    warnings: list[str]
    import_time_seconds: float


class BaseERPConnector(ABC):
    """Abstract base class for ERP connectors."""
    
    def __init__(self, config: ERPConnectionConfig):
        self.config = config
        self.logger = ServiceLogger(f"erp_connector.{config.erp_system}")
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """Test the ERP connection."""
        pass
    
    @abstractmethod
    async def fetch_data(self, entity: str, filters: dict | None = None) -> list[dict]:
        """Fetch data from ERP."""
        pass


class FileBasedConnector(BaseERPConnector):
    """
    File-based connector for universal ERP compatibility.
    
    Works with CSV, Excel, JSON, XML exports from any ERP.
    """
    
    async def test_connection(self) -> bool:
        """File connector is always 'connected'."""
        return True
    
    async def fetch_data(self, entity: str, filters: dict | None = None) -> list[dict]:
        """Not applicable for file-based - use parse_file instead."""
        return []
    
    async def parse_file(
        self,
        file: BinaryIO,
        filename: str,
    ) -> list[dict]:
        """
        Parse an uploaded file into records.
        
        Applies field mappings from config.
        """
        records = []
        
        if self.config.file_format == DataFormat.CSV or filename.lower().endswith('.csv'):
            records = await self._parse_csv(file)
        elif self.config.file_format == DataFormat.JSON or filename.lower().endswith('.json'):
            records = await self._parse_json(file)
        elif filename.lower().endswith(('.xlsx', '.xls')):
            records = await self._parse_excel(file)
        elif filename.lower().endswith('.xml'):
            records = await self._parse_xml(file)
        
        # Apply field mappings
        if self.config.field_mappings:
            records = self._apply_mappings(records)
        
        return records
    
    async def _parse_csv(self, file: BinaryIO) -> list[dict]:
        """Parse CSV file."""
        content = file.read().decode(self.config.file_encoding)
        reader = csv.DictReader(
            io.StringIO(content),
            delimiter=self.config.file_delimiter,
        )
        return list(reader)
    
    async def _parse_json(self, file: BinaryIO) -> list[dict]:
        """Parse JSON file."""
        content = file.read().decode(self.config.file_encoding)
        data = json.loads(content)
        
        # Handle both array and object with array property
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            # Look for common array properties
            for key in ['data', 'records', 'items', 'results']:
                if key in data and isinstance(data[key], list):
                    return data[key]
        
        return [data] if isinstance(data, dict) else []
    
    async def _parse_excel(self, file: BinaryIO) -> list[dict]:
        """Parse Excel file."""
        try:
            import openpyxl
            
            workbook = openpyxl.load_workbook(file, read_only=True)
            sheet = workbook.active
            
            rows = list(sheet.iter_rows(values_only=True))
            if not rows:
                return []
            
            headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(rows[0])]
            
            records = []
            for row in rows[1:]:
                record = {}
                for i, value in enumerate(row):
                    if i < len(headers):
                        record[headers[i]] = value
                records.append(record)
            
            return records
        except ImportError:
            self.logger.log_operation_failed(
                "parse_excel",
                Exception("openpyxl not installed"),
            )
            return []
    
    async def _parse_xml(self, file: BinaryIO) -> list[dict]:
        """Parse XML file."""
        try:
            import xml.etree.ElementTree as ET
            
            content = file.read().decode(self.config.file_encoding)
            root = ET.fromstring(content)
            
            records = []
            # Assume each child of root is a record
            for child in root:
                record = {}
                for elem in child:
                    record[elem.tag] = elem.text
                records.append(record)
            
            return records
        except Exception as e:
            self.logger.log_operation_failed("parse_xml", e)
            return []
    
    def _apply_mappings(self, records: list[dict]) -> list[dict]:
        """Apply field mappings to records."""
        mapped_records = []
        
        for record in records:
            mapped = {}
            for erp_field, our_field in self.config.field_mappings.items():
                if erp_field in record:
                    mapped[our_field] = record[erp_field]
            
            # Include unmapped fields
            for key, value in record.items():
                if key not in self.config.field_mappings:
                    mapped[key] = value
            
            mapped_records.append(mapped)
        
        return mapped_records


class RESTAPIConnector(BaseERPConnector):
    """
    REST API connector for modern ERP systems.
    
    Supports OAuth, API keys, and basic authentication.
    """
    
    async def test_connection(self) -> bool:
        """Test API connection."""
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                headers = self._get_auth_headers()
                response = await client.get(
                    f"{self.config.api_base_url}/health",
                    headers=headers,
                    timeout=10.0,
                )
                return response.status_code < 400
        except Exception as e:
            self.logger.log_operation_failed("test_connection", e)
            return False
    
    async def fetch_data(
        self,
        entity: str,
        filters: dict | None = None,
    ) -> list[dict]:
        """Fetch data from REST API."""
        import httpx
        
        try:
            async with httpx.AsyncClient() as client:
                headers = self._get_auth_headers()
                
                url = f"{self.config.api_base_url}/{entity}"
                params = filters or {}
                
                response = await client.get(
                    url,
                    headers=headers,
                    params=params,
                    timeout=30.0,
                )
                response.raise_for_status()
                
                data = response.json()
                
                # Handle pagination if present
                if isinstance(data, dict):
                    for key in ['data', 'records', 'items', 'results', 'value']:
                        if key in data and isinstance(data[key], list):
                            return data[key]
                
                return data if isinstance(data, list) else [data]
                
        except Exception as e:
            self.logger.log_operation_failed("fetch_data", e, entity=entity)
            return []
    
    def _get_auth_headers(self) -> dict:
        """Build authentication headers."""
        headers = {"Content-Type": "application/json"}
        
        if self.config.api_key:
            # Try common API key header formats
            headers["Authorization"] = f"Bearer {self.config.api_key}"
            headers["X-API-Key"] = self.config.api_key
        
        return headers


class ERPConnector:
    """
    Factory class for creating appropriate ERP connectors.
    
    Automatically selects the right connector based on configuration.
    """
    
    def __init__(self, session: AsyncSession, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.logger = ServiceLogger("erp_connector")
    
    def create_connector(self, config: ERPConnectionConfig) -> BaseERPConnector:
        """Create the appropriate connector for the configuration."""
        if config.connection_type == ConnectionType.FILE_IMPORT:
            return FileBasedConnector(config)
        elif config.connection_type in [ConnectionType.REST_API, ConnectionType.ODATA]:
            return RESTAPIConnector(config)
        else:
            # Default to file-based for maximum compatibility
            return FileBasedConnector(config)
    
    @staticmethod
    def get_standard_mappings(erp_system: str) -> dict[str, dict[str, str]]:
        """
        Get standard field mappings for common ERP systems.
        
        These are starting points - clients will customize.
        """
        mappings = {
            "sap": {
                "parts": {
                    "MATNR": "part_number",
                    "MAKTX": "name",
                    "MTART": "category",
                    "MEINS": "unit_of_measure",
                    "VPREI": "list_price",
                    "STPRS": "unit_cost",
                },
                "work_centers": {
                    "ARBPL": "code",
                    "KTEXT": "name",
                    "KOSTL": "cost_center",
                    "VGWRT": "machine_rate_per_hour",
                },
            },
            "netsuite": {
                "parts": {
                    "itemid": "part_number",
                    "displayname": "name",
                    "description": "description",
                    "baseprice": "list_price",
                    "cost": "unit_cost",
                },
            },
            "epicor": {
                "parts": {
                    "PartNum": "part_number",
                    "PartDescription": "name",
                    "ClassID": "category",
                    "UnitPrice": "list_price",
                    "UnitCost": "unit_cost",
                },
                "work_centers": {
                    "ResourceID": "code",
                    "Description": "name",
                    "ProdBurRate": "machine_rate_per_hour",
                    "SetupBurRate": "setup_labor_rate_per_hour",
                },
            },
            "jobboss": {
                "parts": {
                    "Part_Number": "part_number",
                    "Description": "name",
                    "Sell_Price": "list_price",
                    "Unit_Cost": "unit_cost",
                },
                "work_centers": {
                    "Work_Center": "code",
                    "Description": "name",
                    "Hourly_Rate": "machine_rate_per_hour",
                },
            },
            "e2_shop": {
                "parts": {
                    "PartNo": "part_number",
                    "Description": "name",
                    "UnitPrice": "list_price",
                    "UnitCost": "unit_cost",
                },
            },
            # Generic/Universal mappings
            "generic": {
                "parts": {
                    "part_number": "part_number",
                    "part_no": "part_number",
                    "item_number": "part_number",
                    "item_id": "part_number",
                    "sku": "part_number",
                    "name": "name",
                    "description": "description",
                    "price": "list_price",
                    "cost": "unit_cost",
                    "unit_cost": "unit_cost",
                    "category": "category",
                },
                "work_centers": {
                    "code": "code",
                    "work_center": "code",
                    "resource": "code",
                    "name": "name",
                    "description": "name",
                    "rate": "machine_rate_per_hour",
                    "hourly_rate": "machine_rate_per_hour",
                    "labor_rate": "labor_rate_per_hour",
                },
                "routings": {
                    "part_number": "part_number",
                    "operation": "operation_code",
                    "sequence": "sequence",
                    "work_center": "work_center_code",
                    "setup_time": "setup_time_hours",
                    "run_time": "run_time_hours_per_piece",
                    "cycle_time": "run_time_hours_per_piece",
                },
            },
        }
        
        return mappings.get(erp_system.lower(), mappings["generic"])
