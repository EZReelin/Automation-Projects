"""
Google Calendar Integration Module
=================================
Integrates with Google Calendar for scheduling analysis reports.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False


class GoogleCalendarIntegration:
    """
    Google Calendar integration for dart performance reports.
    
    Creates calendar events with weekly analysis summaries.
    """
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    
    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
        calendar_id: str = 'primary',
        log_level: str = "INFO"
    ):
        """
        Initialize Google Calendar integration.
        
        Args:
            credentials_file: Path to OAuth2 credentials file
            token_file: Path to store/retrieve token
            calendar_id: Calendar ID to use
            log_level: Logging level
        """
        self.credentials_file = credentials_file or os.getenv(
            'GOOGLE_CALENDAR_CREDENTIALS_FILE',
            'credentials.json'
        )
        self.token_file = token_file or os.getenv(
            'GOOGLE_CALENDAR_TOKEN_FILE',
            'token.json'
        )
        self.calendar_id = calendar_id
        
        self.service = None
        self._authenticated = False
        
        # Setup logging
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
        
        if not GOOGLE_AVAILABLE:
            self.logger.warning(
                "Google Calendar libraries not installed. "
                "Install with: pip install google-auth-oauthlib google-api-python-client"
            )
    
    def authenticate(self) -> bool:
        """
        Authenticate with Google Calendar API.
        
        Returns:
            True if authentication successful
        """
        if not GOOGLE_AVAILABLE:
            self.logger.error("Google Calendar libraries not available")
            return False
        
        creds = None
        
        # Try to load existing token
        if os.path.exists(self.token_file):
            try:
                creds = Credentials.from_authorized_user_file(
                    self.token_file,
                    self.SCOPES
                )
            except Exception as e:
                self.logger.warning(f"Could not load token: {e}")
        
        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                except Exception as e:
                    self.logger.warning(f"Could not refresh token: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_file):
                    self.logger.error(
                        f"Credentials file not found: {self.credentials_file}"
                    )
                    return False
                
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file,
                        self.SCOPES
                    )
                    creds = flow.run_local_server(port=0)
                except Exception as e:
                    self.logger.error(f"Authentication flow failed: {e}")
                    return False
            
            # Save token
            try:
                with open(self.token_file, 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                self.logger.warning(f"Could not save token: {e}")
        
        # Build service
        try:
            self.service = build('calendar', 'v3', credentials=creds)
            self._authenticated = True
            self.logger.info("Google Calendar authentication successful")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to build calendar service: {e}")
            return False
    
    def create_analysis_event(
        self,
        report: Dict[str, Any],
        event_date: Optional[datetime] = None,
        duration_minutes: int = 30,
        reminder_minutes: int = 60
    ) -> Optional[str]:
        """
        Create a calendar event for the weekly analysis report.
        
        Args:
            report: Analysis report data
            event_date: Date/time for the event (defaults to next Sunday 6 PM)
            duration_minutes: Event duration in minutes
            reminder_minutes: Reminder before event
            
        Returns:
            Event ID if successful, None otherwise
        """
        if not self._authenticated:
            if not self.authenticate():
                return None
        
        # Default to next Sunday 6 PM
        if event_date is None:
            today = datetime.now()
            days_until_sunday = (6 - today.weekday()) % 7
            if days_until_sunday == 0:
                days_until_sunday = 7
            event_date = today + timedelta(days=days_until_sunday)
            event_date = event_date.replace(hour=18, minute=0, second=0, microsecond=0)
        
        # Build event summary
        period = report.get('week_period', {})
        analysis = report.get('analysis', {})
        
        summary = f"🎯 Dart Coach Weekly Analysis - Week {period.get('week_number', 'N/A')}"
        
        # Build event description
        description = self._build_event_description(report)
        
        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': event_date.isoformat(),
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': (event_date + timedelta(minutes=duration_minutes)).isoformat(),
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': reminder_minutes},
                ],
            },
            'colorId': '7',  # Peacock/teal color
        }
        
        try:
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            event_id = created_event.get('id')
            self.logger.info(f"Created calendar event: {event_id}")
            return event_id
            
        except HttpError as e:
            self.logger.error(f"Failed to create event: {e}")
            return None
    
    def _build_event_description(self, report: Dict[str, Any]) -> str:
        """Build event description from report."""
        analysis = report.get('analysis', {})
        practice = report.get('practice_summary', {})
        competition = report.get('competition_summary', {})
        
        description = f"""📊 WEEKLY DART PERFORMANCE ANALYSIS

📅 Period: {report.get('week_period', {}).get('start_date', 'N/A')} to {report.get('week_period', {}).get('end_date', 'N/A')}

📝 EXECUTIVE SUMMARY
{analysis.get('executive_summary', 'Review your weekly performance report for details.')}

🎯 PRACTICE PERFORMANCE
• Sessions: {practice.get('sessions_count', 0)}
• Average: {practice.get('metrics', {}).get('average_three_dart', 0):.1f}
• Checkout %: {practice.get('metrics', {}).get('average_checkout_pct', 0):.1f}%
• 180s: {practice.get('metrics', {}).get('total_180s', 0)}

🏆 COMPETITION PERFORMANCE  
• Matches: {competition.get('total_matches', 0)}
• Record: {competition.get('matches_won', 0)}-{competition.get('matches_lost', 0)}
• Average: {competition.get('metrics', {}).get('average_three_dart', 0):.1f}

🎯 TOP RECOMMENDATIONS
"""
        
        for i, rec in enumerate(analysis.get('recommendations', [])[:3], 1):
            description += f"{i}. {rec.get('area', 'General')}: {rec.get('recommendation', '')[:100]}...\n"
        
        description += f"""

📈 GOALS FOR THIS WEEK
"""
        
        for goal in analysis.get('goals_for_next_week', [])[:3]:
            description += f"• {goal.get('goal', '')[:100]}\n"
        
        description += """

---
Generated by Dart Performance Coach
"""
        
        return description
    
    def list_upcoming_events(self, max_results: int = 10) -> List[Dict[str, Any]]:
        """List upcoming calendar events."""
        if not self._authenticated:
            if not self.authenticate():
                return []
        
        try:
            now = datetime.utcnow().isoformat() + 'Z'
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            return events
            
        except HttpError as e:
            self.logger.error(f"Failed to list events: {e}")
            return []
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event."""
        if not self._authenticated:
            if not self.authenticate():
                return False
        
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            self.logger.info(f"Deleted event: {event_id}")
            return True
            
        except HttpError as e:
            self.logger.error(f"Failed to delete event: {e}")
            return False
