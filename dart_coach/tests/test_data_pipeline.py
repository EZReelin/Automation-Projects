"""
Tests for the data pipeline module.
"""

import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from dart_coach.data_pipeline.loader import DataLoader
from dart_coach.data_pipeline.validator import DataValidator
from dart_coach.data_pipeline.aggregator import DataAggregator


class TestDataLoader:
    """Tests for DataLoader class."""
    
    def test_load_source_empty_directory(self):
        """Test loading from empty directory."""
        with TemporaryDirectory() as tmpdir:
            loader = DataLoader(Path(tmpdir))
            records = loader.load_source('scolia')
            assert records == []
    
    def test_load_json_file(self):
        """Test loading a JSON file."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'scolia').mkdir()
            
            # Create test data
            test_data = {
                'session_id': 'scolia_20240101_120000',
                'timestamp': '2024-01-01T12:00:00',
                'metrics': {'three_dart_average': 55.5}
            }
            
            with open(tmppath / 'scolia' / 'test.json', 'w') as f:
                json.dump(test_data, f)
            
            loader = DataLoader(tmppath)
            records = loader.load_source('scolia')
            
            assert len(records) == 1
            assert records[0]['session_id'] == 'scolia_20240101_120000'
    
    def test_date_filtering(self):
        """Test date range filtering."""
        with TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            (tmppath / 'scolia').mkdir()
            
            # Create test data with different dates
            for i, date in enumerate(['2024-01-01', '2024-01-05', '2024-01-10']):
                data = {
                    'session_id': f'scolia_{i}',
                    'timestamp': f'{date}T12:00:00'
                }
                with open(tmppath / 'scolia' / f'test_{i}.json', 'w') as f:
                    json.dump(data, f)
            
            loader = DataLoader(tmppath)
            
            # Filter to only include middle date
            records = loader.load_source(
                'scolia',
                start_date=datetime(2024, 1, 3),
                end_date=datetime(2024, 1, 7)
            )
            
            assert len(records) == 1
            assert records[0]['session_id'] == 'scolia_1'


class TestDataValidator:
    """Tests for DataValidator class."""
    
    @pytest.fixture
    def validator(self, tmp_path):
        """Create validator with test schema."""
        schema_dir = tmp_path / 'schemas'
        schema_dir.mkdir()
        
        # Create minimal test schema
        test_schema = {
            '$schema': 'http://json-schema.org/draft-07/schema#',
            'type': 'object',
            'required': ['session_id', 'timestamp'],
            'properties': {
                'session_id': {'type': 'string'},
                'timestamp': {'type': 'string'}
            }
        }
        
        with open(schema_dir / 'scolia_schema.json', 'w') as f:
            json.dump(test_schema, f)
        
        return DataValidator(schema_dir)
    
    def test_validate_valid_data(self, validator):
        """Test validation of valid data."""
        data = {
            'session_id': 'test_123',
            'timestamp': '2024-01-01T12:00:00'
        }
        
        is_valid, errors = validator.validate(data, 'scolia')
        assert is_valid
        assert errors == []
    
    def test_validate_missing_required(self, validator):
        """Test validation with missing required field."""
        data = {
            'session_id': 'test_123'
            # Missing timestamp
        }
        
        is_valid, errors = validator.validate(data, 'scolia')
        assert not is_valid
        assert len(errors) > 0
    
    def test_validate_unknown_source(self, validator):
        """Test validation with unknown source."""
        data = {'some': 'data'}
        
        is_valid, errors = validator.validate(data, 'unknown_source')
        # Should pass since no schema exists
        assert is_valid


class TestDataAggregator:
    """Tests for DataAggregator class."""
    
    @pytest.fixture
    def aggregator_setup(self, tmp_path):
        """Setup aggregator with test data."""
        data_dir = tmp_path / 'data'
        schema_dir = tmp_path / 'schemas'
        
        # Create directories
        (data_dir / 'scolia').mkdir(parents=True)
        (data_dir / 'dart_connect').mkdir(parents=True)
        schema_dir.mkdir()
        
        # Create test scolia data
        scolia_data = {
            'session_id': 'scolia_20240101_120000',
            'timestamp': datetime.now().isoformat(),
            'data_source': 'scolia',
            'session_type': 'free_practice',
            'duration_minutes': 30,
            'metrics': {
                'total_darts': 100,
                'three_dart_average': 55.5,
                'checkout_percentage': 35.0,
                'scoring': {
                    '180s': 1,
                    '140_plus': 5,
                    '100_plus': 10
                }
            }
        }
        
        with open(data_dir / 'scolia' / 'session1.json', 'w') as f:
            json.dump(scolia_data, f)
        
        # Create test dart connect data
        dc_data = {
            'match_id': 'dc_20240101_180000',
            'timestamp': datetime.now().isoformat(),
            'data_source': 'dart_connect',
            'match_type': 'league_match',
            'result': {
                'won': True,
                'legs_won': 3,
                'legs_lost': 1
            },
            'metrics': {
                'three_dart_average': 52.0,
                'checkout_percentage': 30.0,
                'scoring': {'180s': 0}
            },
            'pressure_situations': {
                'match_darts_thrown': 2,
                'match_darts_converted': 1
            }
        }
        
        with open(data_dir / 'dart_connect' / 'match1.json', 'w') as f:
            json.dump(dc_data, f)
        
        return DataAggregator(data_dir, schema_dir)
    
    def test_aggregate_week(self, aggregator_setup):
        """Test weekly aggregation."""
        aggregated = aggregator_setup.aggregate_week()
        
        assert 'period' in aggregated
        assert 'practice_data' in aggregated
        assert 'competition_data' in aggregated
        
        # Check practice data
        practice = aggregated['practice_data']
        assert practice['sessions'] == 1
        assert practice['metrics']['average_three_dart'] == 55.5
        
        # Check competition data
        competition = aggregated['competition_data']
        assert competition['matches'] == 1
        assert competition['overall_record']['won'] == 1
    
    def test_save_aggregated(self, aggregator_setup, tmp_path):
        """Test saving aggregated data."""
        aggregated = aggregator_setup.aggregate_week()
        filepath = aggregator_setup.save_aggregated(aggregated)
        
        assert filepath.exists()
        
        with open(filepath) as f:
            loaded = json.load(f)
        
        assert loaded['practice_data']['sessions'] == 1


class TestIntegration:
    """Integration tests for the data pipeline."""
    
    def test_full_pipeline(self, tmp_path):
        """Test complete data pipeline flow."""
        # Setup directories
        data_dir = tmp_path / 'data'
        schema_dir = tmp_path / 'schemas'
        output_dir = tmp_path / 'output'
        
        for d in ['scolia', 'dart_connect', 'biomechanics', 'voice']:
            (data_dir / d).mkdir(parents=True)
        schema_dir.mkdir()
        output_dir.mkdir()
        
        # Create minimal test data
        test_session = {
            'session_id': 'scolia_test',
            'timestamp': datetime.now().isoformat(),
            'session_type': 'free_practice',
            'metrics': {'three_dart_average': 50.0}
        }
        
        with open(data_dir / 'scolia' / 'test.json', 'w') as f:
            json.dump(test_session, f)
        
        # Run pipeline
        aggregator = DataAggregator(data_dir, schema_dir, output_dir)
        result = aggregator.aggregate_week()
        
        assert result['practice_data']['sessions'] == 1
        assert result['competition_data']['matches'] == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
