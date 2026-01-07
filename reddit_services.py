# reddit_services.py
import os
from typing import List, Optional
from dotenv import load_dotenv
import praw

# Load environment variables
load_dotenv()


class RedditServices:
    def __init__(self, access_token: Optional[str] = None, refresh_token: Optional[str] = None):
        """
        Initialize Reddit API client.
        
        For CLI/script usage: Uses username/password or read-only access
        For web app usage: Uses OAuth access_token and refresh_token
        
        Args:
            access_token: OAuth access token (for web app authentication)
            refresh_token: OAuth refresh token (for web app authentication)
        """
        # Reddit API credentials from environment variables
        client_id = os.getenv('REDDIT_CLIENT_ID')
        client_secret = os.getenv('REDDIT_CLIENT_SECRET')
        user_agent = os.getenv('REDDIT_USER_AGENT', 'ExecutiveAssistant/1.0 by YourUsername')
        username = os.getenv('REDDIT_USERNAME')
        password = os.getenv('REDDIT_PASSWORD')
        
        if not all([client_id, client_secret]):
            raise ValueError(
                "Reddit API credentials not found. Please set in .env file:\n"
                "REDDIT_CLIENT_ID=your-client-id\n"
                "REDDIT_CLIENT_SECRET=your-client-secret\n"
                "REDDIT_USER_AGENT=YourAppName/1.0 by YourUsername\n"
                "\nFor CLI/script usage (optional):\n"
                "REDDIT_USERNAME=your-username\n"
                "REDDIT_PASSWORD=your-password\n"
                "\nFor web app usage:\n"
                "Use OAuth flow to get access_token and refresh_token"
            )
        
        # Initialize Reddit instance
        if access_token:
            # Web app OAuth flow
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                access_token=access_token,
                refresh_token=refresh_token
            )
        else:
            # CLI/script usage - username/password (deprecated but still works) or read-only
            self.reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent,
                username=username if username else None,
                password=password if password else None
            )
        
        # Verify connection
        try:
            if access_token or username:
                user = self.reddit.user.me()
                if user:
                    print(f"✅ Authenticated as Reddit user: {user.name}")
        except Exception as e:
            print(f"Warning: Reddit authentication issue: {e}")
            print("Continuing with read-only access...")
    
    def get_subscribed_subreddits(self, limit: int = 100) -> List[str]:
        """Get list of subreddits the user is subscribed to."""
        try:
            if self.reddit.user.me():
                # Authenticated user - get their subscriptions
                subreddits = []
                for subreddit in self.reddit.user.subreddits(limit=limit):
                    subreddits.append(subreddit.display_name)
                return subreddits
            else:
                # Not authenticated - return empty list or default subreddits
                return []
        except Exception as e:
            print(f"Error getting subscribed subreddits: {e}")
            return []
    
    def get_top_posts_from_subreddits(self, subreddit_names: List[str], 
                                      time_filter: str = 'day',
                                      limit_per_subreddit: int = 5,
                                      total_limit: int = 10) -> List[dict]:
        """
        Get top posts from specified subreddits.
        
        Args:
            subreddit_names: List of subreddit names (without r/)
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
            limit_per_subreddit: Number of posts to fetch per subreddit
            total_limit: Maximum total posts to return
        
        Returns:
            List of post dictionaries with title, score, subreddit, url, etc.
        """
        all_posts = []
        
        for subreddit_name in subreddit_names:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Get top posts based on time filter
                # 'hot' = trending now (combination of score and recency)
                # 'top' = highest scoring posts in time period
                # For "hottest", we use 'hot' which is what Reddit shows on the front page
                # But if user wants time-filtered top posts, we can use 'top' with time_filter
                if time_filter and time_filter != 'all':
                    # Use 'top' for time-filtered results (e.g., top posts today)
                    posts = subreddit.top(limit=limit_per_subreddit, time_filter=time_filter)
                else:
                    # Use 'hot' for current hottest/trending posts
                    posts = subreddit.hot(limit=limit_per_subreddit)
                
                for post in posts:
                    all_posts.append({
                        'title': post.title,
                        'score': post.score,
                        'subreddit': subreddit_name,
                        'url': post.url,
                        'permalink': f"https://reddit.com{post.permalink}",
                        'author': str(post.author),
                        'num_comments': post.num_comments,
                        'created_utc': post.created_utc,
                        'is_self': post.is_self,
                        'selftext': post.selftext[:200] if post.is_self else None  # First 200 chars
                    })
            except Exception as e:
                print(f"Error fetching posts from r/{subreddit_name}: {e}")
                continue
        
        # Sort by score (upvotes) descending and return top N
        all_posts.sort(key=lambda x: x['score'], reverse=True)
        return all_posts[:total_limit]
    
    def get_top_posts_from_my_subreddits(self, time_filter: str = 'day',
                                         limit_per_subreddit: int = 5,
                                         total_limit: int = 10) -> List[dict]:
        """
        Get top posts from user's subscribed subreddits.
        
        Args:
            time_filter: 'hour', 'day', 'week', 'month', 'year', 'all'
            limit_per_subreddit: Number of posts to fetch per subreddit
            total_limit: Maximum total posts to return
        
        Returns:
            List of post dictionaries
        """
        subreddits = self.get_subscribed_subreddits()
        
        if not subreddits:
            # If no subscriptions, use popular subreddits as fallback
            print("No subscribed subreddits found. Using popular subreddits as fallback.")
            subreddits = ['popular', 'all']
        
        return self.get_top_posts_from_subreddits(
            subreddits,
            time_filter=time_filter,
            limit_per_subreddit=limit_per_subreddit,
            total_limit=total_limit
        )

