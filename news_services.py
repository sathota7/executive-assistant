# news_services.py
import os
import re
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
        
        # Reputable news sources (finite list - major established outlets only)
        # These are normalized to lowercase for matching
        self.reputable_sources = {
            # Major US newspapers
            'the new york times', 'new york times', 'nytimes', 'nyt',
            'the washington post', 'washington post', 'wapo',
            'wall street journal', 'wsj',
            'los angeles times', 'la times',
            'chicago tribune',
            'boston globe',
            'usa today',
            
            # News networks
            'abc news', 'abc',
            'cbs news', 'cbs',
            'nbc news', 'nbc',
            'cnn',
            'fox news',
            'msnbc',
            'pbs news', 'pbs',
            'npr',
            
            # Business/Financial
            'bloomberg', 'bloomberg news',
            'reuters',
            'associated press', 'ap news', 'ap',
            'financial times', 'ft',
            'cnbc',
            'forbes',
            'the economist',
            
            # Political/Policy
            'politico',
            'axios',
            'the hill',
            
            # International
            'bbc', 'bbc news',
            'the guardian',
            'the times',
            'time',
            'newsweek',
            
            # Technology (reputable tech news)
            'techcrunch',
            'the verge',
            'wired',
            'ars technica',
            'engadget',
            
            # Business/Finance
            'business insider',
            'marketwatch',
            'yahoo finance',
            'yahoo news'
        }
        
        # Patterns that indicate blogs or non-reputable sources
        self.blog_patterns = [
            r'\.(blog|wordpress|tumblr|medium|substack)\.',
            r'\b(blog|blogger|blogging)\b',
            r'\b(fan|fansite|fans)\b',
            r'\.com/blog/',
            r'/blog/',
        ]
    
    def _is_reputable_source(self, source_name: str) -> bool:
        """
        Check if a source is in the reputable sources list.
        
        Args:
            source_name: Name of the news source
        
        Returns:
            True if source is reputable, False otherwise
        """
        if not source_name:
            return False
        
        source_lower = source_name.lower().strip()
        
        # Direct match
        if source_lower in self.reputable_sources:
            return True
        
        # Check for partial matches (e.g., "The New York Times" matches "new york times")
        for reputable in self.reputable_sources:
            if reputable in source_lower or source_lower in reputable:
                return True
        
        return False
    
    def _is_blog(self, source_name: str, url: str = '') -> bool:
        """
        Check if a source appears to be a blog.
        
        Args:
            source_name: Name of the news source
            url: URL of the article (optional)
        
        Returns:
            True if source appears to be a blog, False otherwise
        """
        if not source_name and not url:
            return False
        
        text = f"{source_name} {url}".lower()
        
        # Check for blog patterns
        for pattern in self.blog_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _filter_articles_by_source(self, articles: List[dict]) -> List[dict]:
        """
        Filter articles to only include those from reputable sources, excluding blogs.
        
        Args:
            articles: List of article dictionaries
        
        Returns:
            Filtered list of articles from reputable sources only
        """
        filtered = []
        
        for article in articles:
            source_name = article.get('source', '')
            url = article.get('url', '')
            
            # Skip if it's a blog
            if self._is_blog(source_name, url):
                continue
            
            # Only include if source is reputable
            if self._is_reputable_source(source_name):
                filtered.append(article)
        
        return filtered
    
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
        
        # Build API request - fetch more to account for filtering
        url = f"{self.base_url}/top-headlines"
        params = {
            'apiKey': self.api_key,
            'country': country,
            'category': category if category != 'general' else None,
            'pageSize': limit * 3  # Fetch more to ensure we have enough after filtering
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
            for article in data.get('articles', []):
                articles.append({
                    'title': article.get('title', 'No title'),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': article.get('publishedAt', ''),
                    'author': article.get('author', ''),
                    'image_url': article.get('urlToImage', '')
                })
            
            # Filter to only reputable sources and return up to limit
            filtered_articles = self._filter_articles_by_source(articles)
            return filtered_articles[:limit]
            
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
            'pageSize': limit * 3,  # Fetch more to ensure we have enough after filtering
            'language': 'en'
        }
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') != 'ok':
                raise Exception(f"News API error: {data.get('message', 'Unknown error')}")
            
            articles = []
            for article in data.get('articles', []):
                articles.append({
                    'title': article.get('title', 'No title'),
                    'description': article.get('description', ''),
                    'url': article.get('url', ''),
                    'source': article.get('source', {}).get('name', 'Unknown'),
                    'published_at': article.get('publishedAt', ''),
                    'author': article.get('author', ''),
                    'image_url': article.get('urlToImage', '')
                })
            
            # Filter to only reputable sources and return up to limit
            filtered_articles = self._filter_articles_by_source(articles)
            return filtered_articles[:limit]
            
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
        
        # RSS feed URLs by topic (only reputable sources)
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
        
        # Reputable sources list (same as NewsServices)
        self.reputable_sources = {
            'the new york times', 'new york times', 'nytimes', 'nyt',
            'the washington post', 'washington post', 'wapo',
            'wall street journal', 'wsj',
            'los angeles times', 'la times',
            'chicago tribune',
            'boston globe',
            'usa today',
            'abc news', 'abc',
            'cbs news', 'cbs',
            'nbc news', 'nbc',
            'cnn',
            'fox news',
            'msnbc',
            'pbs news', 'pbs',
            'npr',
            'bloomberg', 'bloomberg news',
            'reuters',
            'associated press', 'ap news', 'ap',
            'financial times', 'ft',
            'cnbc',
            'forbes',
            'the economist',
            'politico',
            'axios',
            'the hill',
            'bbc', 'bbc news',
            'the guardian',
            'the times',
            'time',
            'newsweek',
            'techcrunch',
            'the verge',
            'wired',
            'ars technica',
            'engadget',
            'business insider',
            'marketwatch',
            'yahoo finance',
            'yahoo news'
        }
        
        # Patterns that indicate blogs
        self.blog_patterns = [
            r'\.(blog|wordpress|tumblr|medium|substack)\.',
            r'\b(blog|blogger|blogging)\b',
            r'\b(fan|fansite|fans)\b',
            r'\.com/blog/',
            r'/blog/',
        ]
    
    def _is_reputable_source(self, source_name: str) -> bool:
        """Check if a source is in the reputable sources list."""
        if not source_name:
            return False
        
        source_lower = source_name.lower().strip()
        
        if source_lower in self.reputable_sources:
            return True
        
        for reputable in self.reputable_sources:
            if reputable in source_lower or source_lower in reputable:
                return True
        
        return False
    
    def _is_blog(self, source_name: str, url: str = '') -> bool:
        """Check if a source appears to be a blog."""
        if not source_name and not url:
            return False
        
        text = f"{source_name} {url}".lower()
        
        for pattern in self.blog_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    def _filter_articles_by_source(self, articles: List[dict]) -> List[dict]:
        """Filter articles to only include those from reputable sources, excluding blogs."""
        filtered = []
        
        for article in articles:
            source_name = article.get('source', '')
            url = article.get('url', '')
            
            if self._is_blog(source_name, url):
                continue
            
            if self._is_reputable_source(source_name):
                filtered.append(article)
        
        return filtered
    
    def get_top_articles(self, topic: str = 'general', limit: int = 5) -> List[dict]:
        """
        Get top articles from RSS feeds for a topic.
        
        Args:
            topic: Topic keyword
            limit: Number of articles to return
        
        Returns:
            List of article dictionaries from reputable sources only
        """
        topic_lower = topic.lower()
        feed_urls = self.feeds.get(topic_lower, self.feeds['general'])
        
        all_articles = []
        
        for feed_url in feed_urls:
            try:
                feed = self.feedparser.parse(feed_url)
                
                # Fetch more articles to account for filtering
                for entry in feed.entries[:limit * 3]:
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
        
        # Filter to only reputable sources
        filtered_articles = self._filter_articles_by_source(all_articles)
        
        # Sort by published date (most recent first) and return top N
        filtered_articles.sort(key=lambda x: x['published_at'], reverse=True)
        return filtered_articles[:limit]

