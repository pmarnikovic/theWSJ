import os
import jinja2
import feedparser
import arxiv
import google.generativeai as genai

# --- CONFIGURATION ---

# Configure the Gemini API client
try:
    gemini_api_key = os.environ
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
except KeyError:
    print("ERROR: GEMINI_API_KEY environment variable not set.")
    exit(1)

# List of RSS feeds to parse for AI news
RSS_FEEDS = [
    "http://www.theverge.com/rss/group/ai-artificial-intelligence/index.xml",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://www.wired.com/feed/category/business/artificial-intelligence/latest/rss",
    "https://news.mit.edu/topic/artificial-intelligence2-rss.xml",
    "https://ai.googleblog.com/feeds/posts/default"
]

MAX_ARTICLES_PER_SOURCE = 3
MAX_TOTAL_ARTICLES = 15

# --- FUNCTIONS ---

def get_articles_from_rss():
    """Fetches and parses articles from the list of RSS feeds."""
    articles =
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                if entry.get('title') and entry.get('link'):
                    articles.append({'title': entry.title, 'url': entry.link})
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
            articles.append({'title': result.title, 'url': result.entry_id})
    except Exception as e:
        print(f"Error fetching from arXiv: {e}")
    return articles

def generate_drudge_headline(title):
    """Uses the Gemini API to generate a sensational, Drudge-style headline."""
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
        # If the AI returns an empty string, fall back to the original title
        return headline if headline else title.upper() + "..."
    except Exception as e:
        print(f"Error generating headline for '{title}': {e}")
        return title.upper() # Fallback to a simple uppercase title

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("Starting AI-Drudge content generation...")

    # 1. Fetch articles from all sources
    all_articles = get_articles_from_rss() + get_articles_from_arxiv()
    print(f"Fetched {len(all_articles)} total articles.")

    # 2. Generate headlines and build the final list
    final_news_items =
    # Limit the total number of articles to process
    for article in all_articles:
        if not article.get('title') or not article.get('url'):
            continue
        print(f"Generating headline for: {article['title']}")
        headline = generate_drudge_headline(article['title'])
        final_news_items.append({'headline': headline, 'url': article['url']})
        print(f"  -> {headline}")

    # 3. Render the HTML template
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("index.html.j2")
    output_html = template.render(news_items=final_news_items)

    # 4. Write the final HTML file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

    print("Successfully generated new index.html with dynamic content.")
