import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

def fetch_and_parse_articles():
    """
    Fetches articles from various RSS feeds and returns a list of dictionaries.
    The feeds are chosen for public accessibility (no subscription required).
    """
    feeds = {
        "wall": [
            # Feeds for financial news and markets (Wall Street)
            "https://www.reuters.com/rssFeed/businessNews",
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=yhoo&region=US&lang=en-US",
            "http://www.marketwatch.com/rss/topstories",
            "https://www.nasdaq.com/feed/rssoutbound?symbol=GME", # Example: GME news from Nasdaq
        ],
        "main": [
            # Feeds for general news and broader economic topics (Main Street)
            "http://rss.cnn.com/rss/cnn_topstories.rss",
            "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
            "https://www.npr.org/rss/rss.php?id=1001",
        ],
        "meme": [
            # Feeds for viral financial news and meme stocks (Meme Street)
            "https://www.reddit.com/r/wallstreetbets/.rss", # Reddit r/wallstreetbets as a source for meme stocks
            "https://www.reddit.com/r/stocks/.rss", # Reddit r/stocks for general stock discussion
            "https://www.forbes.com/feed/",
        ]
    }
    
    articles = []
    
    for category, urls in feeds.items():
        for url in urls:
            print(f"Fetching articles from {url} for category '{category}'...")
            try:
                feed = feedparser.parse(url)
                if feed.bozo:
                    print(f"Warning: Could not parse feed from {url}. Error: {feed.bozo_exception}")
                    continue
                
                if not feed.entries:
                    print(f"No entries found in feed: {url}")
                    continue
                
                for entry in feed.entries:
                    article = {
                        "title": getattr(entry, 'title', 'No Title'),
                        "summary": getattr(entry, 'summary', '') or getattr(entry, 'description', 'No Summary'),
                        "url": getattr(entry, 'link', '#'),
                        "image_url": "", 
                        "category": category,
                        "style": "normal"
                    }
                    articles.append(article)
            except Exception as e:
                print(f"An error occurred while processing feed {url}: {e}")
                
    print(f"✅ Successfully fetched {len(articles)} articles in total.")
    return articles

# Fetch articles dynamically
articles = fetch_and_parse_articles()

# Set up Jinja2 environment to load templates from the 'templates' folder
env = Environment(
    loader=FileSystemLoader(searchpath='templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

# Load your template file
template = env.get_template('index.html.j2')

# Render template with articles
rendered_html = template.render(articles=articles)

# Write rendered HTML to index.html in the root directory
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("✅ index.html successfully generated with articles.")
