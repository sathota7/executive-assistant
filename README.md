# Executive Assistant

An AI-powered executive assistant that manages Google Calendar and Gmail using Claude (Anthropic). It helps you schedule events, find free times, check for conflicts, and manage your calendar through natural language conversations.

Executive assistant capable of managing google calendar, reading gmail schedule requests, prioritizing conflicting calendar holds, and holding daily-to-do list.

## Features

- 📅 **Calendar Management**: Create, delete, and search calendar events using natural language
- 🔍 **Free Time Finder**: Automatically find available time slots in your schedule
- ⚠️ **Conflict Detection**: Flags conflicts with important events (interviews, deadlines, presentations, etc.)
- 📧 **Email Integration**: Search Gmail for scheduling-related content and get updates since last login
- 🔴 **Reddit Integration**: Get top hottest posts from your subscribed subreddits
- 📰 **News Feed**: Get top news articles by topic (business, marketing, stocks, technology, etc.)
- 💬 **Natural Language Processing**: Chat with the assistant using plain English

## Setup

### Prerequisites

- Python 3.8+
- Google account with Calendar and Gmail access
- Anthropic API key
- Reddit API credentials (optional, for Reddit features)

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
   - (Optional) Add Reddit API credentials for Reddit features:
   ```
   REDDIT_CLIENT_ID=your-client-id
   REDDIT_CLIENT_SECRET=your-client-secret
   REDDIT_USER_AGENT=YourAppName/1.0 by YourUsername
   REDDIT_USERNAME=your-username (optional, for authenticated access)
   REDDIT_PASSWORD=your-password (optional, for authenticated access)
   ```
   - (Optional) Add News API key for news features:
   ```
   NEWS_API_KEY=your-news-api-key
   ```
   
   To get News API key:
   1. Go to https://newsapi.org/register
   2. Sign up for a free account (100 requests/day)
   3. Copy your API key from the dashboard
   
   **Note:** If you don't set NEWS_API_KEY, the assistant will use RSS feeds (no API key required, but requires feedparser).
   
   To get Reddit API credentials:
   
   **For CLI/Desktop App (current setup):**
   1. Go to https://www.reddit.com/prefs/apps
   2. Click "create another app..." or "create app"
   3. Choose "script" as the app type
   4. Fill in name and description
   5. Copy the client ID (under the app name) and secret
   
   **For Web Application (recommended for web apps):**
   1. Go to https://www.reddit.com/prefs/apps
   2. Click "create another app..." or "create app"
   3. Choose "web app" as the app type
   4. Fill in name and description
   5. Set redirect URI to: `http://localhost:PORT/reddit/callback` (replace PORT with your app's port)
   6. Copy the client ID (under the app name) and secret
   7. Add to `.env`:
   ```
   REDDIT_REDIRECT_URI=http://localhost:5000/reddit/callback
   ```
   
   **Note:** For web apps, use OAuth flow (see `reddit_oauth.py` for implementation). 
   Username/password authentication is deprecated and not recommended for web applications.

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
- **Send emails**: "Send an email to john@example.com with subject 'Meeting' and body 'Let's meet tomorrow'"
- **Reddit posts**: "Show me top Reddit posts" or "What's hot on Reddit today?"
- **News articles**: "Show me top news about business" or "Get marketing news" or "What's the latest on stocks?"

Type `quit` to exit or `clear` to reset the conversation.

## Configuration

- Default timezone: `America/New_York` (Eastern Time)
- Work hours for free time search: 9 AM - 5 PM (weekdays only)
- Priority keywords: interview, deadline, presentation, meeting with ceo, board meeting, final, urgent, important, review, submission, due date, exam, flight, doctor

## Files

- `assistant.py` - Main assistant class and CLI interface
- `google_services.py` - Google Calendar and Gmail API wrapper
- `reddit_services.py` - Reddit API wrapper for fetching posts
- `reddit_oauth.py` - Reddit OAuth helper for web applications
- `news_services.py` - News API wrapper (NewsAPI and RSS feeds)
- `background_monitor.py` - Background monitoring (future feature)
- `config.yaml` - Configuration file
- `requirements.txt` - Python dependencies
- `WEB_APP_SETUP.md` - Guide for setting up Reddit OAuth in web applications

## Security

⚠️ **Important**: Never commit sensitive files to version control:
- `.env` (contains API keys)
- `token.json` (OAuth tokens)
- `credentials.json` (OAuth credentials)

These files are already in `.gitignore`.

## License

MIT License
