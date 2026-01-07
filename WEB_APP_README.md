# Web Application Guide

The Executive Assistant now includes a beautiful web interface!

## Running the Web Application

1. **Activate your virtual environment:**
   ```bash
   cd Executive-Assistant
   source venv/bin/activate
   ```

2. **Install dependencies (if not already installed):**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Flask app:**
   ```bash
   python app.py
   ```

4. **Open your browser:**
   Navigate to `http://localhost:5000`

## Features

### 1. General Questions
- Chat interface to ask questions about your schedule, emails, etc.
- Can modify calendar or send emails through natural language
- Example: "Schedule lunch Tuesday at noon" or "When am I free this week?"

### 2. Upcoming Calendar Invites
- Shows next 10 calendar events
- Priority events (interviews, deadlines, etc.) are highlighted in bold/red
- Click "Open in Calendar" to view event in Google Calendar

### 3. Email Updates
- Shows recent emails since last login
- Filters out promotional emails
- Click "Open in Gmail" to view email
- "Manage Exclusions" button to add/remove email exclusion domains

### 4. News Updates
- Shows top 5 news articles
- Toggle buttons for different categories:
  - General (default)
  - Business
  - Marketing
  - Stocks
  - Technology

### 5. Reddit Updates
- Shows top 5 Reddit posts from your subscribed subreddits
- If Reddit API not configured, shows trending posts from r/popular
- Click to view post on Reddit

## Configuration

Make sure your `.env` file contains:
- `ANTHROPIC_API_KEY` - Required for chat functionality
- `NEWS_API_KEY` - Optional, for news features (falls back to RSS if not set)
- `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET` - Optional, for Reddit features
- `FLASK_SECRET_KEY` - Optional, for session management (auto-generated if not set)

## Troubleshooting

- **Port already in use**: Change the port in `app.py` (last line: `port=5000`)
- **Assistant not initializing**: Check that all required API keys are in `.env`
- **No data showing**: Check browser console for errors and ensure backend is running

## Development

The web app uses:
- **Backend**: Flask (Python)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **API**: RESTful endpoints under `/api/*`

To modify:
- **Templates**: `templates/index.html`
- **Styles**: `static/css/style.css`
- **JavaScript**: `static/js/app.js`
- **API Routes**: `app.py`

