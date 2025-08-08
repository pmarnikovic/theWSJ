import requests
from bs4 import BeautifulSoup
from jinja2 import Environment, FileSystemLoader, select_autoescape

def fetch_article_from_url(url):
    """
    Fetches metadata (title, summary, image) from a given HTML page.
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"❌ Error fetching {url}: {e}")
        return {
            "title": "Fetch Error",
            "summary": str(e),
            "url": url,
            "image_url": "",
            "style": "error"
        }

    soup = BeautifulSoup(resp.text, "html.parser")
    title = soup.title.string.strip() if soup.title else "No Title Provided"

    # Description from meta tags
    meta_desc = soup.find("meta", attrs={"name": "description"})
    og_desc = soup.find("meta", property="og:description")
    summary = (meta_desc or og_desc)
    summary = summary["content"].strip() if summary and summary.get("content") else ""

    # Fallback: first <p>
    if not summary:
        first_p = soup.find("p")
        summary = first_p.text.strip() if first_p else "No Summary Available"

    # Image: og:image > first <img>
    og_img = soup.find("meta", property="og:image")
    image_url = og_img["content"].strip() if og_img and og_img.get("content") else ""

    if not image_url:
        img = soup.find("img", src=True)
        image_url = img["src"].strip() if img else ""

    # Normalize image URL
    if image_url.startswith("//"):
        image_url = "https:" + image_url
    elif image_url.startswith("/"):
        from urllib.parse import urljoin
        image_url = urljoin(url, image_url)

    return {
        "title": title,
        "summary": summary,
        "url": url,
        "image_url": image_url,
        "style": "normal"
    }

def fetch_and_parse_articles():
    """
    Fetches articles directly from web pages (non-RSS), categorizes, and returns them.
    """
    sources = {
        "wall": [
            "https://www.reuters.com/business/",
            "https://finance.yahoo.com/",
            "https://www.marketwatch.com/",
        ],
        "main": [
            "https://www.cnn.com/",
            "https://www.bbc.com/news/world/us_and_canada",
            "https://www.npr.org/",
        ],
        "meme": [
            "https://www.reddit.com/r/wallstreetbets/",
            "https://www.reddit.com/r/stocks/",
        ]
    }

    articles = []

    for category, urls in sources.items():
        for url in urls:
            print(f"🌐 Fetching {url} as '{category}'...")
            article = fetch_article_from_url(url)
            article['category'] = category
            articles.append(article)

    print(f"✅ Fetched {len(articles)} direct articles.")
    return articles

# --- Main script execution ---
articles = fetch_and_parse_articles()

env = Environment(
    loader=FileSystemLoader(searchpath='templates'),
    autoescape=select_autoescape(['html', 'xml'])
)

template = env.get_template('index.html.j2')
rendered_html = template.render(articles=articles)

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("✅ index.html successfully generated with non-RSS articles.")
