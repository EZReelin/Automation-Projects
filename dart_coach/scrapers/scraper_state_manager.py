"""
Scraper State Manager Module
============================
Manages state persistence for web scrapers to enable incremental scraping.
"""

import json
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Any, Dict, Optional


class ScraperStateManager:
    """Manages state persistence for scrapers to track last processed dates."""

    def __init__(self, state_file: Path, logger: Optional[logging.Logger] = None):
        """
        Initialize the state manager.

        Args:
            state_file: Path to the JSON state file
            logger: Optional logger instance
        """
        self.state_file = Path(state_file)
        self.logger = logger or logging.getLogger(__name__)

        # Ensure parent directory exists
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        # Load existing state or initialize new state
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """
        Load state from file or initialize new state.

        Returns:
            Dictionary containing state data
        """
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                self.logger.info(f"Loaded state from {self.state_file}")
                return state
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Failed to load state from {self.state_file}: {e}")
                return self._initialize_state()
        else:
            self.logger.info(f"No existing state file found at {self.state_file}, initializing new state")
            return self._initialize_state()

    def _initialize_state(self) -> Dict[str, Any]:
        """
        Initialize a new state dictionary.

        Returns:
            New state dictionary
        """
        return {
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "last_processed_date": None,
            "total_sessions_scraped": 0,
            "last_successful_scrape": None,
            "scrape_history": [],
            "metadata": {}
        }

    def save_state(self) -> None:
        """Save current state to file."""
        try:
            self.state["last_updated"] = datetime.now().isoformat()

            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2, default=str)

            self.logger.info(f"Saved state to {self.state_file}")
        except IOError as e:
            self.logger.error(f"Failed to save state to {self.state_file}: {e}")

    def get_last_processed_date(self) -> Optional[date]:
        """
        Get the last processed date.

        Returns:
            Last processed date or None if never scraped
        """
        last_date_str = self.state.get("last_processed_date")
        if last_date_str:
            try:
                return datetime.fromisoformat(last_date_str).date()
            except ValueError:
                self.logger.warning(f"Invalid date format in state: {last_date_str}")
                return None
        return None

    def update_last_processed_date(self, processed_date: date) -> None:
        """
        Update the last processed date.

        Args:
            processed_date: Date that was just processed
        """
        current_last = self.get_last_processed_date()

        # Only update if the new date is more recent
        if current_last is None or processed_date > current_last:
            self.state["last_processed_date"] = processed_date.isoformat()
            self.logger.info(f"Updated last processed date to {processed_date}")
        else:
            self.logger.debug(f"Not updating last processed date - {processed_date} is not more recent than {current_last}")

    def record_scrape_session(
        self,
        sessions_scraped: int,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record information about a scraping session.

        Args:
            sessions_scraped: Number of sessions scraped in this run
            success: Whether the scrape was successful
            error_message: Optional error message if scrape failed
        """
        scrape_record = {
            "timestamp": datetime.now().isoformat(),
            "sessions_scraped": sessions_scraped,
            "success": success,
            "error_message": error_message
        }

        # Add to history
        self.state["scrape_history"].append(scrape_record)

        # Keep only last 50 records to prevent file bloat
        if len(self.state["scrape_history"]) > 50:
            self.state["scrape_history"] = self.state["scrape_history"][-50:]

        # Update totals if successful
        if success:
            self.state["total_sessions_scraped"] = self.state.get("total_sessions_scraped", 0) + sessions_scraped
            self.state["last_successful_scrape"] = datetime.now().isoformat()

        self.logger.info(f"Recorded scrape session: {sessions_scraped} sessions, success={success}")

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """
        Get metadata value.

        Args:
            key: Metadata key
            default: Default value if key not found

        Returns:
            Metadata value or default
        """
        return self.state.get("metadata", {}).get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """
        Set metadata value.

        Args:
            key: Metadata key
            value: Metadata value
        """
        if "metadata" not in self.state:
            self.state["metadata"] = {}

        self.state["metadata"][key] = value
        self.logger.debug(f"Set metadata: {key} = {value}")

    def reset_state(self) -> None:
        """Reset state to initial values."""
        self.logger.warning("Resetting scraper state")
        self.state = self._initialize_state()
        self.save_state()

    def get_scrape_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about scraping history.

        Returns:
            Dictionary containing scrape statistics
        """
        history = self.state.get("scrape_history", [])
        successful_scrapes = [s for s in history if s.get("success", False)]
        failed_scrapes = [s for s in history if not s.get("success", True)]

        return {
            "total_sessions_scraped": self.state.get("total_sessions_scraped", 0),
            "last_successful_scrape": self.state.get("last_successful_scrape"),
            "last_processed_date": self.state.get("last_processed_date"),
            "total_scrape_runs": len(history),
            "successful_runs": len(successful_scrapes),
            "failed_runs": len(failed_scrapes),
            "success_rate": len(successful_scrapes) / len(history) * 100 if history else 0
        }

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - saves state on exit."""
        self.save_state()
        return False
