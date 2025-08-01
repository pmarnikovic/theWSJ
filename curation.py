import os
import jinja2
import feedparser
import arxiv
import google.generativeai as genai
import time
from datetime import datetime, timezone

# --- CONFIGURATION ---

# Configure the Gemini API client
try:
    # Use os.getenv() for safer key retrieval
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        raise KeyError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
except KeyError as e:
    print(f"ERROR: {e}")
    exit(1)

# List of RSS feeds to parse for AI news
RSS_FEEDS = [
    "http://www.theverge.com/rss/group/ai-artificial-intelligence/index.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.wired.com/feed/category/business/artificial-intelligence/latest/rss",
    "https://news.mit.edu/topic/artificial-intelligence2-rss.xml",
    "https://ai.googleblog.com/feeds/posts/default",
    "https://www.marktechpost.com/feed/",
    "https://www.unite.ai/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://futurism.com/feed",
    "https://singularityhub.com/feed/",
    "https://openai.com/blog/rss/",
    "https://www.deepmind.com/blog/rss",
    "https://www.analyticsvidhya.com/feed/",
    "https://www.oreilly.com/radar/topics/ai-ml/feed/index.xml",
    "https://dailyai.com/feed/"
]

MAX_ARTICLES_PER_SOURCE = 3
MAX_TOTAL_ARTICLES = 25

# --- FUNCTIONS ---

def get_articles_from_rss():
    """Fetches and parses articles from the list of RSS feeds."""
    articles =
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                if entry.get('title') and entry.get('link'):
                    article = {'title': entry.title, 'url': entry.link}
                    # Normalize RSS date (struct_time) to timezone-aware datetime
                    if 'published_parsed' in entry and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        article['published'] = dt.replace(tzinfo=timezone.utc)
                    else:
                        # Fallback for feeds without dates
                        article['published'] = datetime.now(timezone.utc)
                    articles.append(article)
        except Exception as e:
            print(f"Error fetching RSS feed {feed_url}: {e}")
    return articles

def get_articles_from_arxiv():
    """Fetches recent research papers from arXiv's Computer Science AI category."""
    articles =
    try:
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=MAX_ARTICLES_PER_SOURCE,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        client = arxiv.Client()
        for result in client.results(search):
            # arXiv 'published' is already a timezone-aware datetime
            articles.append({'title': result.title, 'url': result.entry_id, 'published': result.published})
    except Exception as e:
        print(f"Error fetching from arXiv: {e}")
    return articles

def generate_drudge_headline(title):
    """Uses the Gemini API to generate a sensational, Drudge-style headline."""
    fallback_headline = title.upper().strip() + "..."
    prompt = f"""
    You are an AI news editor with the personality of Matt Drudge. Your job is to write an irresistible, punchy, and sensational headline in all-caps. The headline should be provocative and short.

    Based on the following article title, generate one headline.

    Article Title: "{title}"

    Example Headline Format:
    * SCIENTISTS UNLEASH 'CHILD' AI... FEARS GROW...
    * NEW GOOGLE MODEL SEES THROUGH WALLS... PRIVACY DECLARED DEAD?
    * PAPER REVEALS CHATGPT COST... $700K A DAY TO RUN...

    Now, generate the headline for the provided title.
    """
    try:
        response = gemini_model.generate_content(prompt)
        headline = response.text.strip().replace('*', '').strip()
        return headline if headline else fallback_headline
    except Exception as e:
        print(f"Error generating headline for '{title}': {e}")
        return fallback_headline

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("Starting AI-Drudge content generation...")

    # 1. Fetch articles from all sources
    all_articles = get_articles_from_rss() + get_articles_from_arxiv()
    print(f"Fetched {len(all_articles)} total raw articles.")

    # 2. Deduplicate articles based on URL
    seen_urls = set()
    unique_articles =
    for article in all_articles:
        if article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])

    # 3. Sort all unique articles by publication date, newest first
    unique_articles.sort(key=lambda x: x['published'], reverse=True)
    print(f"Processing {len(unique_articles)} unique articles after deduplication.")

    # 4. Take the most recent articles, respecting the total limit
    articles_to_process = unique_articles
    print(f"Selected the top {len(articles_to_process)} most recent articles for headline generation.")

    # 5. Generate headlines for the final list
    final_news_items =
    for article in articles_to_process:
        print(f"Generating headline for: {article['title']}")
        headline = generate_drudge_headline(article['title'])
        final_news_items.append({'headline': headline, 'url': article['url']})
        print(f"  -> {headline}")

    # 6. Render the HTML template
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("index.html.j2")
    output_html = template.render(news_items=final_news_items)

    # 7. Write the final HTML file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

    print(f"Successfully generated new index.html with {len(final_news_items)} headlines.")
