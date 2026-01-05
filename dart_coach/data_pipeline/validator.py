"""
Data Validator Module
====================
Validates data against JSON schemas.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import jsonschema


class DataValidator:
    """
    Validates dart performance data against defined schemas.
    """
    
    SCHEMA_MAP = {
        'scolia': 'scolia_schema.json',
        'dart_connect': 'dart_connect_schema.json',
        'biomechanics': 'biomechanics_schema.json',
        'voice_observation': 'voice_observation_schema.json',
        'weekly_analysis': 'weekly_analysis_schema.json'
    }
    
    def __init__(
        self,
        schema_dir: Path,
        log_level: str = "INFO"
    ):
        """
        Initialize validator.
        
        Args:
            schema_dir: Directory containing schema files
            log_level: Logging level
        """
        self.schema_dir = Path(schema_dir)
        self.schemas: Dict[str, dict] = {}
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
        
        # Load schemas
        self._load_schemas()
    
    def _load_schemas(self):
        """Load all schema files."""
        for source, filename in self.SCHEMA_MAP.items():
            filepath = self.schema_dir / filename
            
            if filepath.exists():
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.schemas[source] = json.load(f)
                self.logger.debug(f"Loaded schema: {source}")
            else:
                self.logger.warning(f"Schema file not found: {filepath}")
    
    def validate(
        self,
        data: Dict[str, Any],
        source: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate data against its schema.
        
        Args:
            data: Data to validate
            source: Data source type
            
        Returns:
            Tuple of (is_valid, list of error messages)
        """
        if source not in self.schemas:
            return True, []  # No schema to validate against
        
        schema = self.schemas[source]
        errors = []
        
        try:
            jsonschema.validate(instance=data, schema=schema)
            return True, []
            
        except jsonschema.ValidationError as e:
            errors.append(f"Validation error at {e.json_path}: {e.message}")
            
        except jsonschema.SchemaError as e:
            errors.append(f"Schema error: {e.message}")
        
        return False, errors
    
    def validate_batch(
        self,
        data_list: List[Dict[str, Any]],
        source: str
    ) -> Tuple[int, int, List[Tuple[int, List[str]]]]:
        """
        Validate a batch of records.
        
        Args:
            data_list: List of data records
            source: Data source type
            
        Returns:
            Tuple of (valid_count, invalid_count, list of (index, errors))
        """
        valid_count = 0
        invalid_count = 0
        all_errors = []
        
        for i, data in enumerate(data_list):
            is_valid, errors = self.validate(data, source)
            
            if is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                all_errors.append((i, errors))
        
        return valid_count, invalid_count, all_errors
    
    def get_required_fields(self, source: str) -> List[str]:
        """Get list of required fields for a source."""
        if source not in self.schemas:
            return []
        
        return self.schemas[source].get('required', [])
    
    def sanitize_data(
        self,
        data: Dict[str, Any],
        source: str
    ) -> Dict[str, Any]:
        """
        Sanitize data to ensure required fields exist.
        
        Args:
            data: Data to sanitize
            source: Data source type
            
        Returns:
            Sanitized data with required fields
        """
        if source not in self.schemas:
            return data
        
        schema = self.schemas[source]
        sanitized = data.copy()
        
        # Ensure required fields exist
        required = schema.get('required', [])
        properties = schema.get('properties', {})
        
        for field in required:
            if field not in sanitized:
                # Add default value based on type
                field_schema = properties.get(field, {})
                field_type = field_schema.get('type', 'string')
                
                defaults = {
                    'string': '',
                    'integer': 0,
                    'number': 0.0,
                    'boolean': False,
                    'array': [],
                    'object': {}
                }
                
                sanitized[field] = defaults.get(field_type, None)
        
        return sanitized
