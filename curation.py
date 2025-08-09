import re
import html
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape


IMG_SRC_REGEX = re.compile(r'<img[^>]+src=["\']([^"\'>]+)["\']', re.IGNORECASE)


def normalize_image_url(url: str | None) -> str | None:
    """
    Clean and normalize an image URL:
    - Unescape HTML entities (&amp; -> &)
    - Trim quotes/whitespace
    - Convert protocol-relative URLs (//...) to https://...
    """
    if not url:
        return None
    url = html.unescape(url).strip().strip('"').strip("'")
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    return url


def is_valid_image_url(url: str | None) -> bool:
    """
    Allow only http(s) URLs; reject empty, data:, javascript:, about:, etc.
    """
    if not url:
        return False
    url = url.lower()
    return url.startswith("http://") or url.startswith("https://")


def extract_img_from_html(html_fragment: str) -> str | None:
    """
    Find the first <img src="..."> in an HTML fragment.
    """
    if not html_fragment:
        return None
    match = IMG_SRC_REGEX.search(html_fragment)
    return match.group(1) if match else None


def get_article_content(entry):
    title = getattr(entry, "title", "No Title Provided")
    summary = getattr(entry, "summary", "") or getattr(entry, "description", "No Summary Available")
    url = getattr(entry, "link", "#")

    image_url = None

    # 1. media_content
    media = getattr(entry, "media_content", [])
    if isinstance(media, list) and media:
        image_url = media[0].get("url")

    # 2. media_thumbnail
    if not image_url:
        thumbnail = getattr(entry, "media_thumbnail", [])
        if isinstance(thumbnail, list) and thumbnail:
            image_url = thumbnail[0].get("url")

    # 3. enclosures
    if not image_url:
        for enclosure in getattr(entry, "enclosures", []):
            if enclosure.get("type", "").startswith("image/"):
                image_url = enclosure.get("href")
                break

    # 4. <img> in summary/description
    if not image_url:
        image_url = extract_img_from_html(summary)

    # 5. <img> in content:encoded
    if not image_url and hasattr(entry, "content"):
        for content_block in entry.content:
            image_url = extract_img_from_html(getattr(content_block, "value", ""))
            if image_url:
                break

    # Normalize and validate
    image_url = normalize_image_url(image_url)
    if not is_valid_image_url(image_url):
        image_url = None

    return {
        "title": title,
        "summary": summary,
        "url": url,
        **({"image_url": image_url} if image_url else {}),
        "style": "normal",
    }


def fetch_and_parse_articles():
    """
    Fetches articles from various RSS feeds, categorizes them, filters to only those with images,
    and returns a list.
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
        ],
    }

    articles = []
    total_seen = 0
    skipped_no_image = 0

    for category, urls in feeds.items():
        for url in urls:
            print(f"Fetching articles from {url} for category '{category}'...")
            try:
                feed = feedparser.parse(url)
                if getattr(feed, "bozo", 0):
                    print(f"Warning: Could not parse feed from {url}. Error: {getattr(feed, 'bozo_exception', '')}")
                    continue

                if not feed.entries:
                    print(f"No entries found in feed: {url}")
                    continue

                for entry in feed.entries:
                    total_seen += 1
                    article_data = get_article_content(entry)

                    # Skip if no image_url
                    if not article_data.get("image_url"):
                        skipped_no_image += 1
                        continue

                    article_data["category"] = category
                    articles.append(article_data)

            except Exception as e:
                print(f"An error occurred while processing feed {url}: {e}")

    print(
        f"✅ Kept {len(articles)} articles with images. "
        f"Skipped {skipped_no_image} without images out of {total_seen} total."
    )
    return articles


# --- Main script execution ---
if __name__ == "__main__":
    articles = fetch_and_parse_articles()

    # Set up Jinja2 environment to load templates from the 'templates' folder
    env = Environment(
        loader=FileSystemLoader(searchpath="templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Load your template file
    template = env.get_template("index.html.j2")

    # Render template with articles
    rendered_html = template.render(articles=articles)

    # Write rendered HTML to index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print("✅ index.html successfully generated with articles.")

