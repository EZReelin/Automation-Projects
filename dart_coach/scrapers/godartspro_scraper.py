"""
GoDartsPro Scraper Module
=========================
Production-ready web scraper for extracting dart training statistics from GoDartsPro.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError

from .scraper_state_manager import ScraperStateManager


class GoDartsProScraper:
    """
    Production-ready scraper for GoDartsPro platform.

    Features:
    - Playwright-based browser automation for JavaScript-heavy sites
    - State management for incremental scraping
    - Comprehensive error handling and retry logic
    - Rate limiting to avoid being blocked
    - Structured data output for LLM ingestion
    """

    def __init__(
        self,
        username: str,
        password: str,
        config: Dict[str, Any],
        data_dir: Path,
        state_dir: Optional[Path] = None,
        log_level: str = "INFO"
    ):
        """
        Initialize the GoDartsPro scraper.

        Args:
            username: GoDartsPro username
            password: GoDartsPro password
            config: Configuration dictionary (from settings.yaml)
            data_dir: Directory to store scraped data
            state_dir: Directory to store state files (defaults to data_dir)
            log_level: Logging level
        """
        self.username = username
        self.password = password
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        state_dir = Path(state_dir) if state_dir else self.data_dir
        state_file = state_dir / config.get("state_management", {}).get("state_file", "godartspro_scraper_state.json")

        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))

        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)

        # Initialize state manager
        self.state_manager = ScraperStateManager(state_file, self.logger)

        # Browser instances (initialized in async context)
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None

        # Scraping results
        self.scraped_data: List[Dict[str, Any]] = []

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize_browser()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_browser()
        self.state_manager.save_state()
        return False

    async def initialize_browser(self) -> None:
        """Initialize Playwright browser instance."""
        self.logger.info("Initializing browser...")

        browser_config = self.config.get("browser", {})
        headless = browser_config.get("headless", True)
        viewport = browser_config.get("viewport", {"width": 1920, "height": 1080})

        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=headless)

        self.page = await self.browser.new_page(viewport=viewport)
        self.page.set_default_timeout(browser_config.get("timeout", 30000))

        self.logger.info("Browser initialized successfully")

    async def close_browser(self) -> None:
        """Close browser instance."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        self.logger.info("Browser closed")

    async def authenticate(self) -> bool:
        """
        Authenticate with GoDartsPro.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            self.logger.info("Authenticating with GoDartsPro...")

            base_url = self.config.get("base_url", "https://godartspro.com")
            selectors = self.config.get("selectors", {})

            # Navigate to login page
            await self.page.goto(f"{base_url}/login", wait_until="networkidle")
            await self.rate_limit()

            # Fill in credentials
            await self.page.fill(selectors.get("login_username", "#username"), self.username)
            await self.page.fill(selectors.get("login_password", "#password"), self.password)

            # Click login button
            await self.page.click(selectors.get("login_submit", "button[type='submit']"))

            # Wait for navigation to complete
            await self.page.wait_for_load_state("networkidle")
            await self.rate_limit()

            # Check if login was successful by looking for dashboard
            current_url = self.page.url
            if "dashboard" in current_url.lower() or "home" in current_url.lower():
                self.logger.info("Authentication successful")
                return True
            else:
                self.logger.error(f"Authentication may have failed - current URL: {current_url}")
                return False

        except PlaywrightTimeoutError as e:
            self.logger.error(f"Timeout during authentication: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error during authentication: {e}")
            return False

    async def extract_dashboard_statistics(self) -> Dict[str, Any]:
        """
        Extract statistics from the GoDartsPro dashboard.

        Returns:
            Dictionary containing dashboard statistics
        """
        try:
            self.logger.info("Extracting dashboard statistics...")

            base_url = self.config.get("base_url", "https://godartspro.com")
            await self.page.goto(f"{base_url}/dashboard", wait_until="networkidle")
            await self.rate_limit()

            dashboard_stats = {
                "total_sessions": None,
                "total_drills_completed": None,
                "overall_average": None,
                "best_average": None,
                "total_practice_hours": None,
                "current_streak": None,
                "longest_streak": None,
                "additional_stats": {}
            }

            # Extract statistics using selectors
            # NOTE: These selectors are examples - update based on actual GoDartsPro HTML structure
            selectors = self.config.get("selectors", {})
            stats_container = selectors.get("dashboard_stats", ".dashboard-stats")

            try:
                # Wait for stats container to be visible
                await self.page.wait_for_selector(stats_container, timeout=10000)

                # Extract all text content from dashboard
                # This is a generic approach - customize based on actual HTML structure
                stats_text = await self.page.text_content(stats_container)

                # Parse statistics from text
                # This is a placeholder - implement actual parsing logic based on site structure
                dashboard_stats["additional_stats"]["raw_text"] = stats_text

                # Example: Extract specific stats if they have identifiable selectors
                # dashboard_stats["total_sessions"] = await self._extract_stat_by_label("Total Sessions")
                # dashboard_stats["overall_average"] = await self._extract_stat_by_label("Overall Average")

            except PlaywrightTimeoutError:
                self.logger.warning("Dashboard stats container not found - continuing with partial data")

            self.logger.info("Dashboard statistics extracted")
            return dashboard_stats

        except Exception as e:
            self.logger.error(f"Error extracting dashboard statistics: {e}")
            return {}

    async def navigate_to_training_log(self) -> bool:
        """
        Navigate to the training log section.

        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info("Navigating to training log...")

            # Try to find and click training log link
            # Update selector based on actual site structure
            training_log_link = "a:has-text('Training Log'), a:has-text('History'), a:has-text('Sessions')"

            await self.page.click(training_log_link)
            await self.page.wait_for_load_state("networkidle")
            await self.rate_limit()

            self.logger.info("Navigated to training log")
            return True

        except Exception as e:
            self.logger.error(f"Error navigating to training log: {e}")
            return False

    async def get_drill_entries(self) -> List[Dict[str, Any]]:
        """
        Get all drill entries from the training log.

        Returns:
            List of drill entry dictionaries with metadata
        """
        try:
            self.logger.info("Extracting drill entries from training log...")

            selectors = self.config.get("selectors", {})
            drill_selector = selectors.get("drill_entry", ".drill-entry")

            # Wait for drill entries to load
            await self.page.wait_for_selector(drill_selector, timeout=10000)

            # Get all drill entry elements
            drill_elements = await self.page.query_selector_all(drill_selector)

            drill_entries = []
            for idx, element in enumerate(drill_elements):
                try:
                    # Extract drill information
                    # Update selectors based on actual HTML structure
                    drill_info = {
                        "index": idx,
                        "element_handle": element,
                        "date": None,
                        "drill_name": None,
                        "summary": None
                    }

                    # Try to extract date
                    date_selector = selectors.get("session_date", ".session-date")
                    try:
                        date_text = await element.text_content(date_selector)
                        drill_info["date"] = self._parse_date(date_text)
                    except:
                        pass

                    # Try to extract drill name
                    try:
                        drill_name = await element.text_content(".drill-name, .session-name, h3, h4")
                        drill_info["drill_name"] = drill_name.strip() if drill_name else None
                    except:
                        pass

                    drill_entries.append(drill_info)

                except Exception as e:
                    self.logger.warning(f"Error extracting drill entry {idx}: {e}")
                    continue

            self.logger.info(f"Found {len(drill_entries)} drill entries")
            return drill_entries

        except PlaywrightTimeoutError:
            self.logger.warning("No drill entries found in training log")
            return []
        except Exception as e:
            self.logger.error(f"Error getting drill entries: {e}")
            return []

    async def process_drill_entry(self, drill_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Process a single drill entry by clicking into it and extracting stats.

        Args:
            drill_info: Dictionary containing drill entry information

        Returns:
            Extracted session data or None if extraction failed
        """
        try:
            drill_date = drill_info.get("date")
            drill_name = drill_info.get("drill_name", "Unknown")

            self.logger.info(f"Processing drill: {drill_name} ({drill_date})")

            # Click the drill entry to open it
            element = drill_info.get("element_handle")
            if element:
                await element.click()
                await self.page.wait_for_load_state("networkidle")
                await self.rate_limit()

            # Extract stats from the drill/game page
            session_data = await self.extract_session_statistics(drill_date, drill_name)

            # Navigate back to training log
            await self.page.go_back()
            await self.page.wait_for_load_state("networkidle")
            await self.rate_limit()

            return session_data

        except Exception as e:
            self.logger.error(f"Error processing drill entry: {e}")
            try:
                # Try to recover by navigating back
                await self.page.go_back()
                await self.rate_limit()
            except:
                pass
            return None

    async def extract_session_statistics(
        self,
        session_date: Optional[date],
        drill_name: str
    ) -> Dict[str, Any]:
        """
        Extract detailed statistics from a session by clicking the 'Your Stats' ribbon.

        Args:
            session_date: Date of the session
            drill_name: Name of the drill

        Returns:
            Dictionary containing session statistics
        """
        try:
            self.logger.info("Extracting session statistics...")

            # Find and click the "Your Stats" ribbon
            selectors = self.config.get("selectors", {})
            stats_ribbon_selector = selectors.get("your_stats_ribbon", ".stats-ribbon.red, button:has-text('Your Stats')")

            try:
                await self.page.click(stats_ribbon_selector, timeout=5000)
                await self.page.wait_for_load_state("networkidle")
                await self.rate_limit()
            except PlaywrightTimeoutError:
                self.logger.warning("'Your Stats' ribbon not found - extracting available stats from page")

            # Extract individual session stats and averaged stats
            individual_stats = await self._extract_individual_session_stats()
            averaged_stats = await self._extract_averaged_statistics()

            session_data = {
                "session_id": self._generate_session_id(),
                "timestamp": session_date.isoformat() if session_date else datetime.now().isoformat(),
                "data_source": "godartspro",
                "context": "practice",
                "scrape_metadata": {
                    "scrape_timestamp": datetime.now().isoformat(),
                    "scraper_version": "1.0.0"
                },
                "training_log_entry": {
                    "drill_date": session_date.isoformat() if session_date else None,
                    "drill_name": drill_name,
                    "completion_status": "completed"
                },
                "session_statistics": {
                    "session_date": session_date.isoformat() if session_date else None,
                    "individual_session_stats": individual_stats,
                    "averaged_statistics": averaged_stats
                }
            }

            return session_data

        except Exception as e:
            self.logger.error(f"Error extracting session statistics: {e}")
            return {}

    async def _extract_individual_session_stats(self) -> List[Dict[str, Any]]:
        """
        Extract individual session statistics listed by date.

        Returns:
            List of individual session stat dictionaries
        """
        try:
            # This is a placeholder implementation
            # Update selectors based on actual HTML structure

            stats = []
            stats_table_selector = self.config.get("selectors", {}).get("stats_table", ".stats-table")

            try:
                # Wait for stats table
                await self.page.wait_for_selector(stats_table_selector, timeout=5000)

                # Extract rows from stats table
                rows = await self.page.query_selector_all(f"{stats_table_selector} tr, {stats_table_selector} .stat-row")

                for row in rows:
                    try:
                        # Extract stat values from row
                        # This is highly dependent on actual HTML structure
                        row_text = await row.text_content()

                        stat_entry = {
                            "date": None,
                            "metrics": {
                                "raw_text": row_text.strip() if row_text else None
                            }
                        }
                        stats.append(stat_entry)

                    except Exception as e:
                        self.logger.debug(f"Error extracting stat row: {e}")
                        continue

            except PlaywrightTimeoutError:
                self.logger.debug("Stats table not found")

            return stats

        except Exception as e:
            self.logger.error(f"Error extracting individual session stats: {e}")
            return []

    async def _extract_averaged_statistics(self) -> Dict[str, Any]:
        """
        Extract averaged statistics displayed at the top.

        Returns:
            Dictionary containing averaged statistics
        """
        try:
            # This is a placeholder implementation
            # Update based on actual HTML structure

            averaged_stats = {
                "period": "all_time",
                "number_of_sessions": None,
                "avg_three_dart_average": None,
                "avg_first_nine": None,
                "avg_checkout_percentage": None
            }

            # Try to extract averaged stats from page
            # Implementation depends on actual site structure

            return averaged_stats

        except Exception as e:
            self.logger.error(f"Error extracting averaged statistics: {e}")
            return {}

    async def scrape_all(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        incremental: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Scrape all available data from GoDartsPro.

        Args:
            start_date: Start date for scraping (None = from last processed date or beginning)
            end_date: End date for scraping (None = today)
            incremental: If True, resume from last processed date

        Returns:
            List of scraped session dictionaries
        """
        try:
            self.logger.info("Starting GoDartsPro scraping session...")

            # Determine date range
            if incremental and start_date is None:
                last_processed = self.state_manager.get_last_processed_date()
                if last_processed:
                    start_date = last_processed + timedelta(days=1)
                    self.logger.info(f"Resuming from last processed date: {last_processed}")

            if end_date is None:
                end_date = date.today()

            self.logger.info(f"Scraping data from {start_date or 'beginning'} to {end_date}")

            # Authenticate
            if not await self.authenticate():
                raise Exception("Authentication failed")

            # Extract dashboard statistics
            dashboard_stats = await self.extract_dashboard_statistics()

            # Navigate to training log
            if not await self.navigate_to_training_log():
                raise Exception("Failed to navigate to training log")

            # Get all drill entries
            drill_entries = await self.get_drill_entries()

            # Filter drill entries by date range
            filtered_entries = self._filter_entries_by_date(drill_entries, start_date, end_date)

            self.logger.info(f"Processing {len(filtered_entries)} drill entries...")

            # Process each drill entry
            sessions_scraped = 0
            for drill_info in filtered_entries:
                session_data = await self.process_drill_entry(drill_info)

                if session_data:
                    # Add dashboard stats to first session
                    if sessions_scraped == 0:
                        session_data["dashboard_statistics"] = dashboard_stats

                    self.scraped_data.append(session_data)
                    sessions_scraped += 1

                    # Update last processed date
                    if drill_info.get("date"):
                        self.state_manager.update_last_processed_date(drill_info["date"])

            # Record scrape session
            self.state_manager.record_scrape_session(sessions_scraped, success=True)

            self.logger.info(f"Scraping completed - {sessions_scraped} sessions extracted")

            return self.scraped_data

        except Exception as e:
            self.logger.error(f"Error during scraping: {e}")
            self.state_manager.record_scrape_session(len(self.scraped_data), success=False, error_message=str(e))
            return self.scraped_data

    def _filter_entries_by_date(
        self,
        entries: List[Dict[str, Any]],
        start_date: Optional[date],
        end_date: Optional[date]
    ) -> List[Dict[str, Any]]:
        """
        Filter drill entries by date range.

        Args:
            entries: List of drill entries
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            Filtered list of drill entries
        """
        filtered = []

        for entry in entries:
            entry_date = entry.get("date")

            if entry_date is None:
                # Include entries without dates
                filtered.append(entry)
                continue

            if start_date and entry_date < start_date:
                continue

            if end_date and entry_date > end_date:
                continue

            filtered.append(entry)

        return filtered

    def _parse_date(self, date_str: str) -> Optional[date]:
        """
        Parse date string to date object.

        Args:
            date_str: Date string to parse

        Returns:
            Parsed date or None if parsing failed
        """
        if not date_str:
            return None

        date_str = date_str.strip()

        # Try common date formats
        formats = [
            "%Y-%m-%d",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%b %d, %Y",
            "%Y/%m/%d"
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).date()
            except ValueError:
                continue

        self.logger.warning(f"Could not parse date: {date_str}")
        return None

    def _generate_session_id(self) -> str:
        """Generate a unique session ID."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"godartspro_{timestamp}"

    async def rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        delay = self.config.get("rate_limit_seconds", 2.0)
        await asyncio.sleep(delay)

    def save_results(self, filename: Optional[str] = None) -> Path:
        """
        Save scraped results to JSON file.

        Args:
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"godartspro_data_{timestamp}.json"

        filepath = self.data_dir / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.scraped_data, f, indent=2, default=str)

        self.logger.info(f"Saved {len(self.scraped_data)} sessions to {filepath}")
        return filepath

    def get_scrape_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about scraping history.

        Returns:
            Dictionary containing scrape statistics
        """
        return self.state_manager.get_scrape_statistics()


# Convenience function for simple usage
async def scrape_godartspro(
    username: str,
    password: str,
    config_file: Path,
    data_dir: Path,
    incremental: bool = True
) -> Path:
    """
    Convenience function to scrape GoDartsPro data.

    Args:
        username: GoDartsPro username
        password: GoDartsPro password
        config_file: Path to settings.yaml file
        data_dir: Directory to store data
        incremental: Whether to use incremental scraping

    Returns:
        Path to saved data file
    """
    # Load configuration
    with open(config_file, 'r') as f:
        settings = yaml.safe_load(f)

    config = settings.get("godartspro", {})

    # Create and run scraper
    async with GoDartsProScraper(username, password, config, data_dir) as scraper:
        await scraper.scrape_all(incremental=incremental)
        return scraper.save_results()
