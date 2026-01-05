"""
Tests for the analysis module.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from dart_coach.analysis.prompts import AnalysisPrompts
from dart_coach.analysis.ollama_analyzer import OllamaAnalyzer
from dart_coach.analysis.report_generator import ReportGenerator


class TestAnalysisPrompts:
    """Tests for AnalysisPrompts class."""
    
    def test_get_system_prompt(self):
        """Test getting system prompt."""
        prompt = AnalysisPrompts.get_prompt('system')
        assert 'dart coach' in prompt.lower()
        assert len(prompt) > 100
    
    def test_get_weekly_summary_prompt(self):
        """Test getting weekly summary prompt template."""
        prompt = AnalysisPrompts.get_prompt('weekly_summary')
        assert '{practice_summary}' in prompt
        assert '{competition_summary}' in prompt
    
    def test_get_unknown_prompt(self):
        """Test getting unknown prompt returns empty string."""
        prompt = AnalysisPrompts.get_prompt('nonexistent')
        assert prompt == ''


class TestOllamaAnalyzer:
    """Tests for OllamaAnalyzer class."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return OllamaAnalyzer(
            base_url='http://localhost:11434',
            model='llama3.1:8b'
        )
    
    @pytest.fixture
    def sample_aggregated_data(self):
        """Sample aggregated data for testing."""
        return {
            'period': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-07',
                'week_number': 1
            },
            'practice_data': {
                'sessions': 5,
                'total_darts': 500,
                'total_duration_minutes': 150,
                'metrics': {
                    'average_ppd': 15.5,
                    'average_three_dart': 46.5,
                    'best_three_dart': 60.0,
                    'average_checkout_pct': 32.0,
                    'total_180s': 2,
                    'total_140_plus': 10,
                    'total_100_plus': 25
                },
                'match_results': {
                    'cpu_matches': {'played': 3, 'won': 2},
                    'online_matches': {'played': 2, 'won': 1}
                }
            },
            'competition_data': {
                'matches': 2,
                'league_matches': 2,
                'overall_record': {'won': 1, 'lost': 1, 'legs_won': 5, 'legs_lost': 4},
                'metrics': {
                    'average_ppd': 14.0,
                    'average_three_dart': 42.0,
                    'average_checkout_pct': 28.0,
                    'total_180s': 0
                },
                'pressure_performance': {
                    'match_darts_conversion': 50.0,
                    'deciding_legs_won': 1
                }
            },
            'biomechanics_data': {
                'sessions': 2,
                'total_throws_analyzed': 50,
                'average_quality_score': 75.0,
                'average_consistency_score': 70.0,
                'deviation_summary': [
                    {'type': 'elbow_drop', 'count': 5, 'percentage': 10.0}
                ],
                'improvement_trends': {'overall': 'stable'}
            },
            'observations_data': {
                'sessions': 3,
                'total_observations': 15,
                'sentiment_breakdown': {'positive': 8, 'neutral': 5, 'negative': 2},
                'key_themes': ['focus', 'grip', 'rhythm'],
                'top_keywords': [{'keyword': 'focus', 'count': 5}],
                'action_items': ['Work on follow-through']
            }
        }
    
    def test_format_practice_summary(self, analyzer, sample_aggregated_data):
        """Test practice summary formatting."""
        summary = analyzer._format_practice_summary(
            sample_aggregated_data['practice_data']
        )
        
        assert 'Sessions: 5' in summary
        assert '46.5' in summary  # average
        assert '32.0' in summary  # checkout
    
    def test_format_empty_practice(self, analyzer):
        """Test formatting empty practice data."""
        summary = analyzer._format_practice_summary({})
        assert 'No practice data' in summary
    
    def test_format_competition_summary(self, analyzer, sample_aggregated_data):
        """Test competition summary formatting."""
        summary = analyzer._format_competition_summary(
            sample_aggregated_data['competition_data']
        )
        
        assert 'Total Matches: 2' in summary
        assert '1-1' in summary  # record
    
    def test_identify_improvement_areas(self, analyzer, sample_aggregated_data):
        """Test improvement area identification."""
        areas = analyzer._identify_improvement_areas(sample_aggregated_data)
        
        # Should identify practice-to-competition gap
        assert 'gap' in areas.lower() or len(areas) > 0
    
    @patch('requests.post')
    def test_call_ollama_success(self, mock_post, analyzer):
        """Test successful Ollama API call."""
        mock_response = Mock()
        mock_response.json.return_value = {'response': 'Test analysis response'}
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        result = analyzer._call_ollama('Test prompt')
        
        assert result == 'Test analysis response'
        mock_post.assert_called_once()
    
    @patch('requests.post')
    def test_call_ollama_connection_error(self, mock_post, analyzer):
        """Test Ollama connection error handling."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        result = analyzer._call_ollama('Test prompt')
        
        assert result == ''
    
    @patch('requests.get')
    def test_check_connection_success(self, mock_get, analyzer):
        """Test connection check success."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        assert analyzer.check_connection() is True
    
    @patch('requests.get')
    def test_check_connection_failure(self, mock_get, analyzer):
        """Test connection check failure."""
        mock_get.side_effect = Exception('Connection failed')
        
        assert analyzer.check_connection() is False


class TestReportGenerator:
    """Tests for ReportGenerator class."""
    
    @pytest.fixture
    def report_generator(self, tmp_path):
        """Create report generator instance."""
        data_dir = tmp_path / 'data'
        data_dir.mkdir()
        
        return ReportGenerator(
            data_dir=data_dir,
            output_dir=tmp_path / 'reports'
        )
    
    @pytest.fixture
    def sample_aggregated_data(self):
        """Sample aggregated data for testing."""
        return {
            'period': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-07',
                'week_number': 1
            },
            'data_sources_included': {
                'scolia': 5,
                'dart_connect': 2,
                'biomechanics': 2,
                'voice_observation': 3
            },
            'practice_data': {
                'sessions': 5,
                'total_darts': 500,
                'total_duration_minutes': 150,
                'metrics': {
                    'average_three_dart': 46.5,
                    'average_checkout_pct': 32.0,
                    'total_180s': 2
                },
                'match_results': {
                    'cpu_matches': {'played': 3, 'won': 2},
                    'online_matches': {'played': 2, 'won': 1}
                }
            },
            'competition_data': {
                'matches': 2,
                'overall_record': {'won': 1, 'lost': 1, 'legs_won': 5, 'legs_lost': 4},
                'metrics': {
                    'average_three_dart': 42.0,
                    'average_checkout_pct': 28.0,
                    'total_180s': 0
                },
                'pressure_performance': {
                    'match_darts_conversion': 50.0
                }
            },
            'biomechanics_data': {
                'sessions': 2,
                'average_consistency_score': 70.0,
                'deviation_summary': [],
                'improvement_trends': {'overall': 'stable'}
            },
            'observations_data': {
                'sessions': 3,
                'total_observations': 15,
                'sentiment_breakdown': {'positive': 8, 'neutral': 5, 'negative': 2},
                'key_themes': ['focus'],
                'top_keywords': [],
                'action_items': []
            },
            'raw_file_references': {}
        }
    
    def test_build_practice_summary(self, report_generator, sample_aggregated_data):
        """Test building practice summary."""
        summary = report_generator._build_practice_summary(
            sample_aggregated_data['practice_data']
        )
        
        assert summary['sessions_count'] == 5
        assert summary['total_darts_thrown'] == 500
        assert summary['metrics']['average_three_dart'] == 46.5
    
    def test_build_competition_summary(self, report_generator, sample_aggregated_data):
        """Test building competition summary."""
        summary = report_generator._build_competition_summary(
            sample_aggregated_data['competition_data']
        )
        
        assert summary['total_matches'] == 2
        assert summary['matches_won'] == 1
        assert summary['win_rate'] == 50.0
    
    def test_build_comparison(self, report_generator, sample_aggregated_data):
        """Test building practice vs competition comparison."""
        comparison = report_generator._build_comparison(
            sample_aggregated_data['practice_data'],
            sample_aggregated_data['competition_data']
        )
        
        assert comparison['average_difference'] == 4.5  # 46.5 - 42.0
        assert len(comparison['insights']) > 0
    
    @patch.object(OllamaAnalyzer, 'check_connection', return_value=False)
    def test_generate_basic_analysis(self, mock_check, report_generator, sample_aggregated_data):
        """Test generating basic analysis without Ollama."""
        analysis = report_generator._generate_basic_analysis(
            sample_aggregated_data,
            None
        )
        
        assert 'executive_summary' in analysis
        assert 'AI analysis unavailable' in analysis['executive_summary']
    
    def test_report_to_markdown(self, report_generator):
        """Test converting report to markdown."""
        report = {
            'report_id': 'test_report',
            'generated_at': '2024-01-07T18:00:00',
            'week_period': {
                'start_date': '2024-01-01',
                'end_date': '2024-01-07'
            },
            'analysis': {
                'executive_summary': 'Test summary',
                'key_findings': [
                    {'finding': 'Test finding', 'category': 'observation'}
                ],
                'recommendations': [],
                'goals_for_next_week': []
            },
            'practice_summary': {
                'sessions_count': 5,
                'total_practice_time_minutes': 150,
                'total_darts_thrown': 500,
                'metrics': {
                    'average_three_dart': 46.5,
                    'average_checkout_pct': 32.0,
                    'total_180s': 2
                }
            },
            'competition_summary': {
                'total_matches': 2,
                'matches_won': 1,
                'matches_lost': 1,
                'win_rate': 50.0,
                'metrics': {
                    'average_three_dart': 42.0,
                    'average_checkout_pct': 28.0
                }
            }
        }
        
        markdown = report_generator._report_to_markdown(report)
        
        assert '# Dart Performance Weekly Analysis' in markdown
        assert 'Test summary' in markdown
        assert '46.5' in markdown
    
    def test_save_report_json(self, report_generator, sample_aggregated_data):
        """Test saving report as JSON."""
        report = {
            'report_id': 'test_report',
            'generated_at': datetime.now().isoformat(),
            'week_period': sample_aggregated_data['period'],
            'analysis': {'executive_summary': 'Test'}
        }
        
        filepath = report_generator.save_report(report, format='json')
        
        assert filepath.exists()
        assert filepath.suffix == '.json'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
