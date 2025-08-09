import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

import re

def get_article_content(entry):
    title = getattr(entry, 'title', 'No Title Provided')
    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', 'No Summary Available')
    url = getattr(entry, 'link', '#')

    image_url = None

    # 1. media_content
    media = getattr(entry, 'media_content', [])
    if isinstance(media, list) and media:
        image_url = media[0].get('url')

    # 2. media_thumbnail
    if not image_url:
        thumbnail = getattr(entry, 'media_thumbnail', [])
        if isinstance(thumbnail, list) and thumbnail:
            image_url = thumbnail[0].get('url')

    # 3. enclosures
    if not image_url:
        for enclosure in getattr(entry, 'enclosures', []):
            if enclosure.get('type', '').startswith('image/'):
                image_url = enclosure.get('href')
                break

    # 4. <img> in summary
    if not image_url:
        match = re.search(r'<img[^>]+src=["\']([^"\'>]+)["\']', summary)
        if match:
            image_url = match.group(1)

    # 5. <img> in content:encoded
    if not image_url and hasattr(entry, 'content'):
        for content_block in entry.content:
            match = re.search(r'<img[^>]+src=["\']([^"\'>]+)["\']', content_block.value)
            if match:
                image_url = match.group(1)
                break

    # 6. Final fallback: if no image found, don't include image_url
    if not image_url:
        image_url = None

    
    return {
        "title": title,
        "summary": summary,
        "url": url,
        **({"image_url": image_url} if image_url else {}),
        "style": "normal"
    }


def fetch_and_parse_articles():
    """
    Fetches articles from various RSS feeds, categorizes them, and returns a list.
    """
    feeds = {
        "wall": [
            "https://www.investing.com/rss/news_25.rss",
            "https://www.investing.com/rss/news_14.rss",
            "https://www.investing.com/rss/news_95.rss",
            "https://finance.yahoo.com/news/rss",
            "https://finance.yahoo.com/topic/stock-market/rss",
            "https://finance.yahoo.com/topic/tech/rss",
            "https://finance.yahoo.com/topic/crypto/rss",
            "https://finance.yahoo.com/topic/earnings/rss",
            
        ],
        "main": [
            "https://feeds.feedburner.com/SmallBusinessTrends",
            "https://moxie.foxbusiness.com/google-publisher/small-business.xml",
            "https://smallbusinessbonfire.com/feed",
            "https://succeedasyourownboss.com/feed",
            "https://www.ft.com/?format=rss",            
        ],

        "meme": [
            "https://www.reddit.com/r/wallstreetbets/.rss",
            "https://www.reddit.com/r/WallStreetBetsCrypto/.rss",
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
