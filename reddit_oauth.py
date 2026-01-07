# reddit_oauth.py
"""
OAuth helper for Reddit authentication in web applications.
Use this for locally hosted web apps instead of username/password.
"""
import os
import secrets
from flask import Flask, request, redirect, session, url_for
from dotenv import load_dotenv
import praw

load_dotenv()

# Reddit OAuth configuration
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_REDIRECT_URI = os.getenv('REDDIT_REDIRECT_URI', 'http://localhost:5000/reddit/callback')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT', 'ExecutiveAssistant/1.0 by YourUsername')

# OAuth scopes - adjust based on what you need
REDDIT_SCOPES = ['identity', 'read', 'mysubreddits']


def get_reddit_oauth_url(state: str) -> str:
    """
    Generate Reddit OAuth authorization URL.
    
    Args:
        state: Random state string for CSRF protection
        
    Returns:
        Authorization URL
    """
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        redirect_uri=REDDIT_REDIRECT_URI,
        user_agent=REDDIT_USER_AGENT
    )
    
    auth_url = reddit.auth.url(scopes=REDDIT_SCOPES, state=state, duration='permanent')
    return auth_url


def handle_reddit_callback(code: str, state: str) -> dict:
    """
    Exchange authorization code for access token.
    
    Args:
        code: Authorization code from Reddit
        state: State string (should match the one sent)
        
    Returns:
        Dictionary with access_token, refresh_token, and user info
    """
    reddit = praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        redirect_uri=REDDIT_REDIRECT_URI,
        user_agent=REDDIT_USER_AGENT
    )
    
    # Exchange code for tokens
    reddit.auth.authorize(code)
    
    # Get user info
    user = reddit.user.me()
    
    return {
        'access_token': reddit.auth.access_token,
        'refresh_token': reddit.auth.refresh_token,
        'username': user.name if user else None,
        'expires_in': reddit.auth.expires_in
    }


# Example Flask route integration:
"""
@app.route('/reddit/auth')
def reddit_auth():
    # Generate state for CSRF protection
    state = secrets.token_urlsafe(32)
    session['reddit_oauth_state'] = state
    
    # Get authorization URL
    auth_url = get_reddit_oauth_url(state)
    return redirect(auth_url)


@app.route('/reddit/callback')
def reddit_callback():
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
    
    # Store tokens in session or database
    session['reddit_access_token'] = token_data['access_token']
    session['reddit_refresh_token'] = token_data['refresh_token']
    
    return redirect(url_for('dashboard'))  # Redirect to your main page
"""

