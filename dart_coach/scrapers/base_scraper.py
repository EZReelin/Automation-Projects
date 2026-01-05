"""
Base Scraper Module
==================
Abstract base class for all dart performance scrapers.
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class BaseScraper(ABC):
    """Abstract base class for dart performance data scrapers."""
    
    def __init__(
        self,
        base_url: str,
        data_dir: Path,
        retry_attempts: int = 3,
        retry_delay: int = 5,
        session_timeout: int = 3600,
        log_level: str = "INFO"
    ):
        """
        Initialize the base scraper.
        
        Args:
            base_url: Base URL for the data source
            data_dir: Directory to store scraped data
            retry_attempts: Number of retry attempts for failed requests
            retry_delay: Delay between retries in seconds
            session_timeout: Session timeout in seconds
            log_level: Logging level
        """
        self.base_url = base_url.rstrip('/')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.session_timeout = session_timeout
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
        
        # Setup session with retry logic
        self.session = self._create_session()
        self._authenticated = False
        self._auth_expiry: Optional[datetime] = None
    
    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=self.retry_attempts,
            backoff_factor=self.retry_delay,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        session.headers.update({
            'User-Agent': 'DartCoach/1.0 (Performance Analysis System)',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        return session
    
    @abstractmethod
    def authenticate(self, username: str, password: str) -> bool:
        """
        Authenticate with the data source.
        
        Args:
            username: Account username
            password: Account password
            
        Returns:
            True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    def fetch_sessions(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Fetch session/match data within a date range.
        
        Args:
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            List of session/match data dictionaries
        """
        pass
    
    @abstractmethod
    def fetch_session_details(self, session_id: str) -> Dict[str, Any]:
        """
        Fetch detailed data for a specific session/match.
        
        Args:
            session_id: Unique identifier of the session/match
            
        Returns:
            Detailed session/match data dictionary
        """
        pass
    
    @abstractmethod
    def transform_to_schema(self, raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform raw scraped data to match the defined schema.
        
        Args:
            raw_data: Raw data from the scraper
            
        Returns:
            Data transformed to match schema
        """
        pass
    
    def is_authenticated(self) -> bool:
        """Check if current session is authenticated and not expired."""
        if not self._authenticated:
            return False
        if self._auth_expiry and datetime.now() > self._auth_expiry:
            self._authenticated = False
            return False
        return True
    
    def make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Optional[requests.Response]:
        """
        Make an HTTP request with error handling.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint
            data: Request body data
            params: Query parameters
            headers: Additional headers
            
        Returns:
            Response object or None if request failed
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=data,
                params=params,
                headers=headers,
                timeout=30
            )
            response.raise_for_status()
            return response
            
        except requests.exceptions.HTTPError as e:
            self.logger.error(f"HTTP error for {url}: {e}")
            if response.status_code == 401:
                self._authenticated = False
            return None
            
        except requests.exceptions.ConnectionError as e:
            self.logger.error(f"Connection error for {url}: {e}")
            return None
            
        except requests.exceptions.Timeout as e:
            self.logger.error(f"Timeout for {url}: {e}")
            return None
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Request error for {url}: {e}")
            return None
    
    def save_data(
        self,
        data: Dict[str, Any],
        filename: str,
        subdirectory: Optional[str] = None
    ) -> Path:
        """
        Save data to a JSON file.
        
        Args:
            data: Data to save
            filename: Name of the file
            subdirectory: Optional subdirectory within data_dir
            
        Returns:
            Path to the saved file
        """
        save_dir = self.data_dir
        if subdirectory:
            save_dir = save_dir / subdirectory
            save_dir.mkdir(parents=True, exist_ok=True)
        
        filepath = save_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        self.logger.info(f"Saved data to {filepath}")
        return filepath
    
    def load_data(self, filename: str, subdirectory: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Load data from a JSON file.
        
        Args:
            filename: Name of the file
            subdirectory: Optional subdirectory within data_dir
            
        Returns:
            Loaded data or None if file not found
        """
        load_dir = self.data_dir
        if subdirectory:
            load_dir = load_dir / subdirectory
        
        filepath = load_dir / filename
        
        if not filepath.exists():
            self.logger.warning(f"File not found: {filepath}")
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def generate_session_id(self, prefix: str) -> str:
        """Generate a unique session ID with timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{prefix}_{timestamp}"
    
    def rate_limit(self, delay: float = 1.0):
        """Apply rate limiting between requests."""
        time.sleep(delay)
