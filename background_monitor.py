# background_monitor.py
"""
Background service that monitors for scheduling conflicts and sends notifications.
Run this separately from the main assistant.
"""
import time
import schedule
from datetime import datetime, timedelta
from google_services import GoogleServices

# For desktop notifications
try:
    from plyer import notification
    HAS_NOTIFICATIONS = True
except ImportError:
    HAS_NOTIFICATIONS = False
    print("Install plyer for desktop notifications: pip install plyer")

PRIORITY_KEYWORDS = [
    'interview', 'deadline', 'presentation', 'meeting with ceo',
    'board meeting', 'final', 'urgent', 'important'
]

class BackgroundMonitor:
    def __init__(self):
        self.google = GoogleServices()
        self.notified_events = set()
    
    def send_notification(self, title: str, message: str):
        """Send a desktop notification."""
        if HAS_NOTIFICATIONS:
            notification.notify(
                title=title,
                message=message,
                app_name="Executive Assistant",
                timeout=10
            )
        print(f"📢 {title}: {message}")
    
    def check_upcoming_priority_events(self):
        """Check for priority events in the next 24 hours."""
        events = self.google.get_events(days_ahead=1)
        
        for event in events:
            event_id = event.get('id')
            summary = event.get('summary', '').lower()
            
            # Check if it's a priority event
            is_priority = any(keyword in summary for keyword in PRIORITY_KEYWORDS)
            
            if is_priority and event_id not in self.notified_events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                self.send_notification(
                    "⚠️ Important Event Coming Up",
                    f"{event.get('summary')} at {start}"
                )
                self.notified_events.add(event_id)
    
    def check_daily_summary(self):
        """Send a daily summary of events."""
        events = self.google.get_events(days_ahead=1)
        
        if events:
            summary = f"You have {len(events)} events today:\n"
            for event in events[:5]:
                start = event['start'].get('dateTime', event['start'].get('date'))
                summary += f"• {event.get('summary', 'No title')} at {start}\n"
            
            self.send_notification("📅 Daily Summary", summary)
    
    def run(self):
        """Start the background monitor."""
        print("🔄 Background monitor started...")
        
        # Check for priority events every 30 minutes
        schedule.every(30).minutes.do(self.check_upcoming_priority_events)
        
        # Daily summary at 8 AM
        schedule.every().day.at("08:00").do(self.check_daily_summary)
        
        # Initial check
        self.check_upcoming_priority_events()
        
        while True:
            schedule.run_pending()
            time.sleep(60)


if __name__ == "__main__":
    monitor = BackgroundMonitor()
    monitor.run()