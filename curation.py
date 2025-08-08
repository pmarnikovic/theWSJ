import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

def get_article_content(entry):
    """
    Safely retrieves article content, checking for common field names.
    """
    title = getattr(entry, 'title', 'No Title Provided')
    
    # Check for summary or description
    summary = getattr(entry, 'summary', '')
    if not summary:
        summary = getattr(entry, 'description', 'No Summary Available')
    
    url = getattr(entry, 'link', '#')
    
   return {
        "title": title,
        "summary": summary,
        "url": url,
        "image_url": "",  # This remains a placeholder for now
        "style": "normal"
    }



def fetch_and_parse_articles():
    """
    Fetches articles from various RSS feeds, categorizes them, and returns a list.
    """
    feeds = {
        "wall": [
            "https://www.reuters.com/rssFeed/businessNews",
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=yhoo&region=US&lang=en-US",
            "http://www.marketwatch.com/rss/topstories",
        ],
        "main": [
            "http://rss.cnn.com/rss/cnn_topstories.rss",
            "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
            "https://www.npr.org/rss/rss.php?id=1001",
        ],
        "meme": [
            "https://www.reddit.com/r/wallstreetbets/.rss",
            "https://www.reddit.com/r/stocks/.rss",
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
                    article_data = get_article_content(entry)
                    article_data['category'] = category  # Assign the correct category
                    articles.append(article_data)
            except Exception as e:
                print(f"An error occurred while processing feed {url}: {e}")

    print(f"✅ Successfully fetched {len(articles)} articles in total.")
    return articles

# --- Main script execution ---

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

# Write rendered HTML to index.html
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("✅ index.html successfully generated with articles.")
