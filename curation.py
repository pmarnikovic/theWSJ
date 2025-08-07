import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

def fetch_finance_articles():
    feeds = [
        "https://www.reuters.com/rssFeed/businessNews",            # Reuters Business
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=yhoo&region=US&lang=en-US",  # Yahoo Finance
        # Add more finance RSS feed URLs here if you want
    ]
    articles = []
    for url in feeds:
        feed = feedparser.parse(url)
        for entry in feed.entries:
            article = {
                "title": entry.title,
                "summary": getattr(entry, 'summary', '') or getattr(entry, 'description', ''),
                "url": entry.link,
                "image_url": "",  # RSS feeds usually don’t include images; you can improve this later
                "category": "wall",  # You can customize categories based on your needs
                "style": "normal"
            }
            articles.append(article)
    return articles

# Fetch finance articles dynamically
articles = fetch_finance_articles()

# Set up Jinja2 environment to load templates from the 'templates' folder
env = Environment(
    loader=FileSystemLoader(searchpath='templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

# Load your template file from templates/index.html.j2
template = env.get_template('index.html.j2')

# Render template with articles
rendered_html = template.render(articles=articles)

# Write rendered HTML to index.html in the root directory
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("✅ index.html successfully generated with finance articles")
