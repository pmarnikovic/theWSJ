import asyncio
import feedparser
import random
import aiohttp
import os
from jinja2 import Environment, FileSystemLoader
from google.generativeai import configure, GenerativeModel

# Configure Gemini API
configure(api_key=os.getenv("GOOGLE_API_KEY"))
model = GenerativeModel("gemini-pro")

# RSS Feeds
RSS_FEEDS = [
    "https://www.wsj.com/xml/rss/3_7031.xml",   # WSJ Markets
    "https://www.cnbc.com/id/100003114/device/rss/rss.html",  # CNBC Top News
    "https://www.marketwatch.com/rss/topstories",  # MarketWatch
    "https://finance.yahoo.com/news/rssindex",     # Yahoo Finance
    "https://www.reddit.com/r/wallstreetbets/.rss" # WSB (Meme)
]

# Keywords for category assignment
WALL_KEYWORDS = ["S&P", "Nasdaq", "Dow", "Big Tech", "earnings", "FOMC", "rate", "inflation", "Federal Reserve"]
MAIN_KEYWORDS = ["Russell", "small cap", "Main Street", "local", "regional bank"]
MEME_KEYWORDS = ["GameStop", "AMC", "meme stock", "stonks", "YOLO", "WSB", "Reddit", "short squeeze"]

# Category style mappings
CATEGORY_STYLES = {
    "wall": "wall-style",
    "main": "main-style",
    "meme": "meme-style"
}

# Simple fallback image list
FALLBACK_IMAGES = [
    "https://source.unsplash.com/featured/?finance",
    "https://source.unsplash.com/featured/?wallstreet",
    "https://source.unsplash.com/featured/?stocks",
    "https://source.unsplash.com/featured/?trading"
]

# Utility: assign category based on keywords
def assign_category(title, summary, source):
    content = f"{title} {summary} {source}".lower()
    if any(kw.lower() in content for kw in MEME_KEYWORDS):
        return "meme"
    elif any(kw.lower() in content for kw in MAIN_KEYWORDS):
        return "main"
    else:
        return "wall"

# Async: summarize text with Gemini
async def summarize_article(title, summary):
    prompt = f"Summarize this financial news article in 1–2 sentences for investors:\n\nTitle: {title}\n\n{summary}"
    try:
        response = await model.generate_content_async(prompt)
        return response.text.strip()
    except Exception as e:
        print(f"Gemini error: {e}")
        return summary[:200] + "..."

# Async: parse and summarize articles
async def fetch_and_process_articles():
    all_articles = []

    async with aiohttp.ClientSession() as session:
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:
                    title = entry.get("title", "No title")
                    summary = entry.get("summary", "")
                    link = entry.get("link", "#")
                    image_url = (
                        entry.get("media_content", [{}])[0].get("url")
                        if "media_content" in entry
                        else random.choice(FALLBACK_IMAGES)
                    )

                    category = assign_category(title, summary, feed.feed.get("title", ""))
                    style = CATEGORY_STYLES[category]

                    summarized = await summarize_article(title, summary)

                    article = {
                        "title": title,
                        "summary": summarized,
                        "url": link,
                        "image_url": image_url,
                        "category": category,
                        "style": style
                    }
                    all_articles.append(article)
            except Exception as e:
                print(f"Error parsing {feed_url}: {e}")
                continue

    return all_articles

# Render HTML from Jinja template
def render_html(articles):
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("index.html.j2")

    output = template.render(articles=articles)
    os.makedirs("output", exist_ok=True)
    with open("output/index.html", "w", encoding="utf-8") as f:
        f.write(output)

# Main async runner
async def main():
    print("Fetching and summarizing articles...")
    articles = await fetch_and_process_articles()
    print(f"Rendering {len(articles)} articles to output/index.html")
    render_html(articles)

if __name__ == "__main__":
    asyncio.run(main())






from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

# Prepare articles: must be a list of dictionaries with keys:
# title, summary, url, image_url, category, style
# Example:
# articles = [
#     {'title': '...', 'summary': '...', 'url': '...', 'image_url': '...', 'category': 'wall', 'style': 'highlight'},
#     ...
# ]

# Set up the Jinja2 environment to load the template from the current directory
env = Environment(
    loader=FileSystemLoader(searchpath='.'),
    autoescape=select_autoescape(['html', 'xml'])
)

# Load the template
template = env.get_template('index.html.j2')

# Render the template with articles data
rendered_html = template.render(articles=articles)

# Write the rendered HTML to index.html
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("✅ index.html successfully generated from index.html.j2")

