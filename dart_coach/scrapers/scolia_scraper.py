"""
Scolia Web Client Scraper
=========================
Scraper for extracting practice and casual competition data from Scolia.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .base_scraper import BaseScraper


class ScoliaScraper(BaseScraper):
    """
    Scraper for Scolia Web Client.
    
    Captures practice session data including:
    - Free practice sessions
    - X01/Cricket practice games
    - CPU matches
    - Online matches against other players
    """
    
    DATA_SOURCE = "scolia"
    CONTEXT = "practice"
    
    def __init__(
        self,
        data_dir: Path,
        base_url: str = "https://web.scolia.app",
        api_endpoint: str = "https://api.scolia.app/v1",
        headless: bool = True,
        **kwargs
    ):
        """
        Initialize Scolia scraper.
        
        Args:
            data_dir: Directory to store scraped data
            base_url: Scolia web app URL
            api_endpoint: Scolia API endpoint
            headless: Run browser in headless mode
            **kwargs: Additional arguments for BaseScraper
        """
        super().__init__(base_url, data_dir, **kwargs)
        self.api_endpoint = api_endpoint
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self._user_id: Optional[str] = None
    
    def _init_browser(self):
        """Initialize Selenium browser for web scraping."""
        if self.driver is not None:
            return
        
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        self.driver.implicitly_wait(10)
    
    def _close_browser(self):
        """Close the browser instance."""
        if self.driver:
            self.driver.quit()
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
            self.logger.error("Scolia credentials not provided")
            return False
        
        try:
            self._init_browser()
            
            # Navigate to login page
            login_url = f"{self.base_url}/login"
            self.driver.get(login_url)
            
            # Wait for login form
            wait = WebDriverWait(self.driver, 15)
            
            # Enter credentials
            username_field = wait.until(
                EC.presence_of_element_located((By.NAME, "email"))
            )
            username_field.clear()
            username_field.send_keys(username)
            
            password_field = self.driver.find_element(By.NAME, "password")
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for successful login (redirect to dashboard)
            wait.until(EC.url_contains("/dashboard"))
            
            # Extract session tokens/cookies for API calls
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            # Try to get user ID from page or API
            self._extract_user_id()
            
            self._authenticated = True
            self._auth_expiry = datetime.now() + timedelta(seconds=self.session_timeout)
            self.logger.info("Successfully authenticated with Scolia")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            self._authenticated = False
            return False
    
    def _extract_user_id(self):
        """Extract user ID from the page or API."""
        try:
            # Try to get from API
            response = self.make_request("GET", "/api/user/profile")
            if response and response.json():
                self._user_id = response.json().get('id')
                return
            
            # Try to extract from page source
            page_source = self.driver.page_source
            match = re.search(r'"userId":\s*"([^"]+)"', page_source)
            if match:
                self._user_id = match.group(1)
                
        except Exception as e:
            self.logger.warning(f"Could not extract user ID: {e}")
    
    def fetch_sessions(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch all practice sessions within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of session summaries
        """
        if not self.is_authenticated():
            self.logger.error("Not authenticated. Call authenticate() first.")
            return []
        
        sessions = []
        
        try:
            # Try API first
            params = {
                'from': start_date.isoformat(),
                'to': end_date.isoformat(),
                'limit': 100
            }
            
            response = self.make_request(
                "GET",
                f"{self.api_endpoint}/sessions",
                params=params
            )
            
            if response and response.status_code == 200:
                data = response.json()
                sessions = data.get('sessions', [])
                self.logger.info(f"Fetched {len(sessions)} sessions from API")
                
            else:
                # Fallback to web scraping
                sessions = self._scrape_sessions_from_web(start_date, end_date)
                
        except Exception as e:
            self.logger.error(f"Error fetching sessions: {e}")
            # Try web scraping as fallback
            sessions = self._scrape_sessions_from_web(start_date, end_date)
        
        return sessions
    
    def _scrape_sessions_from_web(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Scrape session data directly from the web interface.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of session summaries
        """
        sessions = []
        
        try:
            self._init_browser()
            
            # Navigate to history/statistics page
            history_url = f"{self.base_url}/history"
            self.driver.get(history_url)
            
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "session-list")))
            
            # Parse session list
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            session_elements = soup.find_all(class_='session-item')
            
            for elem in session_elements:
                try:
                    session_data = self._parse_session_element(elem)
                    if session_data:
                        session_date = datetime.fromisoformat(session_data.get('timestamp', ''))
                        if start_date <= session_date <= end_date:
                            sessions.append(session_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing session element: {e}")
                    continue
            
            self.logger.info(f"Scraped {len(sessions)} sessions from web")
            
        except Exception as e:
            self.logger.error(f"Error scraping sessions: {e}")
        
        return sessions
    
    def _parse_session_element(self, elem) -> Optional[Dict[str, Any]]:
        """Parse a session element from the web page."""
        try:
            session_id = elem.get('data-session-id', '')
            
            # Extract basic info
            date_elem = elem.find(class_='session-date')
            type_elem = elem.find(class_='session-type')
            avg_elem = elem.find(class_='session-average')
            
            return {
                'session_id': session_id,
                'timestamp': date_elem.text.strip() if date_elem else '',
                'session_type': type_elem.text.strip() if type_elem else '',
                'average': float(avg_elem.text.strip()) if avg_elem else 0,
            }
        except Exception as e:
            self.logger.warning(f"Error parsing session element: {e}")
            return None
    
    def fetch_session_details(self, session_id: str) -> Dict[str, Any]:
        """
        Fetch detailed data for a specific session.
        
        Args:
            session_id: Scolia session ID
            
        Returns:
            Detailed session data
        """
        if not self.is_authenticated():
            self.logger.error("Not authenticated. Call authenticate() first.")
            return {}
        
        try:
            # Try API first
            response = self.make_request(
                "GET",
                f"{self.api_endpoint}/sessions/{session_id}"
            )
            
            if response and response.status_code == 200:
                return response.json()
            
            # Fallback to web scraping
            return self._scrape_session_details(session_id)
            
        except Exception as e:
            self.logger.error(f"Error fetching session details: {e}")
            return {}
    
    def _scrape_session_details(self, session_id: str) -> Dict[str, Any]:
        """Scrape detailed session data from web interface."""
        details = {}
        
        try:
            self._init_browser()
            
            detail_url = f"{self.base_url}/session/{session_id}"
            self.driver.get(detail_url)
            
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "session-details")))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Parse detailed statistics
            details = {
                'session_id': session_id,
                'metrics': self._extract_metrics(soup),
                'throws': self._extract_throws(soup),
                'game_info': self._extract_game_info(soup)
            }
            
        except Exception as e:
            self.logger.error(f"Error scraping session details: {e}")
        
        return details
    
    def _extract_metrics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract performance metrics from page."""
        metrics = {}
        
        metric_mappings = {
            'total-darts': 'total_darts',
            'points-per-dart': 'points_per_dart',
            'three-dart-average': 'three_dart_average',
            'first-nine': 'first_nine_average',
            'checkout-percentage': 'checkout_percentage',
            'highest-checkout': 'highest_checkout',
            '180s': '180s',
            '140-plus': '140_plus',
            '100-plus': '100_plus'
        }
        
        for css_class, metric_name in metric_mappings.items():
            elem = soup.find(class_=css_class)
            if elem:
                try:
                    value = elem.find(class_='value')
                    if value:
                        text = value.text.strip().replace('%', '').replace(',', '')
                        metrics[metric_name] = float(text) if '.' in text else int(text)
                except (ValueError, AttributeError):
                    continue
        
        return metrics
    
    def _extract_throws(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract individual throw data if available."""
        throws = []
        
        throw_elements = soup.find_all(class_='throw-record')
        for i, elem in enumerate(throw_elements):
            try:
                throw_data = {
                    'throw_number': i + 1,
                    'score': int(elem.find(class_='throw-score').text.strip()),
                    'target': elem.get('data-target', ''),
                    'hit': elem.get('data-hit', '')
                }
                throws.append(throw_data)
            except (ValueError, AttributeError):
                continue
        
        return throws
    
    def _extract_game_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract game format and match information."""
        game_info = {}
        
        # Game type
        game_type_elem = soup.find(class_='game-type')
        if game_type_elem:
            game_info['game_type'] = game_type_elem.text.strip()
        
        # Match result if applicable
        result_elem = soup.find(class_='match-result')
        if result_elem:
            game_info['result'] = {
                'won': 'win' in result_elem.get('class', []),
                'legs_won': int(result_elem.get('data-legs-won', 0)),
                'legs_lost': int(result_elem.get('data-legs-lost', 0))
            }
        
        # Opponent info
        opponent_elem = soup.find(class_='opponent-info')
        if opponent_elem:
            game_info['opponent'] = {
                'name': opponent_elem.find(class_='opponent-name').text.strip()
                if opponent_elem.find(class_='opponent-name') else 'CPU',
                'type': opponent_elem.get('data-opponent-type', 'cpu')
            }
        
        return game_info
    
    def transform_to_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw Scolia data to match the schema.
        
        Args:
            raw_data: Raw data from scraping
            
        Returns:
            Data matching scolia_schema.json
        """
        session_id = raw_data.get('session_id', '')
        if not session_id.startswith('scolia_'):
            session_id = f"scolia_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Determine session type and context
        game_info = raw_data.get('game_info', {})
        session_type = self._determine_session_type(raw_data)
        context = "casual_competition" if session_type in ['cpu_match', 'online_match'] else "practice"
        
        # Transform metrics
        raw_metrics = raw_data.get('metrics', {})
        
        transformed = {
            "session_id": session_id,
            "timestamp": raw_data.get('timestamp', datetime.now().isoformat()),
            "data_source": self.DATA_SOURCE,
            "context": context,
            "session_type": session_type,
            "game_format": {
                "game_type": game_info.get('game_type', '501'),
                "legs_format": game_info.get('legs_format', ''),
                "double_out": True
            },
            "duration_minutes": raw_data.get('duration_minutes', 0),
            "metrics": {
                "total_darts": raw_metrics.get('total_darts', 0),
                "total_points": raw_metrics.get('total_points', 0),
                "points_per_dart": raw_metrics.get('points_per_dart', 0),
                "three_dart_average": raw_metrics.get('three_dart_average', 0),
                "first_nine_average": raw_metrics.get('first_nine_average', 0),
                "checkout_percentage": raw_metrics.get('checkout_percentage', 0),
                "checkout_attempts": raw_metrics.get('checkout_attempts', 0),
                "checkouts_hit": raw_metrics.get('checkouts_hit', 0),
                "highest_checkout": raw_metrics.get('highest_checkout', 0),
                "doubles": {
                    "attempts": raw_metrics.get('doubles_attempts', 0),
                    "hits": raw_metrics.get('doubles_hits', 0),
                    "percentage": raw_metrics.get('doubles_percentage', 0)
                },
                "triples": {
                    "attempts": raw_metrics.get('triples_attempts', 0),
                    "hits": raw_metrics.get('triples_hits', 0),
                    "percentage": raw_metrics.get('triples_percentage', 0)
                },
                "scoring": {
                    "180s": raw_metrics.get('180s', 0),
                    "140_plus": raw_metrics.get('140_plus', 0),
                    "100_plus": raw_metrics.get('100_plus', 0),
                    "60_plus": raw_metrics.get('60_plus', 0),
                    "sub_40": raw_metrics.get('sub_40', 0)
                }
            },
            "throw_data": raw_data.get('throws', []),
            "notes": raw_data.get('notes', '')
        }
        
        # Add match result if applicable
        result = game_info.get('result')
        if result:
            opponent = game_info.get('opponent', {})
            transformed["match_result"] = {
                "won": result.get('won', False),
                "legs_won": result.get('legs_won', 0),
                "legs_lost": result.get('legs_lost', 0),
                "opponent_type": opponent.get('type', 'cpu'),
                "opponent_name": opponent.get('name', ''),
                "opponent_average": opponent.get('average', 0)
            }
        
        return transformed
    
    def _determine_session_type(self, raw_data: Dict[str, Any]) -> str:
        """Determine the session type from raw data."""
        game_info = raw_data.get('game_info', {})
        session_type = raw_data.get('session_type', '').lower()
        
        if 'practice' in session_type or 'free' in session_type:
            return 'free_practice'
        elif game_info.get('opponent', {}).get('type') == 'online':
            return 'online_match'
        elif game_info.get('opponent'):
            return 'cpu_match'
        elif 'x01' in session_type or '501' in session_type:
            return 'x01_practice'
        elif 'cricket' in session_type:
            return 'cricket_practice'
        
        return 'free_practice'
    
    def scrape_and_save(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Path]:
        """
        Scrape all sessions in date range and save to files.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of paths to saved files
        """
        saved_files = []
        
        sessions = self.fetch_sessions(start_date, end_date)
        
        for session_summary in sessions:
            try:
                self.rate_limit(0.5)  # Rate limit between requests
                
                session_id = session_summary.get('session_id')
                if not session_id:
                    continue
                
                # Fetch detailed data
                details = self.fetch_session_details(session_id)
                if not details:
                    continue
                
                # Merge summary and details
                full_data = {**session_summary, **details}
                
                # Transform to schema
                transformed = self.transform_to_schema(full_data)
                
                # Save to file
                filename = f"{transformed['session_id']}.json"
                filepath = self.save_data(transformed, filename)
                saved_files.append(filepath)
                
            except Exception as e:
                self.logger.error(f"Error processing session {session_summary.get('session_id')}: {e}")
                continue
        
        self.logger.info(f"Saved {len(saved_files)} session files")
        return saved_files
    
    def __del__(self):
        """Cleanup browser on deletion."""
        self._close_browser()
