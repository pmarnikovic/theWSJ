import re
import html
import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

# Regex to find the first <img src="...">
IMG_SRC_REGEX = re.compile(r'<img[^>]+src=["\']([^"\'>]+)["\']', re.IGNORECASE)

# Common "fake" image patterns to skip (1x1 pixels, tracking, placeholders)
BAD_IMAGE_PATTERNS = [
    "1x1", "spacer.gif", "pixel.gif", "blank.gif", "data:image", "transparent.gif"
]

VALID_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp")


def normalize_image_url(url: str | None) -> str | None:
    """Clean and normalize an image URL."""
    if not url:
        return None
    url = html.unescape(url).strip().strip('"').strip("'")
    if not url:
        return None
    if url.startswith("//"):
        url = "https:" + url
    return url


def is_valid_image_url(url: str | None) -> bool:
    """Stricter validation: must be http(s), have allowed extension, and not match bad patterns."""
    if not url:
        return False
    url_lower = url.lower()

    # Must be http(s)
    if not (url_lower.startswith("http://") or url_lower.startswith("https://")):
        return False

    # Skip known bad patterns
    if any(pattern in url_lower for pattern in BAD_IMAGE_PATTERNS):
        return False

    # Optional: require file extension looks like an image
    if not url_lower.endswith(VALID_IMAGE_EXTENSIONS):
        return False

    return True


def extract_img_from_html(html_fragment: str) -> str | None:
    """Extract first image src from HTML content."""
    if not html_fragment:
        return None
    match = IMG_SRC_REGEX.search(html_fragment)
    return match.group(1) if match else None


def get_article_content(entry):
    """Extract relevant fields from an RSS entry."""
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

    # 4. <img> in summary
    if not image_url:
        image_url = extract_img_from_html(summary)

    # 5. <img> in content:encoded
    if not image_url and hasattr(entry, "content"):
        for content_block in entry.content:
            image_url = extract_img_from_html(getattr(content_block, "value", ""))
            if image_url:
                break

    # Normalize
    image_url = normalize_image_url(image_url)

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "image_url": image_url,  # May be None or invalid
        "style": "normal",
    }


def fetch_and_parse_articles():
    """Fetch, parse, and filter articles to only those with *valid* images."""
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

                    # Strict image validation here
                    if not is_valid_image_url(article_data["image_url"]):
                        skipped_no_image += 1
                        continue

                    article_data["category"] = category
                    articles.append(article_data)

            except Exception as e:
                print(f"An error occurred while processing feed {url}: {e}")

    print(
        f"✅ Kept {len(articles)} articles with valid images. "
        f"Skipped {skipped_no_image} without usable images out of {total_seen} total."
    )
    return articles


# --- Main script execution ---
if __name__ == "__main__":
    articles = fetch_and_parse_articles()

    # Set up Jinja2
    env = Environment(
        loader=FileSystemLoader(searchpath="templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )

    # Load template
    template = env.get_template("index.html.j2")

    # Render HTML
    rendered_html = template.render(articles=articles)

    # Write to file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(rendered_html)

    print("✅ index.html successfully generated with articles.")
