"""
Unit Tests for GoDartsPro Scraper
==================================
Tests for the GoDartsPro scraper module.
"""

import unittest
import asyncio
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock, MagicMock
import tempfile
import shutil

from dart_coach.scrapers.godartspro_scraper import GoDartsProScraper
from dart_coach.scrapers.scraper_state_manager import ScraperStateManager


class TestScraperStateManager(unittest.TestCase):
    """Test cases for ScraperStateManager."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.state_file = self.test_dir / 'test_state.json'

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_initialization_new_state(self):
        """Test initialization with no existing state file."""
        state_mgr = ScraperStateManager(self.state_file)

        self.assertIsNotNone(state_mgr.state)
        self.assertIsNone(state_mgr.state['last_processed_date'])
        self.assertEqual(state_mgr.state['total_sessions_scraped'], 0)
        self.assertIn('created_at', state_mgr.state)

    def test_save_and_load_state(self):
        """Test saving and loading state."""
        # Create and save state
        state_mgr = ScraperStateManager(self.state_file)
        state_mgr.state['total_sessions_scraped'] = 42
        state_mgr.save_state()

        # Load state in new instance
        state_mgr2 = ScraperStateManager(self.state_file)
        self.assertEqual(state_mgr2.state['total_sessions_scraped'], 42)

    def test_last_processed_date(self):
        """Test getting and updating last processed date."""
        state_mgr = ScraperStateManager(self.state_file)

        # Initially None
        self.assertIsNone(state_mgr.get_last_processed_date())

        # Update date
        test_date = date(2026, 1, 15)
        state_mgr.update_last_processed_date(test_date)

        # Verify update
        self.assertEqual(state_mgr.get_last_processed_date(), test_date)

    def test_only_updates_with_newer_date(self):
        """Test that last_processed_date only updates with newer dates."""
        state_mgr = ScraperStateManager(self.state_file)

        # Set initial date
        initial_date = date(2026, 1, 15)
        state_mgr.update_last_processed_date(initial_date)

        # Try to update with older date
        older_date = date(2026, 1, 10)
        state_mgr.update_last_processed_date(older_date)

        # Should still be initial date
        self.assertEqual(state_mgr.get_last_processed_date(), initial_date)

        # Update with newer date
        newer_date = date(2026, 1, 20)
        state_mgr.update_last_processed_date(newer_date)

        # Should be updated
        self.assertEqual(state_mgr.get_last_processed_date(), newer_date)

    def test_record_scrape_session(self):
        """Test recording scrape sessions."""
        state_mgr = ScraperStateManager(self.state_file)

        # Record successful session
        state_mgr.record_scrape_session(5, success=True)

        self.assertEqual(state_mgr.state['total_sessions_scraped'], 5)
        self.assertEqual(len(state_mgr.state['scrape_history']), 1)
        self.assertTrue(state_mgr.state['scrape_history'][0]['success'])

        # Record another session
        state_mgr.record_scrape_session(3, success=True)

        self.assertEqual(state_mgr.state['total_sessions_scraped'], 8)
        self.assertEqual(len(state_mgr.state['scrape_history']), 2)

    def test_record_failed_session(self):
        """Test recording failed scrape sessions."""
        state_mgr = ScraperStateManager(self.state_file)

        # Record failed session
        state_mgr.record_scrape_session(0, success=False, error_message="Test error")

        # Total should not increase
        self.assertEqual(state_mgr.state['total_sessions_scraped'], 0)

        # History should record failure
        self.assertEqual(len(state_mgr.state['scrape_history']), 1)
        self.assertFalse(state_mgr.state['scrape_history'][0]['success'])
        self.assertEqual(state_mgr.state['scrape_history'][0]['error_message'], "Test error")

    def test_scrape_statistics(self):
        """Test getting scrape statistics."""
        state_mgr = ScraperStateManager(self.state_file)

        # Record some sessions
        state_mgr.record_scrape_session(5, success=True)
        state_mgr.record_scrape_session(3, success=True)
        state_mgr.record_scrape_session(0, success=False, error_message="Error")

        stats = state_mgr.get_scrape_statistics()

        self.assertEqual(stats['total_sessions_scraped'], 8)
        self.assertEqual(stats['total_scrape_runs'], 3)
        self.assertEqual(stats['successful_runs'], 2)
        self.assertEqual(stats['failed_runs'], 1)
        self.assertAlmostEqual(stats['success_rate'], 66.67, places=1)

    def test_metadata(self):
        """Test metadata storage."""
        state_mgr = ScraperStateManager(self.state_file)

        # Set metadata
        state_mgr.set_metadata('test_key', 'test_value')
        state_mgr.set_metadata('count', 42)

        # Get metadata
        self.assertEqual(state_mgr.get_metadata('test_key'), 'test_value')
        self.assertEqual(state_mgr.get_metadata('count'), 42)
        self.assertIsNone(state_mgr.get_metadata('missing_key'))
        self.assertEqual(state_mgr.get_metadata('missing_key', 'default'), 'default')

    def test_reset_state(self):
        """Test resetting state."""
        state_mgr = ScraperStateManager(self.state_file)

        # Set some data
        state_mgr.record_scrape_session(10, success=True)
        state_mgr.update_last_processed_date(date(2026, 1, 15))

        # Reset
        state_mgr.reset_state()

        # Verify reset
        self.assertEqual(state_mgr.state['total_sessions_scraped'], 0)
        self.assertIsNone(state_mgr.state['last_processed_date'])
        self.assertEqual(len(state_mgr.state['scrape_history']), 0)

    def test_context_manager(self):
        """Test using state manager as context manager."""
        with ScraperStateManager(self.state_file) as state_mgr:
            state_mgr.record_scrape_session(5, success=True)

        # State should be saved after context exit
        state_mgr2 = ScraperStateManager(self.state_file)
        self.assertEqual(state_mgr2.state['total_sessions_scraped'], 5)


class TestGoDartsProScraper(unittest.TestCase):
    """Test cases for GoDartsProScraper."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config = {
            'base_url': 'https://godartspro.com',
            'rate_limit_seconds': 0.1,
            'retry_attempts': 2,
            'retry_delay': 1,
            'browser': {
                'headless': True,
                'timeout': 5000,
                'viewport': {'width': 1920, 'height': 1080}
            },
            'selectors': {
                'login_username': '#username',
                'login_password': '#password',
                'login_submit': 'button[type="submit"]',
                'dashboard_stats': '.dashboard-stats',
                'training_log': '.training-log',
                'drill_entry': '.drill-entry',
                'your_stats_ribbon': '.stats-ribbon',
                'session_date': '.session-date',
                'stats_table': '.stats-table'
            },
            'state_management': {
                'enabled': True,
                'state_file': 'test_state.json'
            }
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    def test_initialization(self):
        """Test scraper initialization."""
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        self.assertEqual(scraper.username, 'test_user')
        self.assertEqual(scraper.password, 'test_pass')
        self.assertEqual(scraper.config, self.config)
        self.assertIsNotNone(scraper.state_manager)

    def test_generate_session_id(self):
        """Test session ID generation."""
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        session_id = scraper._generate_session_id()

        self.assertTrue(session_id.startswith('godartspro_'))
        self.assertIn('_', session_id)

    def test_parse_date(self):
        """Test date parsing."""
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        # Test various date formats
        test_cases = [
            ('2026-01-15', date(2026, 1, 15)),
            ('01/15/2026', date(2026, 1, 15)),
            ('15/01/2026', date(2026, 1, 15)),
            ('January 15, 2026', date(2026, 1, 15)),
            ('Jan 15, 2026', date(2026, 1, 15)),
        ]

        for date_str, expected in test_cases:
            result = scraper._parse_date(date_str)
            self.assertEqual(result, expected, f"Failed to parse: {date_str}")

        # Test invalid date
        self.assertIsNone(scraper._parse_date('invalid'))
        self.assertIsNone(scraper._parse_date(''))

    def test_filter_entries_by_date(self):
        """Test filtering drill entries by date range."""
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        # Create test entries
        entries = [
            {'date': date(2026, 1, 10), 'name': 'drill1'},
            {'date': date(2026, 1, 15), 'name': 'drill2'},
            {'date': date(2026, 1, 20), 'name': 'drill3'},
            {'date': date(2026, 1, 25), 'name': 'drill4'},
            {'date': None, 'name': 'drill5'},  # No date
        ]

        # Filter by date range
        filtered = scraper._filter_entries_by_date(
            entries,
            start_date=date(2026, 1, 15),
            end_date=date(2026, 1, 20)
        )

        self.assertEqual(len(filtered), 3)  # drill2, drill3, drill5 (no date)
        self.assertEqual(filtered[0]['name'], 'drill2')
        self.assertEqual(filtered[1]['name'], 'drill3')
        self.assertEqual(filtered[2]['name'], 'drill5')

    def test_filter_entries_no_start_date(self):
        """Test filtering with no start date."""
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        entries = [
            {'date': date(2026, 1, 10), 'name': 'drill1'},
            {'date': date(2026, 1, 20), 'name': 'drill2'},
        ]

        filtered = scraper._filter_entries_by_date(
            entries,
            start_date=None,
            end_date=date(2026, 1, 15)
        )

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]['name'], 'drill1')

    def test_save_results(self):
        """Test saving results to file."""
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        # Add test data
        scraper.scraped_data = [
            {
                'session_id': 'test_1',
                'data_source': 'godartspro',
                'timestamp': '2026-01-15T10:00:00'
            },
            {
                'session_id': 'test_2',
                'data_source': 'godartspro',
                'timestamp': '2026-01-16T10:00:00'
            }
        ]

        # Save results
        result_file = scraper.save_results('test_output.json')

        # Verify file exists and contains data
        self.assertTrue(result_file.exists())

        with open(result_file, 'r') as f:
            loaded_data = json.load(f)

        self.assertEqual(len(loaded_data), 2)
        self.assertEqual(loaded_data[0]['session_id'], 'test_1')
        self.assertEqual(loaded_data[1]['session_id'], 'test_2')


class TestGoDartsProScraperIntegration(unittest.TestCase):
    """Integration tests for GoDartsPro scraper (requires mocking Playwright)."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config = {
            'base_url': 'https://godartspro.com',
            'rate_limit_seconds': 0,
            'browser': {
                'headless': True,
                'timeout': 5000
            },
            'selectors': {
                'login_username': '#username',
                'login_password': '#password',
                'login_submit': 'button[type="submit"]'
            },
            'state_management': {
                'state_file': 'test_state.json'
            }
        }

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir)

    @patch('dart_coach.scrapers.godartspro_scraper.async_playwright')
    async def test_scraper_lifecycle(self, mock_playwright):
        """Test full scraper lifecycle with mocked browser."""
        # Mock Playwright components
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_instance = AsyncMock()

        mock_playwright.return_value.__aenter__.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        # Create scraper
        scraper = GoDartsProScraper(
            username='test_user',
            password='test_pass',
            config=self.config,
            data_dir=self.test_dir
        )

        # Test initialization and cleanup
        await scraper.initialize_browser()
        self.assertIsNotNone(scraper.page)

        await scraper.close_browser()
        mock_browser.close.assert_called_once()


def run_async_test(coro):
    """Helper to run async tests."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coro)


if __name__ == '__main__':
    unittest.main()
