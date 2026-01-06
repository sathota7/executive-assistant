# google_services.py
import os
import base64
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar'
]

# Default timezone - Eastern Time (handles EST/EDT automatically)
DEFAULT_TIMEZONE = 'America/New_York'


class GoogleServices:
    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None
        self.tz = ZoneInfo(DEFAULT_TIMEZONE)
        self._authenticate()
        self.gmail = build('gmail', 'v1', credentials=self.creds)
        self.calendar = build('calendar', 'v3', credentials=self.creds)
    
    def _authenticate(self):
        """Handle OAuth2 authentication flow."""
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                self.creds = flow.run_local_server(port=0)
            
            with open(self.token_path, 'w') as token:
                token.write(self.creds.to_json())
    
    def _ensure_timezone(self, dt: datetime) -> datetime:
        """Ensure a datetime has the default timezone."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=self.tz)
        return dt.astimezone(self.tz)
    
    def _parse_datetime(self, dt_string: str) -> datetime:
        """Parse a datetime string and ensure it has the correct timezone."""
        # Handle various formats
        dt_string = dt_string.replace('Z', '+00:00')
        
        try:
            # Try ISO format first
            if '+' in dt_string or '-' in dt_string[10:]:
                dt = datetime.fromisoformat(dt_string)
            else:
                dt = datetime.fromisoformat(dt_string)
                dt = dt.replace(tzinfo=self.tz)
        except ValueError:
            # Fallback parsing
            dt = datetime.fromisoformat(dt_string.split('.')[0])
            dt = dt.replace(tzinfo=self.tz)
        
        return dt.astimezone(self.tz)
    
    # ===== GMAIL METHODS =====
    
    def get_recent_emails(self, max_results: int = 20, query: str = '') -> list:
        """Fetch recent emails, optionally filtered by query."""
        results = self.gmail.users().messages().list(
            userId='me', maxResults=max_results, q=query
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for msg in messages:
            email_data = self.gmail.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date']
            ).execute()
            
            headers = {h['name']: h['value'] for h in email_data['payload']['headers']}
            emails.append({
                'id': msg['id'],
                'from': headers.get('From', ''),
                'subject': headers.get('Subject', ''),
                'date': headers.get('Date', ''),
                'snippet': email_data.get('snippet', '')
            })
        
        return emails
    
    def get_email_body(self, email_id: str) -> str:
        """Get the full body of an email."""
        msg = self.gmail.users().messages().get(userId='me', id=email_id, format='full').execute()
        
        def extract_body(payload):
            if 'body' in payload and payload['body'].get('data'):
                return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        if part['body'].get('data'):
                            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
                    result = extract_body(part)
                    if result:
                        return result
            return ''
        
        return extract_body(msg['payload'])
    
    # ===== CALENDAR METHODS =====
    
    def get_events(self, days_ahead: int = 7, calendar_id: str = 'primary') -> list:
        """Get calendar events for the next N days."""
        now = datetime.now(self.tz)
        time_min = now.isoformat()
        time_max = (now + timedelta(days=days_ahead)).isoformat()
        
        events_result = self.calendar.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy='startTime',
            timeZone=DEFAULT_TIMEZONE
        ).execute()
        
        return events_result.get('items', [])
    
    def get_free_busy(self, start: datetime, end: datetime) -> list:
        """Get busy times in a date range."""
        start = self._ensure_timezone(start)
        end = self._ensure_timezone(end)
        
        body = {
            "timeMin": start.isoformat(),
            "timeMax": end.isoformat(),
            "timeZone": DEFAULT_TIMEZONE,
            "items": [{"id": "primary"}]
        }
        
        result = self.calendar.freebusy().query(body=body).execute()
        return result['calendars']['primary']['busy']
    
    def find_free_slots(self, days_ahead: int = 7, slot_duration_minutes: int = 60,
                        work_start: int = 9, work_end: int = 17) -> list:
        """Find available time slots in the next N days."""
        now = datetime.now(self.tz)
        end_date = now + timedelta(days=days_ahead)
        busy_times = self.get_free_busy(now, end_date)
        
        # Convert busy times to datetime objects in local timezone
        busy_periods = []
        for busy in busy_times:
            busy_start = self._parse_datetime(busy['start'])
            busy_end = self._parse_datetime(busy['end'])
            busy_periods.append((busy_start, busy_end))
        
        # Find free slots during work hours
        free_slots = []
        current = now.replace(hour=work_start, minute=0, second=0, microsecond=0)
        if current < now:
            current += timedelta(days=1)
        
        for _ in range(days_ahead):
            day_start = current.replace(hour=work_start)
            day_end = current.replace(hour=work_end)
            
            # Skip weekends
            if current.weekday() >= 5:
                current += timedelta(days=1)
                continue
            
            slot_start = day_start
            while slot_start + timedelta(minutes=slot_duration_minutes) <= day_end:
                slot_end = slot_start + timedelta(minutes=slot_duration_minutes)
                
                # Check if slot conflicts with busy periods
                is_free = True
                for busy_start, busy_end in busy_periods:
                    if not (slot_end <= busy_start or slot_start >= busy_end):
                        is_free = False
                        break
                
                if is_free:
                    free_slots.append({
                        'start': slot_start.isoformat(),
                        'end': slot_end.isoformat(),
                        'display': f"{slot_start.strftime('%A %b %d, %I:%M %p')} - {slot_end.strftime('%I:%M %p')} ET"
                    })
                
                slot_start += timedelta(minutes=30)
            
            current += timedelta(days=1)
        
        return free_slots
    
    def create_event(self, summary: str, start: datetime, end: datetime,
                     description: str = '', location: str = '') -> dict:
        """Create a new calendar event."""
        start = self._ensure_timezone(start)
        end = self._ensure_timezone(end)
        
        event = {
            'summary': summary,
            'description': description,
            'location': location,
            'start': {'dateTime': start.isoformat(), 'timeZone': DEFAULT_TIMEZONE},
            'end': {'dateTime': end.isoformat(), 'timeZone': DEFAULT_TIMEZONE},
        }
        
        return self.calendar.events().insert(calendarId='primary', body=event).execute()
    
    def check_conflicts(self, start: datetime, end: datetime) -> list:
        """Check if a time slot has conflicts."""
        start = self._ensure_timezone(start)
        end = self._ensure_timezone(end)
        
        events = self.calendar.events().list(
            calendarId='primary',
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            timeZone=DEFAULT_TIMEZONE
        ).execute()
        
        return events.get('items', [])
    
    def delete_event(self, event_id: str) -> bool:
        """Delete a calendar event by its ID."""
        try:
            self.calendar.events().delete(calendarId='primary', eventId=event_id).execute()
            return True
        except Exception as e:
            print(f"Error deleting event: {e}")
            return False
    
    def find_event_by_name(self, search_term: str, days_ahead: int = 30) -> list:
        """Find events matching a search term."""
        events = self.get_events(days_ahead=days_ahead)
        matching_events = []
        
        search_lower = search_term.lower()
        for event in events:
            summary = event.get('summary', '').lower()
            description = event.get('description', '').lower()
            
            if search_lower in summary or search_lower in description:
                matching_events.append(event)
        
        return matching_events