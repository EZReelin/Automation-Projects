"""
Data Loader Module
=================
Loads data from various sources and formats.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class DataLoader:
    """
    Loads dart performance data from various sources.
    
    Handles JSON files from scrapers, biomechanics analysis,
    and voice observations.
    """
    
    DATA_SOURCES = ['scolia', 'dart_connect', 'biomechanics', 'voice_observation']
    
    def __init__(
        self,
        base_data_dir: Path,
        log_level: str = "INFO"
    ):
        """
        Initialize data loader.
        
        Args:
            base_data_dir: Base directory containing data folders
            log_level: Logging level
        """
        self.base_data_dir = Path(base_data_dir)
        
        # Setup source directories
        self.source_dirs = {
            'scolia': self.base_data_dir / 'scolia',
            'dart_connect': self.base_data_dir / 'dart_connect',
            'biomechanics': self.base_data_dir / 'biomechanics',
            'voice_observation': self.base_data_dir / 'voice'
        }
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
    
    def load_all(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load all data from all sources.
        
        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            Dictionary of data lists keyed by source
        """
        all_data = {}
        
        for source in self.DATA_SOURCES:
            all_data[source] = self.load_source(source, start_date, end_date)
        
        return all_data
    
    def load_source(
        self,
        source: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Load data from a specific source.
        
        Args:
            source: Data source name
            start_date: Optional start date filter
            end_date: Optional end date filter
            
        Returns:
            List of data records
        """
        if source not in self.source_dirs:
            self.logger.error(f"Unknown source: {source}")
            return []
        
        source_dir = self.source_dirs[source]
        
        if not source_dir.exists():
            self.logger.warning(f"Source directory not found: {source_dir}")
            return []
        
        records = []
        
        for filepath in source_dir.glob('*.json'):
            try:
                data = self._load_json_file(filepath)
                
                # Apply date filter
                if start_date or end_date:
                    record_date = self._extract_date(data)
                    if record_date:
                        if start_date and record_date < start_date:
                            continue
                        if end_date and record_date > end_date:
                            continue
                
                records.append(data)
                
            except Exception as e:
                self.logger.error(f"Error loading {filepath}: {e}")
                continue
        
        self.logger.info(f"Loaded {len(records)} records from {source}")
        return records
    
    def _load_json_file(self, filepath: Path) -> Dict[str, Any]:
        """Load a single JSON file."""
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Add file reference
        data['_source_file'] = str(filepath)
        
        return data
    
    def _extract_date(self, data: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from data record."""
        # Try common timestamp fields
        timestamp_fields = ['timestamp', 'generated_at', 'date', 'created_at']
        
        for field in timestamp_fields:
            if field in data:
                try:
                    ts = data[field]
                    if isinstance(ts, str):
                        # Try ISO format
                        return datetime.fromisoformat(ts.replace('Z', '+00:00'))
                    elif isinstance(ts, datetime):
                        return ts
                except (ValueError, TypeError):
                    continue
        
        return None
    
    def load_week(
        self,
        week_end_date: datetime
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load data for a specific week (7 days ending on given date).
        
        Args:
            week_end_date: End date of the week
            
        Returns:
            Dictionary of data lists keyed by source
        """
        from datetime import timedelta
        
        start_date = week_end_date - timedelta(days=7)
        end_date = week_end_date
        
        return self.load_all(start_date, end_date)
    
    def get_file_count(self, source: Optional[str] = None) -> Dict[str, int]:
        """Get count of files per source."""
        counts = {}
        
        sources = [source] if source else self.DATA_SOURCES
        
        for src in sources:
            if src in self.source_dirs and self.source_dirs[src].exists():
                counts[src] = len(list(self.source_dirs[src].glob('*.json')))
            else:
                counts[src] = 0
        
        return counts
    
    def load_latest(self, source: str, n: int = 1) -> List[Dict[str, Any]]:
        """
        Load the most recent records from a source.
        
        Args:
            source: Data source name
            n: Number of records to load
            
        Returns:
            List of most recent records
        """
        records = self.load_source(source)
        
        # Sort by timestamp
        sorted_records = sorted(
            records,
            key=lambda x: self._extract_date(x) or datetime.min,
            reverse=True
        )
        
        return sorted_records[:n]
