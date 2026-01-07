# google_services.py
import os
import base64
import re
import email.utils
from datetime import datetime, timedelta
from typing import Optional, List
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
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
    
    def send_email(self, to: str, subject: str, body: str, 
                   cc: Optional[str] = None, bcc: Optional[str] = None) -> dict:
        """
        Send an email via Gmail.
        
        Args:
            to: Recipient email address(es) - comma-separated for multiple
            subject: Email subject
            body: Email body (plain text)
            cc: CC email address(es) - comma-separated for multiple (optional)
            bcc: BCC email address(es) - comma-separated for multiple (optional)
        
        Returns:
            Dictionary with message ID and status
        """
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        # Create message
        message = MIMEMultipart()
        message['To'] = to
        message['Subject'] = subject
        
        if cc:
            message['Cc'] = cc
        if bcc:
            message['Bcc'] = bcc
        
        # Add body
        message.attach(MIMEText(body, 'plain'))
        
        # Encode message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        
        # Send message
        try:
            send_message = {'raw': raw_message}
            result = self.gmail.users().messages().send(
                userId='me',
                body=send_message
            ).execute()
            
            return {
                'success': True,
                'message_id': result.get('id'),
                'thread_id': result.get('threadId'),
                'message': 'Email sent successfully'
            }
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to send email: {str(e)}'
            }
    
    def _is_promotional_email(self, email_data: dict, exclusion_domains: List[str] = None) -> bool:
        """Check if an email is promotional/marketing based on various signals."""
        if exclusion_domains is None:
            exclusion_domains = []
        
        from_addr = email_data.get('from', '').lower()
        subject = email_data.get('subject', '').lower()
        snippet = email_data.get('snippet', '').lower()
        
        # Check exclusion domains
        for domain in exclusion_domains:
            if domain.lower() in from_addr:
                return True
        
        # Common promotional indicators
        promotional_keywords = [
            'unsubscribe', 'marketing', 'promotion', 'special offer', 'limited time',
            'act now', 'buy now', 'discount', 'sale', 'deal', 'coupon', 'newsletter',
            'sponsored', 'advertisement', 'ad', 'promo code', 'exclusive offer'
        ]
        
        # Check subject and snippet for promotional keywords
        text_to_check = f"{subject} {snippet}"
        if any(keyword in text_to_check for keyword in promotional_keywords):
            return True
        
        # Check for common promotional email patterns
        promotional_patterns = [
            r'noreply@', r'no-reply@', r'donotreply@', r'newsletter@',
            r'marketing@', r'promo@', r'sales@', r'offers@'
        ]
        
        for pattern in promotional_patterns:
            if re.search(pattern, from_addr):
                return True
        
        # Check for list-unsubscribe header (common in marketing emails)
        # This would require getting full email headers, so we'll skip for now
        
        return False
    
    def _extract_domain_from_email(self, from_addr: str) -> str:
        """Extract domain from email address."""
        # Extract email from "Name <email@domain.com>" or just "email@domain.com"
        match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', from_addr)
        if match:
            email_addr = match.group(0)
            return email_addr.split('@')[1].lower()
        return ''
    
    def get_user_email(self) -> str:
        """Get the user's email address."""
        try:
            profile = self.gmail.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', '')
        except Exception:
            return ''
    
    def get_emails_since(self, since_date: datetime, max_results: int = 50, 
                        exclude_promotional: bool = True, 
                        exclusion_domains: List[str] = None,
                        inbound_only: bool = True) -> list:
        """
        Get emails since a specific date, optionally filtering out promotional emails.
        
        Args:
            since_date: Date to get emails since
            max_results: Maximum number of emails to return
            exclude_promotional: Whether to exclude promotional emails
            exclusion_domains: List of domains to exclude
            inbound_only: Only return inbound (received) emails, exclude sent emails
        """
        since_date = self._ensure_timezone(since_date)
        
        # Gmail search query for emails after a specific date
        # Format: after:YYYY/MM/DD
        date_str = since_date.strftime('%Y/%m/%d')
        query = f'after:{date_str}'
        
        # Only show inbox emails (naturally excludes sent emails)
        # Also exclude sent emails explicitly
        if inbound_only:
            query += ' in:inbox -from:me'
        
        # Exclude promotional emails from primary mailbox
        if exclude_promotional:
            query += ' -category:promotions -category:social -category:updates'
        
        results = self.gmail.users().messages().list(
            userId='me', 
            maxResults=max_results, 
            q=query
        ).execute()
        
        messages = results.get('messages', [])
        emails = []
        
        for msg in messages:
            email_data = self.gmail.users().messages().get(
                userId='me', id=msg['id'], format='metadata',
                metadataHeaders=['From', 'Subject', 'Date', 'List-Unsubscribe']
            ).execute()
            
            headers = {h['name']: h['value'] for h in email_data['payload']['headers']}
            
            # Additional check: ensure this is not a sent email
            if inbound_only:
                # Check labels to ensure it's not in SENT
                labels = email_data.get('labelIds', [])
                if 'SENT' in labels:
                    continue
                
                # Double-check: if From header contains user's email, skip
                from_addr = headers.get('From', '')
                user_email = self.get_user_email()
                if user_email and user_email.lower() in from_addr.lower():
                    continue
            
            email_info = {
                'id': msg['id'],
                'from': headers.get('From', ''),
                'subject': headers.get('Subject', ''),
                'date': headers.get('Date', ''),
                'snippet': email_data.get('snippet', ''),
                'domain': self._extract_domain_from_email(headers.get('From', ''))
            }
            
            # Additional filtering for promotional emails
            if exclude_promotional:
                if self._is_promotional_email(email_info, exclusion_domains):
                    continue
            
            # Parse date for better formatting
            try:
                parsed_date = email.utils.parsedate_to_datetime(headers.get('Date', ''))
                email_info['parsed_date'] = parsed_date.isoformat() if parsed_date else None
            except:
                email_info['parsed_date'] = None
            
            emails.append(email_info)
        
        return emails
    
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