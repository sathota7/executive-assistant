# assistant.py
import os
import json
from datetime import datetime, timedelta
from typing import Optional, List
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import anthropic
from google_services import GoogleServices

# Try to import Reddit services (optional)
try:
    from reddit_services import RedditServices
    HAS_REDDIT = True
except ImportError:
    HAS_REDDIT = False
except Exception as e:
    HAS_REDDIT = False
    print(f"Warning: Reddit services not available: {e}")

# Try to import News services (optional)
try:
    from news_services import NewsServices, RSSNewsServices
    HAS_NEWS = True
except ImportError:
    HAS_NEWS = False
except Exception as e:
    HAS_NEWS = False
    print(f"Warning: News services not available: {e}")

# Load environment variables from .env file
load_dotenv()

# Default timezone
DEFAULT_TIMEZONE = 'America/New_York'

# Priority keywords for flagging important events
PRIORITY_KEYWORDS = [
    'interview', 'deadline', 'presentation', 'meeting with ceo',
    'board meeting', 'final', 'urgent', 'important', 'review',
    'submission', 'due date', 'exam', 'flight', 'doctor'
]


class ExecutiveAssistant:
    def __init__(self, anthropic_api_key: Optional[str] = None):
        # Load API key from parameter, environment variable, or .env file
        api_key = anthropic_api_key or os.getenv('ANTHROPIC_API_KEY')
        
        if not api_key:
            raise ValueError(
                "Anthropic API key not found. Please either:\n"
                "1. Create a .env file with ANTHROPIC_API_KEY=your-key-here\n"
                "2. Set the ANTHROPIC_API_KEY environment variable\n"
                "3. Pass the key directly to ExecutiveAssistant()"
            )
        
        self.google = GoogleServices()
        self.client = anthropic.Anthropic(api_key=api_key)
        self.conversation_history = []
        self.tz = ZoneInfo(DEFAULT_TIMEZONE)
        self.state_file = 'assistant_state.json'
        self.exclusion_file = 'email_exclusions.json'
        
        # Initialize Reddit services (optional)
        self.reddit = None
        if HAS_REDDIT:
            try:
                self.reddit = RedditServices()
            except Exception as e:
                print(f"Warning: Could not initialize Reddit services: {e}")
                print("Reddit features will be disabled. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env to enable.")
        
        # Initialize News services (optional)
        self.news = None
        if HAS_NEWS:
            try:
                # Try NewsAPI first (requires API key)
                self.news = NewsServices()
            except ValueError:
                # Fall back to RSS feeds if no API key
                try:
                    print("NewsAPI key not found. Using RSS feeds instead (no API key required).")
                    self.news = RSSNewsServices()
                except ImportError:
                    print("feedparser not installed. Install with: pip install feedparser")
                    self.news = None
                except Exception as e:
                    print(f"Warning: Could not initialize News services: {e}")
                    self.news = None
            except Exception as e:
                print(f"Warning: Could not initialize News services: {e}")
                print("News features will be disabled. Set NEWS_API_KEY in .env to enable NewsAPI, or install feedparser for RSS feeds.")
        
        self._load_state()
        # Store previous login before updating
        self.previous_login = self.last_login
        self._update_last_login()
    
    def _load_state(self):
        """Load assistant state (last login, exclusion list, etc.)."""
        self.last_login = None
        self.exclusion_domains = []
        
        # Load last login time
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    if 'last_login' in state:
                        last_login_str = state['last_login']
                        # Handle both timezone-aware and naive datetime strings
                        if '+' in last_login_str or last_login_str.endswith('Z'):
                            self.last_login = datetime.fromisoformat(last_login_str.replace('Z', '+00:00'))
                        else:
                            self.last_login = datetime.fromisoformat(last_login_str)
                            self.last_login = self.last_login.replace(tzinfo=self.tz)
            except Exception as e:
                print(f"Warning: Could not load state: {e}")
        
        # Load exclusion domains
        if os.path.exists(self.exclusion_file):
            try:
                with open(self.exclusion_file, 'r') as f:
                    exclusions = json.load(f)
                    self.exclusion_domains = exclusions.get('domains', [])
            except Exception as e:
                print(f"Warning: Could not load exclusions: {e}")
    
    def _save_state(self):
        """Save assistant state."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump({
                    'last_login': datetime.now(self.tz).isoformat()
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save state: {e}")
    
    def _save_exclusions(self):
        """Save exclusion domains list."""
        try:
            with open(self.exclusion_file, 'w') as f:
                json.dump({
                    'domains': self.exclusion_domains
                }, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save exclusions: {e}")
    
    def _update_last_login(self):
        """Update last login timestamp."""
        self.last_login = datetime.now(self.tz)
        self._save_state()
    
    def add_exclusion_domain(self, domain: str) -> bool:
        """Add a domain to the exclusion list."""
        domain = domain.lower().strip()
        if domain and domain not in self.exclusion_domains:
            self.exclusion_domains.append(domain)
            self._save_exclusions()
            return True
        return False
    
    def remove_exclusion_domain(self, domain: str) -> bool:
        """Remove a domain from the exclusion list."""
        domain = domain.lower().strip()
        if domain in self.exclusion_domains:
            self.exclusion_domains.remove(domain)
            self._save_exclusions()
            return True
        return False
    
    def get_exclusion_domains(self) -> List[str]:
        """Get list of excluded domains."""
        return self.exclusion_domains.copy()
    
    def _get_current_time_context(self) -> str:
        """Get detailed current time context to help Claude with date calculations."""
        now = datetime.now(self.tz)
        
        # Calculate this week's dates
        days_of_week = []
        for i in range(7):
            day = now + timedelta(days=i)
            day_name = day.strftime('%A')
            day_date = day.strftime('%Y-%m-%d')
            days_of_week.append(f"{day_name} = {day_date}")
        
        return f"""Current date/time: {now.strftime('%A, %B %d, %Y at %I:%M %p')} Eastern Time
Today's date: {now.strftime('%Y-%m-%d')} ({now.strftime('%A')})

This week's dates for reference:
{chr(10).join(days_of_week)}

IMPORTANT: When the user says "this Thursday", they mean {(now + timedelta(days=(3 - now.weekday()) % 7)).strftime('%A, %B %d, %Y')} (the Thursday of this current week).
All times should be interpreted as Eastern Time unless otherwise specified."""
    
    def _check_priority_conflicts(self, start: datetime, end: datetime) -> list:
        """Check if there are priority conflicts."""
        conflicts = self.google.check_conflicts(start, end)
        priority_conflicts = []
        
        for event in conflicts:
            summary = event.get('summary', '').lower()
            if any(keyword in summary for keyword in PRIORITY_KEYWORDS):
                priority_conflicts.append(event)
        
        return priority_conflicts
    
    def _build_tools(self) -> list:
        """Define tools available to Claude."""
        return [
            {
                "name": "get_calendar_events",
                "description": "Get calendar events for the next N days",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {
                            "type": "integer",
                            "description": "Number of days to look ahead (default 7)"
                        }
                    }
                }
            },
            {
                "name": "find_free_times",
                "description": "Find available time slots in the calendar",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "days_ahead": {
                            "type": "integer",
                            "description": "Number of days to search (default 7)"
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Required slot duration in minutes (default 60)"
                        }
                    }
                }
            },
            {
                "name": "create_calendar_event",
                "description": "Create a new calendar event. IMPORTANT: Use the exact date from the reference dates provided. All times are in Eastern Time.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "summary": {"type": "string", "description": "Event title"},
                        "start_time": {
                            "type": "string", 
                            "description": "Start time in ISO format with timezone, e.g., '2026-01-08T20:30:00-05:00' for 8:30 PM ET. MUST include the -05:00 (EST) or -04:00 (EDT) offset."
                        },
                        "duration_minutes": {"type": "integer", "description": "Event duration in minutes"},
                        "description": {"type": "string", "description": "Event description (optional)"},
                        "location": {"type": "string", "description": "Event location (optional)"}
                    },
                    "required": ["summary", "start_time", "duration_minutes"]
                }
            },
            {
                "name": "search_emails",
                "description": "Search emails for scheduling-related content",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query for emails"}
                    }
                }
            },
            {
                "name": "check_conflicts",
                "description": "Check if a proposed time has conflicts, especially with priority events",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "start_time": {"type": "string", "description": "Start time in ISO format with timezone offset"},
                        "end_time": {"type": "string", "description": "End time in ISO format with timezone offset"}
                    },
                    "required": ["start_time", "end_time"]
                }
            },
            {
                "name": "find_event",
                "description": "Search for calendar events by name/keyword. Use this to find an event before deleting it.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "search_term": {
                            "type": "string",
                            "description": "The name or keyword to search for in event titles"
                        },
                        "days_ahead": {
                            "type": "integer",
                            "description": "Number of days to search ahead (default 30)"
                        }
                    },
                    "required": ["search_term"]
                }
            },
            {
                "name": "delete_event",
                "description": "Delete a calendar event by its ID. Always use find_event first to get the correct event ID, and confirm with the user before deleting.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "event_id": {
                            "type": "string",
                            "description": "The unique ID of the event to delete"
                        },
                        "event_summary": {
                            "type": "string",
                            "description": "The name of the event (for confirmation logging)"
                        }
                    },
                    "required": ["event_id"]
                }
            },
            {
                "name": "get_new_emails_since_login",
                "description": "Get new emails received since the last login. Only includes emails from primary mailbox, excluding promotional/marketing emails.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of emails to return (default 20)"
                        }
                    }
                }
            },
            {
                "name": "add_exclusion_domain",
                "description": "Add a domain or URL to the exclusion list to filter out promotional emails from that sender.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain name or URL to exclude (e.g., 'example.com' or 'newsletter.example.com')"
                        }
                    },
                    "required": ["domain"]
                }
            },
            {
                "name": "remove_exclusion_domain",
                "description": "Remove a domain from the exclusion list.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "domain": {
                            "type": "string",
                            "description": "Domain name to remove from exclusion list"
                        }
                    },
                    "required": ["domain"]
                }
            },
            {
                "name": "get_exclusion_domains",
                "description": "Get the list of excluded domains/URLs.",
                "input_schema": {
                    "type": "object",
                    "properties": {}
                }
            },
            {
                "name": "get_top_reddit_posts",
                "description": "Get the top hottest posts from Reddit subreddits the user is subscribed to.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Number of top posts to return (default 10)"
                        },
                        "time_filter": {
                            "type": "string",
                            "description": "Time period: 'hour', 'day', 'week', 'month', 'year', 'all' (default 'day')",
                            "enum": ["hour", "day", "week", "month", "year", "all"]
                        }
                    }
                }
            },
            {
                "name": "get_top_news",
                "description": "Get top news articles for a specific topic. Topics include: general, business, marketing, stocks, technology, sports, entertainment, health, science.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "News topic: 'general', 'business', 'marketing', 'stocks', 'technology', 'sports', 'entertainment', 'health', 'science' (default: 'general')"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Number of articles to return (default 5)"
                        }
                    }
                }
            }
        ]
    
    def _execute_tool(self, tool_name: str, tool_input: dict) -> str:
        """Execute a tool and return the result."""
        try:
            if tool_name == "get_calendar_events":
                days = tool_input.get("days_ahead", 7)
                events = self.google.get_events(days_ahead=days)
                return json.dumps(events, default=str)
            
            elif tool_name == "find_free_times":
                days = tool_input.get("days_ahead", 7)
                duration = tool_input.get("duration_minutes", 60)
                slots = self.google.find_free_slots(days_ahead=days, slot_duration_minutes=duration)
                return json.dumps(slots[:10])  # Return top 10 slots
            
            elif tool_name == "create_calendar_event":
                # Parse the start time - handle timezone properly
                start_str = tool_input["start_time"]
                
                # Parse ISO format with timezone
                if '+' in start_str or start_str.count('-') > 2:
                    start = datetime.fromisoformat(start_str)
                else:
                    # No timezone provided, assume Eastern
                    start = datetime.fromisoformat(start_str)
                    start = start.replace(tzinfo=self.tz)
                
                # Ensure it's in Eastern time
                start = start.astimezone(self.tz)
                end = start + timedelta(minutes=tool_input["duration_minutes"])
                
                # Log for debugging
                print(f"DEBUG: Creating event at {start.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
                
                # Check for priority conflicts first
                priority_conflicts = self._check_priority_conflicts(start, end)
                if priority_conflicts:
                    conflict_info = [{"summary": e.get("summary"), "start": e["start"]} for e in priority_conflicts]
                    return json.dumps({
                        "warning": "PRIORITY CONFLICT DETECTED",
                        "conflicts": conflict_info,
                        "message": "This time conflicts with important events. Consider rescheduling."
                    })
                
                event = self.google.create_event(
                    summary=tool_input["summary"],
                    start=start,
                    end=end,
                    description=tool_input.get("description", ""),
                    location=tool_input.get("location", "")
                )
                return json.dumps({
                    "success": True, 
                    "event_id": event["id"], 
                    "link": event.get("htmlLink"),
                    "scheduled_for": start.strftime('%A, %B %d, %Y at %I:%M %p %Z')
                })
            
            elif tool_name == "search_emails":
                query = tool_input.get("query", "")
                emails = self.google.get_recent_emails(query=query)
                return json.dumps(emails)
            
            elif tool_name == "check_conflicts":
                start = datetime.fromisoformat(tool_input["start_time"])
                end = datetime.fromisoformat(tool_input["end_time"])
                
                # Ensure timezone
                if start.tzinfo is None:
                    start = start.replace(tzinfo=self.tz)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=self.tz)
                
                conflicts = self.google.check_conflicts(start, end)
                priority = self._check_priority_conflicts(start, end)
                return json.dumps({
                    "has_conflicts": len(conflicts) > 0,
                    "conflicts": conflicts,
                    "has_priority_conflicts": len(priority) > 0,
                    "priority_conflicts": priority
                }, default=str)
            
            elif tool_name == "find_event":
                search_term = tool_input["search_term"]
                days_ahead = tool_input.get("days_ahead", 30)
                events = self.google.find_event_by_name(search_term, days_ahead)
                
                # Format events for easier reading
                formatted_events = []
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    formatted_events.append({
                        "id": event['id'],
                        "summary": event.get('summary', 'No title'),
                        "start": start,
                        "description": event.get('description', '')[:100] if event.get('description') else ''
                    })
                
                return json.dumps({
                    "found": len(formatted_events),
                    "events": formatted_events
                })
            
            elif tool_name == "delete_event":
                event_id = tool_input["event_id"]
                event_summary = tool_input.get("event_summary", "Unknown event")
                
                print(f"DEBUG: Deleting event '{event_summary}' (ID: {event_id})")
                
                success = self.google.delete_event(event_id)
                
                if success:
                    return json.dumps({
                        "success": True,
                        "message": f"Successfully deleted event: {event_summary}"
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "message": f"Failed to delete event: {event_summary}. It may have already been deleted or the ID is invalid."
                    })
            
            elif tool_name == "get_new_emails_since_login":
                max_results = tool_input.get("max_results", 20)
                
                # Use previous_login if available (before this session), otherwise use last_login
                since_date = getattr(self, 'previous_login', None) or self.last_login
                
                if since_date is None:
                    # If no previous login, get emails from last 24 hours
                    since_date = datetime.now(self.tz) - timedelta(days=1)
                
                emails = self.google.get_emails_since(
                    since_date=since_date,
                    max_results=max_results,
                    exclude_promotional=True,
                    exclusion_domains=self.exclusion_domains
                )
                
                return json.dumps({
                    "count": len(emails),
                    "since": since_date.isoformat(),
                    "emails": emails
                }, default=str)
            
            elif tool_name == "add_exclusion_domain":
                domain = tool_input["domain"]
                success = self.add_exclusion_domain(domain)
                
                if success:
                    return json.dumps({
                        "success": True,
                        "message": f"Added '{domain}' to exclusion list",
                        "excluded_domains": self.get_exclusion_domains()
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "message": f"Domain '{domain}' is already in exclusion list or invalid"
                    })
            
            elif tool_name == "remove_exclusion_domain":
                domain = tool_input["domain"]
                success = self.remove_exclusion_domain(domain)
                
                if success:
                    return json.dumps({
                        "success": True,
                        "message": f"Removed '{domain}' from exclusion list",
                        "excluded_domains": self.get_exclusion_domains()
                    })
                else:
                    return json.dumps({
                        "success": False,
                        "message": f"Domain '{domain}' not found in exclusion list"
                    })
            
            elif tool_name == "get_exclusion_domains":
                domains = self.get_exclusion_domains()
                return json.dumps({
                    "count": len(domains),
                    "domains": domains
                })
            
            elif tool_name == "get_top_reddit_posts":
                if not self.reddit:
                    return json.dumps({
                        "error": "Reddit services not available. Please set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env file."
                    })
                
                limit = tool_input.get("limit", 10)
                time_filter = tool_input.get("time_filter", "day")
                
                try:
                    posts = self.reddit.get_top_posts_from_my_subreddits(
                        time_filter=time_filter,
                        total_limit=limit
                    )
                    
                    return json.dumps({
                        "count": len(posts),
                        "time_filter": time_filter,
                        "posts": posts
                    }, default=str)
                except Exception as e:
                    return json.dumps({
                        "error": f"Failed to fetch Reddit posts: {str(e)}"
                    })
            
            elif tool_name == "get_top_news":
                if not self.news:
                    return json.dumps({
                        "error": "News services not available. Please set NEWS_API_KEY in .env file or install feedparser for RSS feeds."
                    })
                
                topic = tool_input.get("topic", "general")
                limit = tool_input.get("limit", 5)
                
                try:
                    articles = self.news.get_news_by_topic(topic=topic, limit=limit)
                    
                    return json.dumps({
                        "count": len(articles),
                        "topic": topic,
                        "articles": articles
                    }, default=str)
                except Exception as e:
                    return json.dumps({
                        "error": f"Failed to fetch news: {str(e)}"
                    })
            
            return json.dumps({"error": f"Unknown tool: {tool_name}"})
        
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    def chat(self, user_message: str) -> str:
        """Process a user message and return a response."""
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })
        
        time_context = self._get_current_time_context()
        
        system_prompt = f"""You are an executive assistant with access to the user's Gmail, Google Calendar, Reddit, and News feeds.
Your job is to help manage their schedule efficiently and keep them informed.

{time_context}

CRITICAL DATE HANDLING:
- Use the reference dates above to determine the correct date for any day mentioned
- "This Thursday" means the Thursday shown in the reference dates above
- Always use ISO format with timezone offset: YYYY-MM-DDTHH:MM:SS-05:00 (for EST) or -04:00 (for EDT)
- Currently we are in EST (Eastern Standard Time), so use -05:00
- Double-check the date before creating any event

Key responsibilities:
1. Schedule events based on natural language requests
2. Find free times when asked
3. Check emails for scheduling requests and suggest times
4. ALWAYS flag conflicts with important events (interviews, deadlines, presentations)
5. Suggest alternative times when conflicts exist
6. Delete events when requested
7. Provide email updates since last login (automatically on startup)
8. Manage exclusion list for filtering promotional emails
9. Show top Reddit posts from subscribed subreddits (automatically on startup)
10. Show top news articles by topic (automatically on startup with general news)

DELETING EVENTS:
- When the user asks to delete/remove/cancel an event, first use find_event to search for it
- If multiple events match, list them and ask the user to confirm which one to delete
- Always confirm the event details (name and date/time) before deleting
- Use the event ID from find_event to delete the correct event

Priority keywords to watch for: {', '.join(PRIORITY_KEYWORDS)}

When creating events:
1. First, determine the correct date using the reference dates provided
2. Check for conflicts
3. Create the event with the EXACT date from the reference
4. Confirm the day and date with the user in your response"""

        # Initial API call
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            tools=self._build_tools(),
            messages=self.conversation_history
        )
        
        # Handle tool use in a loop
        while response.stop_reason == "tool_use":
            tool_results = []
            assistant_content = response.content
            
            for block in response.content:
                if block.type == "tool_use":
                    print(f"DEBUG: Tool called: {block.name}")
                    print(f"DEBUG: Tool input: {json.dumps(block.input, indent=2)}")
                    result = self._execute_tool(block.name, block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result
                    })
            
            # Add assistant's response and tool results to history
            self.conversation_history.append({
                "role": "assistant",
                "content": assistant_content
            })
            self.conversation_history.append({
                "role": "user",
                "content": tool_results
            })
            
            # Get next response
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=self._build_tools(),
                messages=self.conversation_history
            )
        
        # Extract final text response
        final_response = ""
        for block in response.content:
            if hasattr(block, "text"):
                final_response += block.text
        
        self.conversation_history.append({
            "role": "assistant",
            "content": response.content
        })
        
        return final_response


def main():
    """Run the assistant in interactive mode."""
    print("=" * 50)
    print("🤖 Executive Assistant")
    print("=" * 50)
    
    try:
        print("Initializing...")
        assistant = ExecutiveAssistant()
        
        # Show current time for verification
        tz = ZoneInfo(DEFAULT_TIMEZONE)
        now = datetime.now(tz)
        print(f"✅ Connected to Gmail and Calendar")
        print(f"✅ Connected to Claude API")
        print(f"📅 Current time: {now.strftime('%A, %B %d, %Y at %I:%M %p %Z')}")
        print("=" * 50)
        
        # Show email updates since last login
        if assistant.previous_login:
            time_since = now - assistant.previous_login
            if time_since.total_seconds() > 60:  # Only show if more than 1 minute since last login
                print("\n📧 Checking for new emails since last login...")
                try:
                    email_response = assistant.chat("Show me new emails since I last logged in. Only show emails from my primary mailbox, excluding promotional and marketing emails.")
                    print(f"\n{email_response}\n")
                except Exception as e:
                    print(f"⚠️  Could not fetch email updates: {e}\n")
        else:
            print("\n📧 This is your first login. Checking recent emails...")
            try:
                email_response = assistant.chat("Show me my recent emails from the primary mailbox, excluding promotional and marketing emails.")
                print(f"\n{email_response}\n")
            except Exception as e:
                print(f"⚠️  Could not fetch email updates: {e}\n")
        
        # Show top Reddit posts
        if assistant.reddit:
            print("🔴 Fetching top Reddit posts from your subscribed subreddits...")
            try:
                reddit_response = assistant.chat("Show me the top 10 hottest posts from Reddit subreddits I'm subscribed to. Format them nicely with title, subreddit, upvotes, and link.")
                print(f"\n{reddit_response}\n")
            except Exception as e:
                print(f"⚠️  Could not fetch Reddit posts: {e}\n")
        else:
            print("ℹ️  Reddit integration not configured. Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in .env to enable.")
        
        # Show top news articles
        if assistant.news:
            print("📰 Fetching top news articles...")
            try:
                news_response = assistant.chat("Show me the top 5 news articles for general/current events. Format them nicely with title, source, description, and link.")
                print(f"\n{news_response}\n")
            except Exception as e:
                print(f"⚠️  Could not fetch news: {e}\n")
        else:
            print("ℹ️  News integration not configured. Set NEWS_API_KEY in .env to enable NewsAPI, or install feedparser for RSS feeds.")
        
        print("=" * 50)
        print("\nHow to use:")
        print("  • Type naturally: 'Schedule lunch Tuesday at noon'")
        print("  • Ask questions: 'When am I free this week?'")
        print("  • Email updates: 'Show me new emails' or 'What emails do I have?'")
        print("  • Reddit posts: 'Show me top Reddit posts'")
        print("  • News articles: 'Show me top news about business' or 'Get marketing news'")
        print("  • Manage exclusions: 'Add example.com to exclusion list'")
        print("  • Type 'quit' to exit")
        print("  • Type 'clear' to reset conversation")
        print("=" * 50 + "\n")
        
        while True:
            try:
                user_input = input("You: ").strip()
            except EOFError:
                break
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("Goodbye! 👋")
                break
            
            if user_input.lower() == 'clear':
                assistant.conversation_history = []
                print("✅ Conversation cleared.\n")
                continue
            
            print("\nThinking...\n")
            response = assistant.chat(user_input)
            print(f"Assistant: {response}\n")
    
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()