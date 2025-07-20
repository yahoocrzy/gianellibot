from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
import os
import json
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from loguru import logger
import asyncio
from concurrent.futures import ThreadPoolExecutor

class GoogleCalendarAPI:
    """Google Calendar API wrapper for calendar operations"""
    
    SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
    
    def __init__(self, credentials_json: str = None):
        """Initialize Google Calendar API
        
        Args:
            credentials_json: Stored OAuth2 credentials in JSON format
        """
        self.credentials = None
        self.service = None
        self.executor = ThreadPoolExecutor(max_workers=5)
        
        if credentials_json:
            try:
                self.credentials = Credentials.from_authorized_user_info(
                    json.loads(credentials_json),
                    self.SCOPES
                )
                self._build_service()
            except Exception as e:
                logger.error(f"Failed to load credentials: {e}")
    
    def _build_service(self):
        """Build the Google Calendar service"""
        if self.credentials and self.credentials.valid:
            self.service = build('calendar', 'v3', credentials=self.credentials)
    
    async def refresh_credentials(self) -> bool:
        """Refresh expired credentials
        
        Returns:
            bool: True if refresh successful, False otherwise
        """
        if not self.credentials:
            return False
            
        if self.credentials.expired and self.credentials.refresh_token:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    self.executor,
                    self.credentials.refresh,
                    Request()
                )
                self._build_service()
                return True
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                return False
        return True
    
    def get_credentials_json(self) -> Optional[str]:
        """Get credentials as JSON string for storage
        
        Returns:
            str: JSON credentials or None
        """
        if self.credentials:
            return self.credentials.to_json()
        return None
    
    async def list_calendars(self) -> List[Dict]:
        """List all calendars for the authenticated user
        
        Returns:
            List of calendar dictionaries
        """
        if not self.service:
            await self.refresh_credentials()
            if not self.service:
                raise Exception("Not authenticated")
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.service.calendarList().list().execute
            )
            return result.get('items', [])
        except Exception as e:
            logger.error(f"Failed to list calendars: {e}")
            raise
    
    async def list_events(
        self,
        calendar_id: str = 'primary',
        time_min: datetime = None,
        time_max: datetime = None,
        max_results: int = 10,
        single_events: bool = True,
        order_by: str = 'startTime'
    ) -> List[Dict]:
        """List events from a calendar
        
        Args:
            calendar_id: Calendar ID (default 'primary')
            time_min: Start time filter
            time_max: End time filter
            max_results: Maximum number of results
            single_events: Whether to expand recurring events
            order_by: Sort order
            
        Returns:
            List of event dictionaries
        """
        if not self.service:
            await self.refresh_credentials()
            if not self.service:
                raise Exception("Not authenticated")
        
        # Default to next 7 days if no time specified
        if not time_min:
            time_min = datetime.now(timezone.utc)
        if not time_max:
            time_max = time_min + timedelta(days=7)
        
        try:
            # Convert to proper RFC3339 format for Google Calendar API
            time_min_str = time_min.isoformat()
            time_max_str = time_max.isoformat()
            
            # Add Z if timezone aware, otherwise assume UTC
            if time_min.tzinfo is None:
                time_min_str += 'Z'
            if time_max.tzinfo is None:
                time_max_str += 'Z'
                
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self.service.events().list(
                    calendarId=calendar_id,
                    timeMin=time_min_str,
                    timeMax=time_max_str,
                    maxResults=max_results,
                    singleEvents=single_events,
                    orderBy=order_by
                ).execute()
            )
            return result.get('items', [])
        except Exception as e:
            logger.error(f"Failed to list events: {e}")
            raise
    
    async def get_event(self, event_id: str, calendar_id: str = 'primary') -> Dict:
        """Get a specific event
        
        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default 'primary')
            
        Returns:
            Event dictionary
        """
        if not self.service:
            await self.refresh_credentials()
            if not self.service:
                raise Exception("Not authenticated")
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self.service.events().get(
                    calendarId=calendar_id,
                    eventId=event_id
                ).execute()
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get event: {e}")
            raise
    
    async def get_calendar_colors(self) -> Dict:
        """Get available calendar and event colors
        
        Returns:
            Dictionary of colors
        """
        if not self.service:
            await self.refresh_credentials()
            if not self.service:
                raise Exception("Not authenticated")
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self.service.colors().get().execute
            )
            return result
        except Exception as e:
            logger.error(f"Failed to get colors: {e}")
            raise
    
    @staticmethod
    def create_auth_flow(redirect_uri: str) -> Flow:
        """Create OAuth2 flow for authentication
        
        Args:
            redirect_uri: OAuth2 redirect URI
            
        Returns:
            OAuth2 Flow object
        """
        # Check for required environment variables
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        
        if not client_id or not client_secret:
            raise ValueError("Missing required Google OAuth credentials: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set")
        
        # OAuth2 client configuration
        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "redirect_uris": [redirect_uri]
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=GoogleCalendarAPI.SCOPES
        )
        flow.redirect_uri = redirect_uri
        
        return flow
    
    @staticmethod
    def parse_event_time(event: Dict) -> tuple[datetime, datetime]:
        """Parse event start and end times
        
        Args:
            event: Event dictionary from Google Calendar API
            
        Returns:
            Tuple of (start_time, end_time) as datetime objects
        """
        start = event.get('start', {})
        end = event.get('end', {})
        
        # Handle all-day events
        if 'date' in start:
            start_time = datetime.fromisoformat(start['date'])
            end_time = datetime.fromisoformat(end['date'])
        else:
            # Handle timed events
            start_time = datetime.fromisoformat(start.get('dateTime', '').replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end.get('dateTime', '').replace('Z', '+00:00'))
        
        return start_time, end_time