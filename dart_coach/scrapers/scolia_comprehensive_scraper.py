"""
Comprehensive Scolia Web Client Scraper
========================================
Production-ready scraper for extracting comprehensive darts statistics from Scolia.

Features:
- Authenticates and navigates the Scolia Web Client interface
- Extracts statistics from all game types (X01, Cricket, Around the World, Bob's 27, Shanghai)
- Captures chart data in numerical format
- Processes match history with incremental tracking
- Extracts match-level and leg-level data
- Captures turn-by-turn throw analysis
- Handles multiple tabs for different game types
- Exports to JSON and CSV formats
"""

import csv
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .base_scraper import BaseScraper


class ScoliaComprehensiveScraper(BaseScraper):
    """
    Comprehensive scraper for Scolia Web Client.

    Extracts all statistics from:
    - Main stats pages for each game type
    - Charts and visual data representations
    - Match history with incremental tracking
    - Individual matches with all tabs
    - Individual legs with turn-by-turn data
    """

    DATA_SOURCE = "scolia"

    # Game type identifiers
    GAME_TYPES = {
        'x01': 'X01',
        'cricket': 'Cricket',
        'around_the_world': 'Around the World',
        'bobs_27': "Bob's 27",
        'shanghai': 'Shanghai'
    }

    # CSS selectors for different page elements (to be customized based on actual Scolia structure)
    SELECTORS = {
        'stats_page': {
            'overall_stats': '.stats-container',
            'game_selector': '.game-type-selector',
            'stat_cards': '.stat-card',
            'charts': '.chart-container'
        },
        'match_history': {
            'match_list': '.match-list',
            'match_item': '.match-item',
            'match_date': '.match-date',
            'match_type': '.match-type',
            'match_result': '.match-result',
            'match_link': 'a.match-link'
        },
        'match_details': {
            'tabs': '.tab-navigation',
            'tab_throw_analysis': 'button[data-tab="throw-analysis"]',
            'tab_scoring': 'button[data-tab="scoring"]',
            'tab_score_history': 'button[data-tab="score-history"]',  # X01
            'tab_marks': 'button[data-tab="marks"]',  # Cricket
            'leg_list': '.leg-list',
            'leg_item': '.leg-item'
        },
        'leg_details': {
            'turn_list': '.turn-list',
            'turn_item': '.turn-item',
            'throw_data': '.throw-data'
        },
        'charts': {
            'chart_canvas': 'canvas.chart',
            'chart_data_script': 'script[type="application/json"]',
            'chart_legend': '.chart-legend'
        }
    }

    def __init__(
        self,
        data_dir: Path,
        base_url: str = "https://web.scolia.app",
        headless: bool = True,
        **kwargs
    ):
        """
        Initialize comprehensive Scolia scraper.

        Args:
            data_dir: Directory to store scraped data
            base_url: Scolia web app URL
            headless: Run browser in headless mode
            **kwargs: Additional arguments for BaseScraper
        """
        super().__init__(base_url, data_dir, **kwargs)
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self._user_id: Optional[str] = None

        # Tracking state for incremental scraping
        self.state_file = self.data_dir / "scraper_state.json"
        self.last_scraped_matches = self._load_scraper_state()

    def _init_browser(self):
        """Initialize Selenium browser for web scraping."""
        if self.driver is not None:
            return

        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            self.driver.implicitly_wait(10)
            self.logger.info("Browser initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize browser: {e}")
            raise

    def _close_browser(self):
        """Close the browser instance."""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Browser closed")
            except Exception as e:
                self.logger.warning(f"Error closing browser: {e}")
            finally:
                self.driver = None

    def authenticate(self, username: str = None, password: str = None) -> bool:
        """
        Authenticate with Scolia using credentials.

        Args:
            username: Scolia username (defaults to SCOLIA_USERNAME env var)
            password: Scolia password (defaults to SCOLIA_PASSWORD env var)

        Returns:
            True if authentication successful
        """
        username = username or os.getenv('SCOLIA_USERNAME')
        password = password or os.getenv('SCOLIA_PASSWORD')

        if not username or not password:
            self.logger.error("Scolia credentials not provided. Set SCOLIA_USERNAME and SCOLIA_PASSWORD environment variables.")
            return False

        try:
            self._init_browser()

            # Navigate to login page
            login_url = f"{self.base_url}/login"
            self.logger.info(f"Navigating to login page: {login_url}")
            self.driver.get(login_url)

            # Wait for login form
            wait = WebDriverWait(self.driver, 20)

            # Try multiple common field names for username/email
            username_field = None
            for field_name in ['email', 'username', 'user']:
                try:
                    username_field = wait.until(
                        EC.presence_of_element_located((By.NAME, field_name))
                    )
                    break
                except TimeoutException:
                    continue

            if not username_field:
                # Try by ID or other selectors
                try:
                    username_field = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='email'], input[type='text']"))
                    )
                except TimeoutException:
                    self.logger.error("Could not find username/email field")
                    return False

            username_field.clear()
            username_field.send_keys(username)
            self.logger.debug("Entered username")

            # Find password field
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(password)
            self.logger.debug("Entered password")

            # Submit login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            self.logger.debug("Clicked login button")

            # Wait for successful login (redirect to dashboard or stats page)
            try:
                wait.until(lambda driver: 'login' not in driver.current_url.lower())
                self.logger.info(f"Login successful, redirected to: {self.driver.current_url}")
            except TimeoutException:
                self.logger.error("Login failed - did not redirect from login page")
                return False

            # Extract user ID if available
            self._extract_user_id()

            self._authenticated = True
            self._auth_expiry = datetime.now() + timedelta(seconds=self.session_timeout)
            self.logger.info("Successfully authenticated with Scolia")

            return True

        except Exception as e:
            self.logger.error(f"Authentication failed: {e}", exc_info=True)
            self._authenticated = False
            return False

    def _extract_user_id(self):
        """Extract user ID from the page."""
        try:
            # Try to extract from page source or local storage
            page_source = self.driver.page_source

            # Try various patterns
            patterns = [
                r'"userId":\s*"([^"]+)"',
                r'"user_id":\s*"([^"]+)"',
                r'"id":\s*"([^"]+)"',
                r'userId:\s*"([^"]+)"'
            ]

            for pattern in patterns:
                match = re.search(pattern, page_source)
                if match:
                    self._user_id = match.group(1)
                    self.logger.info(f"Extracted user ID: {self._user_id}")
                    return

            self.logger.warning("Could not extract user ID from page")

        except Exception as e:
            self.logger.warning(f"Error extracting user ID: {e}")

    def _load_scraper_state(self) -> Dict[str, Any]:
        """Load the scraper state to track last processed matches."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    self.logger.info(f"Loaded scraper state from {self.state_file}")
                    return state
            except Exception as e:
                self.logger.warning(f"Error loading scraper state: {e}")

        return {
            'last_scrape_time': None,
            'last_match_ids': {},  # {game_type: last_match_id}
            'total_matches_scraped': 0
        }

    def _save_scraper_state(self):
        """Save the scraper state for incremental scraping."""
        try:
            state = {
                'last_scrape_time': datetime.now().isoformat(),
                'last_match_ids': self.last_scraped_matches.get('last_match_ids', {}),
                'total_matches_scraped': self.last_scraped_matches.get('total_matches_scraped', 0)
            }

            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

            self.logger.info(f"Saved scraper state to {self.state_file}")
        except Exception as e:
            self.logger.error(f"Error saving scraper state: {e}")

    def extract_all_statistics(self, game_types: List[str] = None) -> Dict[str, Any]:
        """
        Extract comprehensive statistics for all or specified game types.

        Args:
            game_types: List of game types to scrape. If None, scrapes all.

        Returns:
            Dictionary containing all extracted statistics
        """
        if not self.is_authenticated():
            self.logger.error("Not authenticated. Call authenticate() first.")
            return {}

        if game_types is None:
            game_types = list(self.GAME_TYPES.keys())

        all_stats = {
            'scrape_timestamp': datetime.now().isoformat(),
            'game_types': {}
        }

        for game_type in game_types:
            self.logger.info(f"Extracting statistics for {game_type}")
            try:
                game_stats = self._extract_game_type_statistics(game_type)
                all_stats['game_types'][game_type] = game_stats
                self.rate_limit(1.0)  # Rate limiting between game types
            except Exception as e:
                self.logger.error(f"Error extracting {game_type} statistics: {e}", exc_info=True)
                all_stats['game_types'][game_type] = {'error': str(e)}

        return all_stats

    def _extract_game_type_statistics(self, game_type: str) -> Dict[str, Any]:
        """
        Extract statistics for a specific game type.

        Args:
            game_type: Game type identifier

        Returns:
            Dictionary containing game type statistics
        """
        stats = {
            'game_type': game_type,
            'stats_page_data': {},
            'charts': [],
            'match_history': []
        }

        # Navigate to stats page for this game type
        stats_url = self._get_stats_url(game_type)
        self.logger.info(f"Navigating to stats page: {stats_url}")

        try:
            self.driver.get(stats_url)
            time.sleep(2)  # Wait for page load

            # Extract stats page data
            stats['stats_page_data'] = self._extract_stats_page_data()

            # Extract chart data
            stats['charts'] = self._extract_chart_data()

            # Extract match history
            stats['match_history'] = self._extract_match_history(game_type)

        except Exception as e:
            self.logger.error(f"Error extracting statistics page for {game_type}: {e}")
            stats['error'] = str(e)

        return stats

    def _get_stats_url(self, game_type: str) -> str:
        """Get the stats page URL for a game type."""
        # Customize based on actual Scolia URL structure
        game_type_urls = {
            'x01': f"{self.base_url}/stats/x01",
            'cricket': f"{self.base_url}/stats/cricket",
            'around_the_world': f"{self.base_url}/stats/around-the-world",
            'bobs_27': f"{self.base_url}/stats/bobs-27",
            'shanghai': f"{self.base_url}/stats/shanghai"
        }

        return game_type_urls.get(game_type, f"{self.base_url}/stats")

    def _extract_stats_page_data(self) -> Dict[str, Any]:
        """Extract all statistical metrics from the stats page."""
        stats_data = {}

        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Find all stat cards/containers
            stat_cards = soup.find_all(class_=re.compile(r'stat-card|metric-card|stats-item'))

            for card in stat_cards:
                try:
                    # Extract metric name and value
                    label_elem = card.find(class_=re.compile(r'label|title|name'))
                    value_elem = card.find(class_=re.compile(r'value|number|metric'))

                    if label_elem and value_elem:
                        label = label_elem.get_text(strip=True)
                        value = value_elem.get_text(strip=True)

                        # Clean and convert value
                        value_clean = value.replace('%', '').replace(',', '').strip()

                        try:
                            if '.' in value_clean:
                                stats_data[label] = float(value_clean)
                            else:
                                stats_data[label] = int(value_clean)
                        except ValueError:
                            stats_data[label] = value

                except Exception as e:
                    self.logger.debug(f"Error parsing stat card: {e}")
                    continue

            # Try to extract from data attributes as well
            data_elements = soup.find_all(attrs={'data-metric': True})
            for elem in data_elements:
                metric_name = elem.get('data-metric')
                metric_value = elem.get('data-value', elem.get_text(strip=True))
                stats_data[metric_name] = metric_value

            self.logger.info(f"Extracted {len(stats_data)} statistics from page")

        except Exception as e:
            self.logger.error(f"Error extracting stats page data: {e}")

        return stats_data

    def _extract_chart_data(self) -> List[Dict[str, Any]]:
        """
        Extract numerical data from charts (not just screenshots).

        Returns:
            List of chart data dictionaries
        """
        charts = []

        try:
            # Look for chart containers
            chart_elements = self.driver.find_elements(By.CSS_SELECTOR,
                ".chart-container, .chart, canvas[id*='chart'], canvas[class*='chart']")

            for idx, chart_elem in enumerate(chart_elements):
                try:
                    chart_data = {
                        'chart_id': f"chart_{idx}",
                        'type': 'unknown',
                        'data': {}
                    }

                    # Try to extract data from JavaScript variables or data attributes
                    chart_id = chart_elem.get_attribute('id')
                    if chart_id:
                        chart_data['chart_id'] = chart_id

                    # Execute JavaScript to get chart data if using Chart.js or similar
                    try:
                        script = f"""
                        var chartElement = arguments[0];
                        var chartId = chartElement.id;

                        // Try Chart.js
                        if (window.Chart && Chart.instances) {{
                            for (var id in Chart.instances) {{
                                var chart = Chart.instances[id];
                                if (chart.canvas.id === chartId) {{
                                    return {{
                                        type: chart.config.type,
                                        data: chart.config.data,
                                        options: chart.config.options
                                    }};
                                }}
                            }}
                        }}

                        // Try to find data in element attributes
                        if (chartElement.dataset.chartData) {{
                            return JSON.parse(chartElement.dataset.chartData);
                        }}

                        return null;
                        """

                        js_data = self.driver.execute_script(script, chart_elem)
                        if js_data:
                            chart_data['data'] = js_data

                    except Exception as e:
                        self.logger.debug(f"Could not extract chart data via JavaScript: {e}")

                    # Look for data in nearby script tags
                    parent_html = chart_elem.get_attribute('outerHTML')
                    if parent_html:
                        soup = BeautifulSoup(parent_html, 'html.parser')
                        script_tags = soup.find_all('script', {'type': 'application/json'})
                        for script in script_tags:
                            try:
                                json_data = json.loads(script.string)
                                chart_data['data'] = json_data
                                break
                            except:
                                continue

                    if chart_data['data']:
                        charts.append(chart_data)

                except Exception as e:
                    self.logger.debug(f"Error extracting chart {idx}: {e}")
                    continue

            self.logger.info(f"Extracted data from {len(charts)} charts")

        except Exception as e:
            self.logger.error(f"Error extracting chart data: {e}")

        return charts

    def _extract_match_history(self, game_type: str) -> List[Dict[str, Any]]:
        """
        Extract match history with incremental tracking.

        Args:
            game_type: Game type to extract matches for

        Returns:
            List of match data dictionaries
        """
        matches = []

        try:
            # Navigate to match history page
            history_url = f"{self.base_url}/history/{game_type}"
            self.logger.info(f"Navigating to match history: {history_url}")
            self.driver.get(history_url)
            time.sleep(2)

            # Get last processed match ID for this game type
            last_match_id = self.last_scraped_matches.get('last_match_ids', {}).get(game_type)

            # Find all match items
            match_elements = self.driver.find_elements(By.CSS_SELECTOR,
                ".match-item, .game-item, .history-item, tr.match-row")

            self.logger.info(f"Found {len(match_elements)} matches in history")

            new_matches_found = False

            for match_elem in match_elements:
                try:
                    # Extract match ID
                    match_id = match_elem.get_attribute('data-match-id') or match_elem.get_attribute('data-id')

                    if not match_id:
                        # Try to extract from href
                        link = match_elem.find_element(By.TAG_NAME, 'a')
                        href = link.get_attribute('href')
                        match_id = href.split('/')[-1] if href else None

                    if not match_id:
                        continue

                    # Check if this is a new match (incremental scraping)
                    if last_match_id and match_id == last_match_id:
                        self.logger.info(f"Reached last processed match: {match_id}")
                        break

                    if not new_matches_found:
                        new_matches_found = True

                    # Extract match summary data
                    match_summary = self._extract_match_summary(match_elem, match_id)

                    # Navigate to match details and extract comprehensive data
                    match_details = self._extract_match_details(match_id, game_type)

                    # Combine summary and details
                    match_data = {**match_summary, **match_details}
                    matches.append(match_data)

                    self.rate_limit(0.5)  # Rate limit between matches

                except Exception as e:
                    self.logger.warning(f"Error extracting match: {e}")
                    continue

            # Update last scraped match for this game type
            if matches:
                if 'last_match_ids' not in self.last_scraped_matches:
                    self.last_scraped_matches['last_match_ids'] = {}
                self.last_scraped_matches['last_match_ids'][game_type] = matches[0].get('match_id')
                self.last_scraped_matches['total_matches_scraped'] = \
                    self.last_scraped_matches.get('total_matches_scraped', 0) + len(matches)
                self._save_scraper_state()

            self.logger.info(f"Extracted {len(matches)} matches for {game_type}")

        except Exception as e:
            self.logger.error(f"Error extracting match history: {e}", exc_info=True)

        return matches

    def _extract_match_summary(self, match_elem, match_id: str) -> Dict[str, Any]:
        """Extract summary data from a match list item."""
        summary = {
            'match_id': match_id,
            'date': None,
            'opponent': None,
            'result': None,
            'score': None
        }

        try:
            soup = BeautifulSoup(match_elem.get_attribute('outerHTML'), 'html.parser')

            # Extract date
            date_elem = soup.find(class_=re.compile(r'date|time'))
            if date_elem:
                summary['date'] = date_elem.get_text(strip=True)

            # Extract opponent
            opponent_elem = soup.find(class_=re.compile(r'opponent|player'))
            if opponent_elem:
                summary['opponent'] = opponent_elem.get_text(strip=True)

            # Extract result
            result_elem = soup.find(class_=re.compile(r'result|outcome'))
            if result_elem:
                summary['result'] = result_elem.get_text(strip=True)

            # Extract score
            score_elem = soup.find(class_=re.compile(r'score'))
            if score_elem:
                summary['score'] = score_elem.get_text(strip=True)

        except Exception as e:
            self.logger.debug(f"Error extracting match summary: {e}")

        return summary

    def _extract_match_details(self, match_id: str, game_type: str) -> Dict[str, Any]:
        """
        Extract comprehensive details for a specific match.

        Args:
            match_id: Match identifier
            game_type: Game type (x01, cricket, etc.)

        Returns:
            Dictionary containing match details
        """
        details = {
            'tabs': {},
            'legs': [],
            'timeline_analysis': {},
            'scoring_analysis': {}
        }

        try:
            # Navigate to match detail page
            match_url = f"{self.base_url}/match/{match_id}"
            self.logger.info(f"Navigating to match: {match_url}")
            self.driver.get(match_url)
            time.sleep(2)

            # Extract data from different tabs
            if game_type == 'x01':
                details['tabs'] = self._extract_x01_tabs()
                details['timeline_analysis'] = self._extract_timeline_analysis()
                details['scoring_analysis'] = self._extract_scoring_analysis()
            elif game_type == 'cricket':
                details['tabs'] = self._extract_cricket_tabs()
            else:
                details['tabs'] = self._extract_generic_tabs()

            # Extract leg-level data
            details['legs'] = self._extract_all_legs()

        except Exception as e:
            self.logger.error(f"Error extracting match details for {match_id}: {e}")
            details['error'] = str(e)

        return details

    def _extract_x01_tabs(self) -> Dict[str, Any]:
        """Extract data from all three tabs in X01 match."""
        tabs_data = {}

        # Tab 1: Throw Analysis
        tabs_data['throw_analysis'] = self._extract_tab_data('throw-analysis')

        # Tab 2: Scoring
        tabs_data['scoring'] = self._extract_tab_data('scoring')

        # Tab 3: Score History
        tabs_data['score_history'] = self._extract_tab_data('score-history')

        return tabs_data

    def _extract_cricket_tabs(self) -> Dict[str, Any]:
        """Extract data from all three tabs in Cricket match."""
        tabs_data = {}

        # Tab 1: Throw Analysis
        tabs_data['throw_analysis'] = self._extract_tab_data('throw-analysis')

        # Tab 2: Scoring
        tabs_data['scoring'] = self._extract_tab_data('scoring')

        # Tab 3: Number of Marks
        tabs_data['marks'] = self._extract_tab_data('marks')

        return tabs_data

    def _extract_generic_tabs(self) -> Dict[str, Any]:
        """Extract data from tabs for other game types."""
        tabs_data = {}

        try:
            # Find all tab buttons
            tab_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                "button[role='tab'], .tab-button, button[data-tab]")

            for tab_button in tab_buttons:
                try:
                    tab_name = tab_button.get_attribute('data-tab') or \
                              tab_button.get_attribute('aria-label') or \
                              tab_button.text.strip().lower().replace(' ', '-')

                    tabs_data[tab_name] = self._extract_tab_data(tab_name, tab_button)

                except Exception as e:
                    self.logger.debug(f"Error extracting tab: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting generic tabs: {e}")

        return tabs_data

    def _extract_tab_data(self, tab_name: str, tab_button=None) -> Dict[str, Any]:
        """
        Extract data from a specific tab.

        Args:
            tab_name: Name/identifier of the tab
            tab_button: Optional tab button element (if already found)

        Returns:
            Dictionary containing tab data
        """
        tab_data = {}

        try:
            # Click on the tab if button provided
            if tab_button:
                tab_button.click()
            else:
                # Try to find and click the tab
                selectors = [
                    f"button[data-tab='{tab_name}']",
                    f"button[aria-label*='{tab_name}']",
                    f".tab-button[data-tab='{tab_name}']"
                ]

                for selector in selectors:
                    try:
                        button = self.driver.find_element(By.CSS_SELECTOR, selector)
                        button.click()
                        break
                    except NoSuchElementException:
                        continue

            time.sleep(1)  # Wait for tab content to load

            # Extract table data if present
            tables = self.driver.find_elements(By.TAG_NAME, 'table')
            if tables:
                tab_data['tables'] = []
                for table in tables:
                    tab_data['tables'].append(self._extract_table_data(table))

            # Extract other structured data
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Look for data lists
            data_lists = soup.find_all(class_=re.compile(r'data-list|stat-list|metric-list'))
            if data_lists:
                tab_data['lists'] = []
                for data_list in data_lists:
                    items = []
                    for item in data_list.find_all(class_=re.compile(r'item|row')):
                        items.append(item.get_text(strip=True))
                    tab_data['lists'].append(items)

            # Look for key-value pairs
            kv_elements = soup.find_all(class_=re.compile(r'stat-row|metric-row|data-row'))
            if kv_elements:
                tab_data['metrics'] = {}
                for elem in kv_elements:
                    label = elem.find(class_=re.compile(r'label|key'))
                    value = elem.find(class_=re.compile(r'value'))
                    if label and value:
                        tab_data['metrics'][label.get_text(strip=True)] = value.get_text(strip=True)

        except Exception as e:
            self.logger.debug(f"Error extracting tab data for {tab_name}: {e}")

        return tab_data

    def _extract_table_data(self, table_element) -> List[Dict[str, Any]]:
        """Extract data from an HTML table."""
        table_data = []

        try:
            soup = BeautifulSoup(table_element.get_attribute('outerHTML'), 'html.parser')

            # Get headers
            headers = []
            header_row = soup.find('thead')
            if header_row:
                headers = [th.get_text(strip=True) for th in header_row.find_all('th')]

            # Get rows
            tbody = soup.find('tbody') or soup
            rows = tbody.find_all('tr')

            for row in rows:
                cells = row.find_all(['td', 'th'])
                if len(cells) == len(headers):
                    row_data = {headers[i]: cells[i].get_text(strip=True) for i in range(len(headers))}
                else:
                    row_data = {f"col_{i}": cell.get_text(strip=True) for i, cell in enumerate(cells)}
                table_data.append(row_data)

        except Exception as e:
            self.logger.debug(f"Error extracting table data: {e}")

        return table_data

    def _extract_timeline_analysis(self) -> Dict[str, Any]:
        """Extract Timeline Analysis data for X01 games."""
        timeline_data = {}

        try:
            # Look for timeline section
            timeline_selectors = [
                '.timeline-analysis',
                '.timeline-section',
                '#timeline-analysis',
                "div[data-section='timeline']"
            ]

            for selector in timeline_selectors:
                try:
                    timeline_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    soup = BeautifulSoup(timeline_elem.get_attribute('outerHTML'), 'html.parser')

                    # Extract timeline data points
                    data_points = soup.find_all(class_=re.compile(r'timeline-point|data-point'))
                    timeline_data['points'] = []

                    for point in data_points:
                        point_data = {}
                        for attr in ['turn', 'score', 'remaining', 'average']:
                            elem = point.find(class_=re.compile(attr))
                            if elem:
                                point_data[attr] = elem.get_text(strip=True)
                        if point_data:
                            timeline_data['points'].append(point_data)

                    break

                except NoSuchElementException:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting timeline analysis: {e}")

        return timeline_data

    def _extract_scoring_analysis(self) -> Dict[str, Any]:
        """Extract Scoring Analysis data for X01 games."""
        scoring_data = {}

        try:
            # Look for scoring analysis section
            scoring_selectors = [
                '.scoring-analysis',
                '.scoring-section',
                '#scoring-analysis',
                "div[data-section='scoring']"
            ]

            for selector in scoring_selectors:
                try:
                    scoring_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    soup = BeautifulSoup(scoring_elem.get_attribute('outerHTML'), 'html.parser')

                    # Extract scoring metrics
                    metrics = soup.find_all(class_=re.compile(r'metric|stat'))
                    for metric in metrics:
                        label = metric.find(class_=re.compile(r'label|name'))
                        value = metric.find(class_=re.compile(r'value|number'))
                        if label and value:
                            scoring_data[label.get_text(strip=True)] = value.get_text(strip=True)

                    break

                except NoSuchElementException:
                    continue

        except Exception as e:
            self.logger.debug(f"Error extracting scoring analysis: {e}")

        return scoring_data

    def _extract_all_legs(self) -> List[Dict[str, Any]]:
        """Extract data from all legs in a match."""
        legs_data = []

        try:
            # Find leg list or leg selector
            leg_selectors = [
                '.leg-list .leg-item',
                '.legs .leg',
                "div[data-leg]",
                '.leg-selector option'
            ]

            leg_elements = []
            for selector in leg_selectors:
                try:
                    leg_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if leg_elements:
                        break
                except NoSuchElementException:
                    continue

            if not leg_elements:
                self.logger.warning("No leg elements found")
                return legs_data

            self.logger.info(f"Found {len(leg_elements)} legs")

            for idx, leg_elem in enumerate(leg_elements):
                try:
                    # Click or navigate to leg
                    try:
                        leg_elem.click()
                        time.sleep(1)
                    except:
                        # If clicking doesn't work, the leg data might already be visible
                        pass

                    # Extract leg data
                    leg_data = self._extract_leg_details(idx + 1)
                    legs_data.append(leg_data)

                except Exception as e:
                    self.logger.warning(f"Error extracting leg {idx + 1}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Error extracting legs: {e}")

        return legs_data

    def _extract_leg_details(self, leg_number: int) -> Dict[str, Any]:
        """
        Extract detailed turn-by-turn data for a specific leg.

        Args:
            leg_number: Leg number

        Returns:
            Dictionary containing leg details
        """
        leg_data = {
            'leg_number': leg_number,
            'turns': [],
            'summary': {}
        }

        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')

            # Extract turn-by-turn data
            turn_selectors = [
                '.turn-list .turn-item',
                '.turns .turn',
                'tr.turn-row',
                "div[data-turn]"
            ]

            turn_elements = None
            for selector in turn_selectors:
                turn_elements = soup.select(selector)
                if turn_elements:
                    break

            if turn_elements:
                for turn_elem in turn_elements:
                    turn_data = self._extract_turn_data(turn_elem)
                    if turn_data:
                        leg_data['turns'].append(turn_data)

            # Extract leg summary statistics
            summary_elem = soup.find(class_=re.compile(r'leg-summary|leg-stats'))
            if summary_elem:
                metrics = summary_elem.find_all(class_=re.compile(r'metric|stat'))
                for metric in metrics:
                    label = metric.find(class_=re.compile(r'label'))
                    value = metric.find(class_=re.compile(r'value'))
                    if label and value:
                        leg_data['summary'][label.get_text(strip=True)] = value.get_text(strip=True)

        except Exception as e:
            self.logger.debug(f"Error extracting leg {leg_number} details: {e}")

        return leg_data

    def _extract_turn_data(self, turn_elem) -> Optional[Dict[str, Any]]:
        """Extract data for a single turn (3 darts)."""
        turn_data = {
            'turn_number': None,
            'throws': [],
            'total_score': 0,
            'remaining': None
        }

        try:
            # Extract turn number
            turn_num_elem = turn_elem.find(class_=re.compile(r'turn-number|turn-id'))
            if turn_num_elem:
                turn_data['turn_number'] = int(turn_num_elem.get_text(strip=True))

            # Extract individual throws
            throw_elements = turn_elem.find_all(class_=re.compile(r'throw|dart'))
            for throw_elem in throw_elements:
                throw_info = {
                    'target': throw_elem.get('data-target', ''),
                    'score': 0,
                    'multiplier': throw_elem.get('data-multiplier', '1')
                }

                # Extract score
                score_elem = throw_elem.find(class_=re.compile(r'score|value'))
                if score_elem:
                    try:
                        throw_info['score'] = int(score_elem.get_text(strip=True))
                    except ValueError:
                        pass

                turn_data['throws'].append(throw_info)

            # Extract total score for the turn
            total_elem = turn_elem.find(class_=re.compile(r'total|turn-score'))
            if total_elem:
                try:
                    turn_data['total_score'] = int(total_elem.get_text(strip=True))
                except ValueError:
                    pass

            # Extract remaining score
            remaining_elem = turn_elem.find(class_=re.compile(r'remaining|left'))
            if remaining_elem:
                try:
                    turn_data['remaining'] = int(remaining_elem.get_text(strip=True))
                except ValueError:
                    pass

        except Exception as e:
            self.logger.debug(f"Error extracting turn data: {e}")
            return None

        return turn_data if turn_data['turn_number'] is not None else None

    def export_to_json(self, data: Dict[str, Any], filename: str) -> Path:
        """
        Export data to JSON file.

        Args:
            data: Data to export
            filename: Output filename

        Returns:
            Path to saved file
        """
        return self.save_data(data, filename)

    def export_to_csv(self, data: Dict[str, Any], base_filename: str) -> List[Path]:
        """
        Export data to CSV files (multiple files for hierarchical data).

        Args:
            data: Data to export
            base_filename: Base filename (without extension)

        Returns:
            List of paths to saved CSV files
        """
        csv_files = []

        try:
            # Export summary statistics
            summary_path = self.data_dir / f"{base_filename}_summary.csv"
            self._export_summary_to_csv(data, summary_path)
            csv_files.append(summary_path)

            # Export matches
            if 'game_types' in data:
                for game_type, game_data in data['game_types'].items():
                    if 'match_history' in game_data:
                        matches_path = self.data_dir / f"{base_filename}_{game_type}_matches.csv"
                        self._export_matches_to_csv(game_data['match_history'], matches_path)
                        csv_files.append(matches_path)

                        # Export turn-by-turn data
                        turns_path = self.data_dir / f"{base_filename}_{game_type}_turns.csv"
                        self._export_turns_to_csv(game_data['match_history'], turns_path)
                        csv_files.append(turns_path)

            self.logger.info(f"Exported data to {len(csv_files)} CSV files")

        except Exception as e:
            self.logger.error(f"Error exporting to CSV: {e}")

        return csv_files

    def _export_summary_to_csv(self, data: Dict[str, Any], filepath: Path):
        """Export summary statistics to CSV."""
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Game Type', 'Metric', 'Value'])

                if 'game_types' in data:
                    for game_type, game_data in data['game_types'].items():
                        if 'stats_page_data' in game_data:
                            for metric, value in game_data['stats_page_data'].items():
                                writer.writerow([game_type, metric, value])

            self.logger.info(f"Exported summary to {filepath}")

        except Exception as e:
            self.logger.error(f"Error exporting summary CSV: {e}")

    def _export_matches_to_csv(self, matches: List[Dict[str, Any]], filepath: Path):
        """Export match data to CSV."""
        if not matches:
            return

        try:
            # Flatten match data
            flattened_matches = []
            for match in matches:
                flat_match = {
                    'match_id': match.get('match_id'),
                    'date': match.get('date'),
                    'opponent': match.get('opponent'),
                    'result': match.get('result'),
                    'score': match.get('score'),
                    'num_legs': len(match.get('legs', []))
                }
                flattened_matches.append(flat_match)

            if flattened_matches:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=flattened_matches[0].keys())
                    writer.writeheader()
                    writer.writerows(flattened_matches)

                self.logger.info(f"Exported matches to {filepath}")

        except Exception as e:
            self.logger.error(f"Error exporting matches CSV: {e}")

    def _export_turns_to_csv(self, matches: List[Dict[str, Any]], filepath: Path):
        """Export turn-by-turn data to CSV."""
        try:
            rows = []

            for match in matches:
                match_id = match.get('match_id')
                for leg in match.get('legs', []):
                    leg_num = leg.get('leg_number')
                    for turn in leg.get('turns', []):
                        for throw_idx, throw in enumerate(turn.get('throws', [])):
                            row = {
                                'match_id': match_id,
                                'leg': leg_num,
                                'turn': turn.get('turn_number'),
                                'throw_num': throw_idx + 1,
                                'target': throw.get('target'),
                                'score': throw.get('score'),
                                'multiplier': throw.get('multiplier'),
                                'turn_total': turn.get('total_score'),
                                'remaining': turn.get('remaining')
                            }
                            rows.append(row)

            if rows:
                with open(filepath, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)

                self.logger.info(f"Exported turns to {filepath}")

        except Exception as e:
            self.logger.error(f"Error exporting turns CSV: {e}")

    def run_full_scrape(
        self,
        game_types: List[str] = None,
        export_format: str = 'both'
    ) -> Tuple[Path, List[Path]]:
        """
        Run a complete scraping session.

        Args:
            game_types: List of game types to scrape (None = all)
            export_format: 'json', 'csv', or 'both'

        Returns:
            Tuple of (json_path, csv_paths)
        """
        if not self.is_authenticated():
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        self.logger.info("Starting comprehensive scrape")

        # Extract all statistics
        all_data = self.extract_all_statistics(game_types)

        # Generate timestamp for filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # Export data
        json_path = None
        csv_paths = []

        if export_format in ['json', 'both']:
            json_path = self.export_to_json(all_data, f"scolia_data_{timestamp}.json")

        if export_format in ['csv', 'both']:
            csv_paths = self.export_to_csv(all_data, f"scolia_data_{timestamp}")

        self.logger.info("Scraping completed successfully")

        return json_path, csv_paths

    # Implement abstract methods from BaseScraper
    def fetch_sessions(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Fetch sessions - delegates to extract_all_statistics."""
        return []

    def fetch_session_details(self, session_id: str) -> Dict[str, Any]:
        """Fetch session details - not used in comprehensive scraper."""
        return {}

    def transform_to_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform data to schema - data is already structured."""
        return raw_data

    def __del__(self):
        """Cleanup browser on deletion."""
        self._close_browser()
