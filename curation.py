import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

def get_article_content(entry):
    """
    Safely retrieves article content, checking for common field names, including image URL.
    """
    title = getattr(entry, 'title', 'No Title Provided')

    # Check for summary or description
    summary = getattr(entry, 'summary', '')
    if not summary:
        summary = getattr(entry, 'description', 'No Summary Available')

    url = getattr(entry, 'link', '#')

    # Attempt to get image URL from known locations
    image_url = ""

    # 1. Check media_content
    if hasattr(entry, 'media_content'):
        media = entry.media_content
        if isinstance(media, list) and media:
            image_url = media[0].get('url', '')

    # 2. Check media_thumbnail
    elif hasattr(entry, 'media_thumbnail'):
        thumbnail = entry.media_thumbnail
        if isinstance(thumbnail, list) and thumbnail:
            image_url = thumbnail[0].get('url', '')

    # 3. Check enclosures
    elif hasattr(entry, 'enclosures'):
        for enclosure in entry.enclosures:
            if enclosure.get('type', '').startswith('image/'):
                image_url = enclosure.get('href', '')
                break

    # 4. Extract from <img> tag in summary/content
    if not image_url:
        match = re.search(r'<img[^>]+src="([^">]+)"', summary)
        if match:
            image_url = match.group(1)

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "image_url": image_url,
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
            "https://www.reddit.com/r/SuperStonk/.rss",
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
