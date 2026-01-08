# app.py
"""
Flask web application for Executive Assistant
"""
from flask import Flask, render_template, request, jsonify, session
from flask_cors import CORS
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import json
import os
from assistant import ExecutiveAssistant

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', os.urandom(24).hex())
CORS(app)

# Initialize assistant (shared instance)
assistant = None

def get_assistant():
    """Get or create assistant instance"""
    global assistant
    if assistant is None:
        try:
            assistant = ExecutiveAssistant()
        except Exception as e:
            print(f"Error initializing assistant: {e}")
            return None
    return assistant

@app.route('/')
def index():
    """Home page"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """Handle chat messages"""
    data = request.json
    message = data.get('message', '')
    
    if not message:
        return jsonify({'error': 'No message provided'}), 400
    
    assistant = get_assistant()
    if not assistant:
        return jsonify({'error': 'Assistant not initialized'}), 500
    
    try:
        response = assistant.chat(message)
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/calendar/upcoming', methods=['GET'])
def get_upcoming_calendar():
    """Get upcoming calendar events - exactly 10 events"""
    assistant = get_assistant()
    if not assistant:
        return jsonify({'error': 'Assistant not initialized'}), 500
    
    try:
        events = assistant.google.get_events(days_ahead=60)  # Get more to ensure we have 10
        
        # Sort by start time and get exactly next 10
        upcoming_events = []
        now = datetime.now(assistant.tz)
        
        for event in events:
            start_str = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
            if not start_str:
                continue
            
            try:
                if 'T' in start_str:
                    start = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                else:
                    start = datetime.fromisoformat(start_str)
                    start = start.replace(tzinfo=assistant.tz)
                
                if start >= now:
                    # Check if priority
                    from assistant import PRIORITY_KEYWORDS
                    summary = event.get('summary', '').lower()
                    is_priority = any(keyword in summary for keyword in PRIORITY_KEYWORDS)
                    
                    upcoming_events.append({
                        'id': event.get('id'),
                        'title': event.get('summary', 'No title'),
                        'start': start.isoformat(),
                        'start_display': start.strftime('%A, %B %d at %I:%M %p'),
                        'location': event.get('location', ''),
                        'description': event.get('description', ''),
                        'htmlLink': event.get('htmlLink', ''),
                        'is_priority': is_priority
                    })
            except Exception as e:
                continue
        
        # Sort by start time and take exactly 10
        upcoming_events.sort(key=lambda x: x['start'])
        upcoming_events = upcoming_events[:10]
        
        return jsonify({'events': upcoming_events})  # Return exactly 10 or less
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/recent', methods=['GET'])
def get_recent_emails():
    """Get recent emails"""
    assistant = get_assistant()
    if not assistant:
        return jsonify({'error': 'Assistant not initialized'}), 500
    
    try:
        # Get emails since last login or last 24 hours
        since_date = getattr(assistant, 'previous_login', None)
        if not since_date:
            since_date = datetime.now(assistant.tz) - timedelta(days=1)
        
        emails = assistant.google.get_emails_since(
            since_date=since_date,
            max_results=20,
            exclude_promotional=True,
            exclusion_domains=assistant.exclusion_domains,
            inbound_only=True  # Only show inbound emails
        )
        
        # Format for display and prioritize response-requested emails
        email_list = []
        response_required = []
        regular_emails = []
        
        for email in emails:
            email_item = {
                'id': email.get('id'),
                'from': email.get('from', ''),
                'subject': email.get('subject', 'No subject'),
                'snippet': email.get('snippet', ''),
                'date': email.get('date', ''),
                'requires_response': email.get('requires_response', False),
                'gmail_link': f"https://mail.google.com/mail/u/0/#inbox/{email.get('id')}"
            }
            
            if email_item['requires_response']:
                response_required.append(email_item)
            else:
                regular_emails.append(email_item)
        
        # Sort: response-required emails first, then regular emails
        email_list = response_required + regular_emails
        email_list = email_list[:10]  # Limit to 10 total
        
        return jsonify({'emails': email_list})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/emails/exclusions', methods=['GET', 'POST', 'DELETE'])
def manage_exclusions():
    """Manage email exclusion domains"""
    assistant = get_assistant()
    if not assistant:
        return jsonify({'error': 'Assistant not initialized'}), 500
    
    if request.method == 'GET':
        return jsonify({'exclusions': assistant.get_exclusion_domains()})
    
    elif request.method == 'POST':
        data = request.json
        domain = data.get('domain', '').strip()
        if domain:
            success = assistant.add_exclusion_domain(domain)
            if success:
                return jsonify({'success': True, 'message': f'Added {domain}'})
            return jsonify({'success': False, 'message': 'Domain already exists'}), 400
        return jsonify({'error': 'No domain provided'}), 400
    
    elif request.method == 'DELETE':
        data = request.json
        domain = data.get('domain', '').strip()
        if domain:
            success = assistant.remove_exclusion_domain(domain)
            if success:
                return jsonify({'success': True, 'message': f'Removed {domain}'})
            return jsonify({'success': False, 'message': 'Domain not found'}), 404
        return jsonify({'error': 'No domain provided'}), 400

@app.route('/api/news', methods=['GET'])
def get_news():
    """Get news articles by topic"""
    topic = request.args.get('topic', 'general')
    limit = int(request.args.get('limit', 20))  # Default to 20 for queue (10 displayed + buffer)
    
    assistant = get_assistant()
    if not assistant or not assistant.news:
        return jsonify({'error': 'News service not available'}), 500
    
    try:
        articles = assistant.news.get_news_by_topic(topic=topic, limit=limit)
        return jsonify({'articles': articles, 'topic': topic})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/reddit', methods=['GET'])
def get_reddit_posts():
    """Get Reddit posts"""
    limit = int(request.args.get('limit', 5))
    
    assistant = get_assistant()
    if not assistant:
        return jsonify({'error': 'Assistant not initialized'}), 500
    
    try:
        if assistant.reddit:
            # Try to get from subscribed subreddits
            posts = assistant.reddit.get_top_posts_from_my_subreddits(
                time_filter='day',
                total_limit=limit
            )
        else:
            # Fallback to popular/trending
            try:
                import praw
                from dotenv import load_dotenv
                import os
                load_dotenv()
                
                reddit = praw.Reddit(
                    client_id=os.getenv('REDDIT_CLIENT_ID', ''),
                    client_secret=os.getenv('REDDIT_CLIENT_SECRET', ''),
                    user_agent=os.getenv('REDDIT_USER_AGENT', 'ExecutiveAssistant/1.0')
                )
                
                posts = []
                for post in reddit.subreddit('popular').hot(limit=limit):
                    posts.append({
                        'title': post.title,
                        'score': post.score,
                        'subreddit': post.subreddit.display_name,
                        'url': post.url,
                        'permalink': f"https://reddit.com{post.permalink}",
                        'num_comments': post.num_comments
                    })
            except Exception as e:
                return jsonify({'error': f'Reddit not available: {str(e)}'}), 500
        
        return jsonify({'posts': posts})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)

