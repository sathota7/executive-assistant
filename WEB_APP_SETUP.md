# Web Application Setup Guide

This guide explains how to set up Reddit OAuth for a locally hosted web application.

## Reddit API Setup for Web Apps

### Step 1: Create Reddit App

1. Go to https://www.reddit.com/prefs/apps
2. Click **"create another app..."** or **"create app"**
3. Choose **"web app"** as the app type (NOT "script")
4. Fill in:
   - **Name**: Your app name (e.g., "Executive Assistant")
   - **Description**: Brief description
   - **Redirect URI**: `http://localhost:5000/reddit/callback` (adjust port as needed)
5. Click **"create app"**
6. Copy:
   - **Client ID** (the string under your app name)
   - **Secret** (the "secret" field)

### Step 2: Environment Variables

Add to your `.env` file:

```bash
REDDIT_CLIENT_ID=your-client-id-here
REDDIT_CLIENT_SECRET=your-client-secret-here
REDDIT_REDIRECT_URI=http://localhost:5000/reddit/callback
REDDIT_USER_AGENT=ExecutiveAssistant/1.0 by YourUsername
```

### Step 3: Install Flask (if not already installed)

```bash
pip install flask
```

Add to `requirements.txt`:
```
flask>=2.0.0
```

### Step 4: Implement OAuth Flow

Use the `reddit_oauth.py` helper or implement your own OAuth flow:

```python
from flask import Flask, session, redirect, url_for, request
from reddit_oauth import get_reddit_oauth_url, handle_reddit_callback
from reddit_services import RedditServices
import secrets

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Use a secure random key in production

@app.route('/reddit/auth')
def reddit_auth():
    """Initiate Reddit OAuth flow"""
    state = secrets.token_urlsafe(32)
    session['reddit_oauth_state'] = state
    
    auth_url = get_reddit_oauth_url(state)
    return redirect(auth_url)

@app.route('/reddit/callback')
def reddit_callback():
    """Handle Reddit OAuth callback"""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    
    if error:
        return f"Reddit OAuth error: {error}", 400
    
    # Verify state
    if state != session.get('reddit_oauth_state'):
        return "Invalid state parameter", 400
    
    # Exchange code for tokens
    token_data = handle_reddit_callback(code, state)
    
    # Store tokens in session (or database for persistence)
    session['reddit_access_token'] = token_data['access_token']
    session['reddit_refresh_token'] = token_data['refresh_token']
    session['reddit_username'] = token_data['username']
    
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    """Example dashboard that uses Reddit services"""
    # Get tokens from session
    access_token = session.get('reddit_access_token')
    refresh_token = session.get('reddit_refresh_token')
    
    if not access_token:
        return redirect(url_for('reddit_auth'))
    
    # Initialize Reddit services with OAuth tokens
    reddit = RedditServices(
        access_token=access_token,
        refresh_token=refresh_token
    )
    
    # Get top posts
    posts = reddit.get_top_posts_from_my_subreddits(total_limit=10)
    
    return f"<h1>Top Reddit Posts</h1><pre>{posts}</pre>"
```

## Key Differences: Script vs Web App

| Feature | Script Type | Web App Type |
|---------|-------------|--------------|
| **Use Case** | CLI/Desktop apps | Web applications |
| **Authentication** | Username/password (deprecated) | OAuth flow |
| **Redirect URI** | Not needed | Required |
| **Security** | Less secure | More secure |
| **User Experience** | Requires credentials in .env | User logs in via browser |

## Security Notes

1. **Never commit tokens**: Store OAuth tokens in session or database, not in code
2. **Use HTTPS in production**: OAuth requires secure connections
3. **Validate state parameter**: Always verify the state to prevent CSRF attacks
4. **Token expiration**: Handle token refresh when tokens expire
5. **Secret key**: Use a strong, random secret key for Flask sessions

## Testing Locally

1. Start your Flask app: `python app.py`
2. Navigate to: `http://localhost:5000/reddit/auth`
3. You'll be redirected to Reddit to authorize
4. After authorization, you'll be redirected back with tokens
5. Tokens are stored in session and can be used for API calls

## Troubleshooting

- **"Invalid redirect URI"**: Make sure the redirect URI in Reddit app settings exactly matches `REDDIT_REDIRECT_URI` in your `.env`
- **"Invalid client"**: Double-check your `REDDIT_CLIENT_ID` and `REDDIT_CLIENT_SECRET`
- **Tokens not persisting**: Consider storing tokens in a database instead of session for better persistence

