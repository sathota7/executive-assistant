# Executive Assistant

An AI-powered executive assistant that manages Google Calendar and Gmail using Claude (Anthropic). It helps you schedule events, find free times, check for conflicts, and manage your calendar through natural language conversations.

## Features

- 📅 **Calendar Management**: Create, delete, and search calendar events using natural language
- 🔍 **Free Time Finder**: Automatically find available time slots in your schedule
- ⚠️ **Conflict Detection**: Flags conflicts with important events (interviews, deadlines, presentations, etc.)
- 📧 **Email Integration**: Search Gmail for scheduling-related content
- 💬 **Natural Language Processing**: Chat with the assistant using plain English

## Setup

### Prerequisites

- Python 3.8+
- Google account with Calendar and Gmail access
- Anthropic API key

### Installation

1. Clone this repository:
```bash
git clone https://github.com/sathota7/executive-assistant.git
cd executive-assistant
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Set up Google OAuth:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one
   - Enable Google Calendar API and Gmail API
   - Create OAuth 2.0 credentials (Desktop app)
   - Download `credentials.json` and place it in the project directory

4. Set up environment variables:
   - Create a `.env` file in the project root
   - Add your Anthropic API key:
   ```
   ANTHROPIC_API_KEY=your-api-key-here
   ```

5. Run the assistant:
```bash
python assistant.py
```

On first run, you'll be prompted to authenticate with Google. This will create a `token.json` file for future sessions.

## Usage

Once running, you can interact with the assistant using natural language:

- **Schedule events**: "Schedule lunch Tuesday at noon"
- **Find free time**: "When am I free this week?"
- **Check conflicts**: "Do I have any conflicts on Thursday?"
- **Delete events**: "Cancel my meeting on Friday"
- **Search emails**: "Check my emails for scheduling requests"

Type `quit` to exit or `clear` to reset the conversation.

## Configuration

- Default timezone: `America/New_York` (Eastern Time)
- Work hours for free time search: 9 AM - 5 PM (weekdays only)
- Priority keywords: interview, deadline, presentation, meeting with ceo, board meeting, final, urgent, important, review, submission, due date, exam, flight, doctor

## Files

- `assistant.py` - Main assistant class and CLI interface
- `google_services.py` - Google Calendar and Gmail API wrapper
- `background_monitor.py` - Background monitoring (future feature)
- `config.yaml` - Configuration file
- `requirements.txt` - Python dependencies

## Security

⚠️ **Important**: Never commit sensitive files to version control:
- `.env` (contains API keys)
- `token.json` (OAuth tokens)
- `credentials.json` (OAuth credentials)

These files are already in `.gitignore`.

## License

MIT License

