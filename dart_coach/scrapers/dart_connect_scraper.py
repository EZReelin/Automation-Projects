"""
Dart Connect Scraper
====================
Scraper for extracting competitive match data from Dart Connect.
"""

import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from .base_scraper import BaseScraper


class DartConnectScraper(BaseScraper):
    """
    Scraper for Dart Connect.
    
    Captures competitive match data including:
    - League matches
    - Bar matches
    - Tournament matches
    - Playoff matches
    """
    
    DATA_SOURCE = "dart_connect"
    CONTEXT = "competition"
    
    def __init__(
        self,
        data_dir: Path,
        base_url: str = "https://dartconnect.com",
        api_endpoint: str = "https://api.dartconnect.com/v1",
        headless: bool = True,
        **kwargs
    ):
        """
        Initialize Dart Connect scraper.
        
        Args:
            data_dir: Directory to store scraped data
            base_url: Dart Connect web URL
            api_endpoint: Dart Connect API endpoint
            headless: Run browser in headless mode
            **kwargs: Additional arguments for BaseScraper
        """
        super().__init__(base_url, data_dir, **kwargs)
        self.api_endpoint = api_endpoint
        self.headless = headless
        self.driver: Optional[webdriver.Chrome] = None
        self._player_id: Optional[str] = None
    
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
        Authenticate with Dart Connect.
        
        Args:
            username: Dart Connect username (defaults to DART_CONNECT_USERNAME env var)
            password: Dart Connect password (defaults to DART_CONNECT_PASSWORD env var)
            
        Returns:
            True if authentication successful
        """
        username = username or os.getenv('DART_CONNECT_USERNAME')
        password = password or os.getenv('DART_CONNECT_PASSWORD')
        
        if not username or not password:
            self.logger.error("Dart Connect credentials not provided")
            return False
        
        try:
            self._init_browser()
            
            # Navigate to login page
            login_url = f"{self.base_url}/account/login"
            self.driver.get(login_url)
            
            wait = WebDriverWait(self.driver, 15)
            
            # Enter credentials
            username_field = wait.until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            username_field.clear()
            username_field.send_keys(username)
            
            password_field = self.driver.find_element(By.ID, "password")
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit login
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            login_button.click()
            
            # Wait for successful login
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "user-dashboard")))
            
            # Extract cookies for API calls
            cookies = self.driver.get_cookies()
            for cookie in cookies:
                self.session.cookies.set(cookie['name'], cookie['value'])
            
            # Get player ID
            self._extract_player_id()
            
            self._authenticated = True
            self._auth_expiry = datetime.now() + timedelta(seconds=self.session_timeout)
            self.logger.info("Successfully authenticated with Dart Connect")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Authentication failed: {e}")
            self._authenticated = False
            return False
    
    def _extract_player_id(self):
        """Extract player ID from page or API."""
        try:
            # Try to find player ID in page
            page_source = self.driver.page_source
            match = re.search(r'"playerId":\s*"?(\d+)"?', page_source)
            if match:
                self._player_id = match.group(1)
                return
            
            # Try API
            response = self.make_request("GET", "/api/account/profile")
            if response and response.json():
                self._player_id = str(response.json().get('id'))
                
        except Exception as e:
            self.logger.warning(f"Could not extract player ID: {e}")
    
    def fetch_sessions(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch all competitive matches within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of match summaries
        """
        if not self.is_authenticated():
            self.logger.error("Not authenticated. Call authenticate() first.")
            return []
        
        matches = []
        
        try:
            # Try API first
            params = {
                'playerId': self._player_id,
                'startDate': start_date.strftime('%Y-%m-%d'),
                'endDate': end_date.strftime('%Y-%m-%d'),
                'limit': 100
            }
            
            response = self.make_request(
                "GET",
                f"{self.api_endpoint}/matches",
                params=params
            )
            
            if response and response.status_code == 200:
                data = response.json()
                matches = data.get('matches', [])
                self.logger.info(f"Fetched {len(matches)} matches from API")
            else:
                # Fallback to web scraping
                matches = self._scrape_matches_from_web(start_date, end_date)
                
        except Exception as e:
            self.logger.error(f"Error fetching matches: {e}")
            matches = self._scrape_matches_from_web(start_date, end_date)
        
        return matches
    
    def _scrape_matches_from_web(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Scrape match data directly from the web interface.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of match summaries
        """
        matches = []
        
        try:
            self._init_browser()
            
            # Navigate to match history
            history_url = f"{self.base_url}/player/{self._player_id}/matches"
            self.driver.get(history_url)
            
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "match-list")))
            
            # Parse match list
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            match_elements = soup.find_all(class_='match-row')
            
            for elem in match_elements:
                try:
                    match_data = self._parse_match_element(elem)
                    if match_data:
                        match_date = datetime.strptime(
                            match_data.get('date', ''),
                            '%Y-%m-%d'
                        )
                        if start_date <= match_date <= end_date:
                            matches.append(match_data)
                except Exception as e:
                    self.logger.warning(f"Error parsing match element: {e}")
                    continue
            
            self.logger.info(f"Scraped {len(matches)} matches from web")
            
        except Exception as e:
            self.logger.error(f"Error scraping matches: {e}")
        
        return matches
    
    def _parse_match_element(self, elem) -> Optional[Dict[str, Any]]:
        """Parse a match element from the web page."""
        try:
            match_id = elem.get('data-match-id', '')
            
            date_elem = elem.find(class_='match-date')
            opponent_elem = elem.find(class_='opponent-name')
            result_elem = elem.find(class_='match-result')
            venue_elem = elem.find(class_='venue')
            type_elem = elem.find(class_='match-type')
            
            return {
                'match_id': match_id,
                'date': date_elem.text.strip() if date_elem else '',
                'opponent': opponent_elem.text.strip() if opponent_elem else '',
                'result': result_elem.text.strip() if result_elem else '',
                'venue': venue_elem.text.strip() if venue_elem else '',
                'match_type': type_elem.text.strip() if type_elem else 'league_match'
            }
        except Exception as e:
            self.logger.warning(f"Error parsing match element: {e}")
            return None
    
    def fetch_session_details(self, session_id: str) -> Dict[str, Any]:
        """
        Fetch detailed data for a specific match.
        
        Args:
            session_id: Dart Connect match ID
            
        Returns:
            Detailed match data
        """
        if not self.is_authenticated():
            self.logger.error("Not authenticated. Call authenticate() first.")
            return {}
        
        try:
            # Try API first
            response = self.make_request(
                "GET",
                f"{self.api_endpoint}/matches/{session_id}"
            )
            
            if response and response.status_code == 200:
                return response.json()
            
            # Fallback to web scraping
            return self._scrape_match_details(session_id)
            
        except Exception as e:
            self.logger.error(f"Error fetching match details: {e}")
            return {}
    
    def _scrape_match_details(self, match_id: str) -> Dict[str, Any]:
        """Scrape detailed match data from web interface."""
        details = {}
        
        try:
            self._init_browser()
            
            detail_url = f"{self.base_url}/match/{match_id}"
            self.driver.get(detail_url)
            
            wait = WebDriverWait(self.driver, 15)
            wait.until(EC.presence_of_element_located((By.CLASS_NAME, "match-details")))
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            details = {
                'match_id': match_id,
                'competition': self._extract_competition_info(soup),
                'opponent': self._extract_opponent_info(soup),
                'result': self._extract_result_info(soup),
                'metrics': self._extract_match_metrics(soup),
                'legs': self._extract_leg_breakdown(soup),
                'pressure': self._extract_pressure_situations(soup)
            }
            
        except Exception as e:
            self.logger.error(f"Error scraping match details: {e}")
        
        return details
    
    def _extract_competition_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract competition/league information."""
        info = {}
        
        league_elem = soup.find(class_='league-name')
        if league_elem:
            info['league_name'] = league_elem.text.strip()
        
        division_elem = soup.find(class_='division')
        if division_elem:
            info['division'] = division_elem.text.strip()
        
        venue_elem = soup.find(class_='venue-name')
        if venue_elem:
            info['venue'] = venue_elem.text.strip()
        
        venue_type_elem = soup.find(class_='venue-type')
        if venue_type_elem:
            info['venue_type'] = venue_type_elem.text.strip().lower()
        
        return info
    
    def _extract_opponent_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract opponent information."""
        opponent = {}
        
        name_elem = soup.find(class_='opponent-name')
        if name_elem:
            opponent['name'] = name_elem.text.strip()
        
        team_elem = soup.find(class_='opponent-team')
        if team_elem:
            opponent['team'] = team_elem.text.strip()
        
        avg_elem = soup.find(class_='opponent-average')
        if avg_elem:
            try:
                opponent['average'] = float(avg_elem.text.strip())
            except ValueError:
                pass
        
        return opponent
    
    def _extract_result_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract match result information."""
        result = {}
        
        result_elem = soup.find(class_='match-result')
        if result_elem:
            result['won'] = 'win' in result_elem.get('class', [])
            
            legs_elem = result_elem.find(class_='legs-score')
            if legs_elem:
                score_text = legs_elem.text.strip()
                match = re.match(r'(\d+)\s*-\s*(\d+)', score_text)
                if match:
                    result['legs_won'] = int(match.group(1))
                    result['legs_lost'] = int(match.group(2))
        
        return result
    
    def _extract_match_metrics(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract performance metrics from match."""
        metrics = {}
        
        metric_mappings = {
            'total-darts': 'total_darts',
            'ppd': 'points_per_dart',
            'three-dart-avg': 'three_dart_average',
            'first-nine': 'first_nine_average',
            'checkout-pct': 'checkout_percentage',
            'highest-checkout': 'highest_checkout',
            'match-180s': '180s',
            'ton-plus': 'ton_plus'
        }
        
        for css_class, metric_name in metric_mappings.items():
            elem = soup.find(class_=css_class)
            if elem:
                try:
                    text = elem.text.strip().replace('%', '').replace(',', '')
                    metrics[metric_name] = float(text) if '.' in text else int(text)
                except (ValueError, AttributeError):
                    continue
        
        # Opponent metrics
        opp_metrics = {}
        opp_section = soup.find(class_='opponent-stats')
        if opp_section:
            for css_class, metric_name in metric_mappings.items():
                elem = opp_section.find(class_=css_class)
                if elem:
                    try:
                        text = elem.text.strip().replace('%', '').replace(',', '')
                        opp_metrics[metric_name] = float(text) if '.' in text else int(text)
                    except (ValueError, AttributeError):
                        continue
        
        if opp_metrics:
            metrics['opponent_metrics'] = opp_metrics
        
        return metrics
    
    def _extract_leg_breakdown(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract leg-by-leg breakdown."""
        legs = []
        
        leg_elements = soup.find_all(class_='leg-row')
        for i, elem in enumerate(leg_elements):
            try:
                leg = {
                    'leg_number': i + 1,
                    'won': 'won' in elem.get('class', []),
                }
                
                darts_elem = elem.find(class_='darts-used')
                if darts_elem:
                    leg['darts_used'] = int(darts_elem.text.strip())
                
                checkout_elem = elem.find(class_='checkout')
                if checkout_elem:
                    leg['checkout'] = int(checkout_elem.text.strip())
                
                avg_elem = elem.find(class_='leg-average')
                if avg_elem:
                    leg['average'] = float(avg_elem.text.strip())
                
                legs.append(leg)
            except (ValueError, AttributeError):
                continue
        
        return legs
    
    def _extract_pressure_situations(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Extract pressure situation performance."""
        pressure = {}
        
        pressure_section = soup.find(class_='pressure-stats')
        if pressure_section:
            mappings = {
                'match-darts-faced': 'match_darts_faced',
                'match-darts-saved': 'match_darts_saved',
                'match-darts-thrown': 'match_darts_thrown',
                'match-darts-converted': 'match_darts_converted'
            }
            
            for css_class, key in mappings.items():
                elem = pressure_section.find(class_=css_class)
                if elem:
                    try:
                        pressure[key] = int(elem.text.strip())
                    except ValueError:
                        continue
        
        return pressure
    
    def transform_to_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw Dart Connect data to match the schema.
        
        Args:
            raw_data: Raw data from scraping
            
        Returns:
            Data matching dart_connect_schema.json
        """
        match_id = raw_data.get('match_id', '')
        if not match_id.startswith('dc_'):
            match_id = f"dc_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Extract nested data
        competition = raw_data.get('competition', {})
        opponent = raw_data.get('opponent', {})
        result = raw_data.get('result', {})
        metrics = raw_data.get('metrics', {})
        pressure = raw_data.get('pressure', {})
        
        # Determine match type
        match_type = self._determine_match_type(raw_data)
        
        transformed = {
            "match_id": match_id,
            "timestamp": raw_data.get('timestamp', datetime.now().isoformat()),
            "data_source": self.DATA_SOURCE,
            "context": self.CONTEXT,
            "match_type": match_type,
            "competition_details": {
                "league_name": competition.get('league_name', ''),
                "division": competition.get('division', ''),
                "season": competition.get('season', ''),
                "week_number": competition.get('week_number', 0),
                "venue": competition.get('venue', ''),
                "venue_type": competition.get('venue_type', 'away')
            },
            "game_format": {
                "game_type": raw_data.get('game_type', '501'),
                "legs_format": raw_data.get('legs_format', 'best of 5'),
                "double_in": False,
                "double_out": True
            },
            "opponent": {
                "name": opponent.get('name', ''),
                "team": opponent.get('team', ''),
                "ranking": opponent.get('ranking', ''),
                "historical_average": opponent.get('average', 0)
            },
            "result": {
                "won": result.get('won', False),
                "legs_won": result.get('legs_won', 0),
                "legs_lost": result.get('legs_lost', 0),
                "sets_won": result.get('sets_won', 0),
                "sets_lost": result.get('sets_lost', 0),
                "match_deciding_leg": result.get('match_deciding_leg', False)
            },
            "metrics": {
                "total_darts": metrics.get('total_darts', 0),
                "points_per_dart": metrics.get('points_per_dart', 0),
                "three_dart_average": metrics.get('three_dart_average', 0),
                "first_nine_average": metrics.get('first_nine_average', 0),
                "checkout_percentage": metrics.get('checkout_percentage', 0),
                "checkout_attempts": metrics.get('checkout_attempts', 0),
                "checkouts_hit": metrics.get('checkouts_hit', 0),
                "highest_checkout": metrics.get('highest_checkout', 0),
                "doubles": {
                    "attempts": metrics.get('doubles_attempts', 0),
                    "hits": metrics.get('doubles_hits', 0),
                    "percentage": metrics.get('doubles_percentage', 0)
                },
                "scoring": {
                    "180s": metrics.get('180s', 0),
                    "140_plus": metrics.get('140_plus', 0),
                    "100_plus": metrics.get('100_plus', 0),
                    "ton_plus_total": metrics.get('ton_plus', 0)
                },
                "opponent_metrics": metrics.get('opponent_metrics', {})
            },
            "pressure_situations": {
                "match_darts_faced": pressure.get('match_darts_faced', 0),
                "match_darts_saved": pressure.get('match_darts_saved', 0),
                "match_darts_thrown": pressure.get('match_darts_thrown', 0),
                "match_darts_converted": pressure.get('match_darts_converted', 0)
            },
            "leg_breakdown": raw_data.get('legs', []),
            "mental_notes": raw_data.get('mental_notes', '')
        }
        
        return transformed
    
    def _determine_match_type(self, raw_data: Dict[str, Any]) -> str:
        """Determine the type of competitive match."""
        match_type = raw_data.get('match_type', '').lower()
        competition = raw_data.get('competition', {})
        
        if 'tournament' in match_type:
            return 'tournament_match'
        elif 'playoff' in match_type:
            return 'playoff_match'
        elif 'league' in match_type or competition.get('league_name'):
            return 'league_match'
        else:
            return 'bar_match'
    
    def scrape_and_save(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Path]:
        """
        Scrape all matches in date range and save to files.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of paths to saved files
        """
        saved_files = []
        
        matches = self.fetch_sessions(start_date, end_date)
        
        for match_summary in matches:
            try:
                self.rate_limit(0.5)
                
                match_id = match_summary.get('match_id')
                if not match_id:
                    continue
                
                # Fetch detailed data
                details = self.fetch_session_details(match_id)
                if not details:
                    continue
                
                # Merge summary and details
                full_data = {**match_summary, **details}
                
                # Transform to schema
                transformed = self.transform_to_schema(full_data)
                
                # Save to file
                filename = f"{transformed['match_id']}.json"
                filepath = self.save_data(transformed, filename)
                saved_files.append(filepath)
                
            except Exception as e:
                self.logger.error(f"Error processing match {match_summary.get('match_id')}: {e}")
                continue
        
        self.logger.info(f"Saved {len(saved_files)} match files")
        return saved_files
    
    def __del__(self):
        """Cleanup browser on deletion."""
        self._close_browser()
