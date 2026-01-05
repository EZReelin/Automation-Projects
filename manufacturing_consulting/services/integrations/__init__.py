"""
ERP Integration Services.

Provides open, universal connectivity to manufacturing ERP systems
through multiple integration patterns:

1. **File-Based Import/Export** (CSV, Excel, XML)
   - Universal compatibility with any ERP
   - Batch data synchronization
   - Historical data import

2. **API Connectors** (REST, SOAP, OData)
   - Real-time data access
   - Bi-directional sync
   - Webhook support

3. **Database Direct Connect** (ODBC, JDBC)
   - Read-only access to ERP databases
   - Custom queries
   - Real-time data extraction

Supported ERP Systems (with varying integration levels):
- SAP (S/4HANA, Business One, ECC)
- Oracle (NetSuite, JD Edwards, E-Business Suite)
- Microsoft Dynamics (365, NAV, GP)
- Epicor (Prophet 21, Kinetic)
- SYSPRO
- Infor (CloudSuite, SyteLine, VISUAL)
- Sage (100, 300, X3)
- IQMS/DELMIAworks
- JobBOSS
- E2 Shop System
- Global Shop Solutions
- ECi M1
- Plex
- Any system with CSV/Excel export capability
"""

from services.integrations.erp_connector import ERPConnector, ERPConnectionConfig
from services.integrations.data_import import DataImportService
from services.integrations.cost_import import ManufacturingCostImporter

__all__ = [
    "ERPConnector",
    "ERPConnectionConfig",
    "DataImportService",
    "ManufacturingCostImporter",
]
