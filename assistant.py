# assistant.py
import os
import json
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
import anthropic
from google_services import GoogleServices

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
        
        system_prompt = f"""You are an executive assistant with access to the user's Gmail and Google Calendar.
Your job is to help manage their schedule efficiently.

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
        print("\nHow to use:")
        print("  • Type naturally: 'Schedule lunch Tuesday at noon'")
        print("  • Ask questions: 'When am I free this week?'")
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