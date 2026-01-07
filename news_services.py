# news_services.py
import os
from typing import List, Optional
from dotenv import load_dotenv
import requests
from datetime import datetime

# Load environment variables
load_dotenv()


class NewsServices:
    def __init__(self):
        """Initialize News API client."""
        # NewsAPI credentials from environment variables
        self.api_key = os.getenv('NEWS_API_KEY')
        self.base_url = 'https://newsapi.org/v2'
        
        if not self.api_key:
            raise ValueError(
                "News API key not found. Please set in .env file:\n"
                "NEWS_API_KEY=your-api-key-here\n"
                "\nTo get a free API key:\n"
                "1. Go to https://newsapi.org/register\n"
                "2. Sign up for a free account (100 requests/day)\n"
                "3. Copy your API key from the dashboard"
            )
        
        # Topic to category mapping
        self.topic_categories = {
            'business': 'business',
            'marketing': 'business',  # Marketing falls under business
            'stocks': 'business',
            'technology': 'technology',
            'tech': 'technology',
            'sports': 'sports',
            'entertainment': 'entertainment',
            'health': 'health',
            'science': 'science',
            'general': 'general',
            'default': 'general'
        }
    
    def get_top_headlines(self, topic: str = 'general', country: str = 'us', 
                         limit: int = 5) -> List[dict]:
        """
        Get top headlines for a specific topic.
        
        Args:
            topic: Topic keyword (business, marketing, stocks, technology, etc.)
            country: Country code (default: 'us')
            limit: Number of articles to return (default: 5)
        
        Returns:
            List of article dictionaries with title, description, url, source, etc.
        """
        # Map topic to NewsAPI category
        category = self.topic_categories.get(topic.lower(), 'general')
        
        # For marketing/stocks, we'll use keyword search instead of category
        if topic.lower() in ['marketing', 'stocks']:
            return self.search_articles(query=topic, limit=limit)
        
        # Build API request
        url = f"{self.base_url}/top-headlines"
        params = {
            'apiKey': self.api_key,
            'country': country,
            'category': category if category != 'general' else None,
            'pageSize': limit
        }
        
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'ok':
                raise Exception(f"News API error: {data.get('message', 'Unknown error')}")
            
            articles = []
            for article in data.get('articles', [])[:limit]:
                articles.append({
                    'title': article.get('title', 'No title'),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': article.get('publishedAt', ''),
                    'author': article.get('author', ''),
                    'image_url': article.get('urlToImage', '')
                })
            
            return articles
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch news: {str(e)}")
    
    def search_articles(self, query: str, limit: int = 5, 
                      sort_by: str = 'publishedAt') -> List[dict]:
        """
        Search for articles by keyword.
        
        Args:
            query: Search query (e.g., 'marketing', 'stocks', 'AI')
            limit: Number of articles to return
            sort_by: Sort order ('relevancy', 'popularity', 'publishedAt')
        
        Returns:
            List of article dictionaries
        """
        url = f"{self.base_url}/everything"
        params = {
            'apiKey': self.api_key,
            'q': query,
            'sortBy': sort_by,
            'pageSize': limit,
            'language': 'en'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'ok':
                raise Exception(f"News API error: {data.get('message', 'Unknown error')}")
            
            articles = []
            for article in data.get('articles', [])[:limit]:
                articles.append({
                    'title': article.get('title', 'No title'),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': article.get('publishedAt', ''),
                    'author': article.get('author', ''),
                    'image_url': article.get('urlToImage', '')
                })
            
            return articles
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to search news: {str(e)}")
    
    def get_news_by_topic(self, topic: str = 'general', limit: int = 5) -> List[dict]:
        """
        Get news articles for a specific topic.
        This is a convenience method that handles topic mapping.
        
        Args:
            topic: Topic keyword (business, marketing, stocks, technology, etc.)
            limit: Number of articles to return
        
        Returns:
            List of article dictionaries
        """
        topic_lower = topic.lower()
        
        # Handle specific topics that need keyword search
        if topic_lower in ['marketing', 'stocks', 'stock market']:
            search_query = 'marketing' if topic_lower == 'marketing' else 'stocks OR stock market'
            return self.search_articles(query=search_query, limit=limit, sort_by='popularity')
        
        # Use category-based search for standard topics
        return self.get_top_headlines(topic=topic, limit=limit)


# Alternative: RSS Feed Parser (no API key needed, but less structured)
class RSSNewsServices:
    """
    Alternative news service using RSS feeds.
    No API key required, but requires maintaining feed URLs.
    """
    
    def __init__(self):
        try:
            import feedparser
            self.feedparser = feedparser
        except ImportError:
            raise ImportError("feedparser library required. Install with: pip install feedparser")
        
        # RSS feed URLs by topic
        self.feeds = {
            'general': [
                'https://feeds.bbci.co.uk/news/rss.xml',
                'https://rss.cnn.com/rss/edition.rss',
                'https://feeds.npr.org/1001/rss.xml'
            ],
            'business': [
                'https://feeds.bbci.co.uk/news/business/rss.xml',
                'https://rss.cnn.com/rss/money_latest.rss',
                'https://www.cnbc.com/id/100003114/device/rss/rss.html'
            ],
            'technology': [
                'https://feeds.bbci.co.uk/news/technology/rss.xml',
                'https://rss.cnn.com/rss/edition_technology.rss',
                'https://techcrunch.com/feed/'
            ],
            'marketing': [
                'https://www.marketingland.com/feed',
                'https://www.marketingprofs.com/rss.xml'
            ],
            'stocks': [
                'https://www.cnbc.com/id/15839069/device/rss/rss.html',
                'https://feeds.finance.yahoo.com/rss/2.0/headline'
            ]
        }
    
    def get_top_articles(self, topic: str = 'general', limit: int = 5) -> List[dict]:
        """
        Get top articles from RSS feeds for a topic.
        
        Args:
            topic: Topic keyword
            limit: Number of articles to return
        
        Returns:
            List of article dictionaries
        """
        topic_lower = topic.lower()
        feed_urls = self.feeds.get(topic_lower, self.feeds['general'])
        
        all_articles = []
        
        for feed_url in feed_urls:
            try:
                feed = self.feedparser.parse(feed_url)
                
                for entry in feed.entries[:limit]:
                    all_articles.append({
                        'title': entry.get('title', 'No title'),
                        'description': entry.get('summary', ''),
                        'url': entry.get('link', ''),
                        'source': feed.feed.get('title', 'Unknown'),
                        'published_at': entry.get('published', ''),
                        'author': entry.get('author', ''),
                        'image_url': None
                    })
            except Exception as e:
                print(f"Error fetching feed {feed_url}: {e}")
                continue
        
        # Sort by published date (most recent first) and return top N
        all_articles.sort(key=lambda x: x['published_at'], reverse=True)
        return all_articles[:limit]

