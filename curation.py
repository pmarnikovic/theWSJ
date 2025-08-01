import os
import jinja2
import feedparser
import arxiv
import google.generativeai as genai
import time
from datetime import datetime

# --- CONFIGURATION ---

# Configure the Gemini API client
try:
    gemini_api_key = os.environ['GEMINI_API_KEY']
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
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                if entry.get('title') and entry.get('link'):
                    article = {'title': entry.title, 'url': entry.link}
                    if 'published_parsed' in entry:
                        article['published'] = entry.published_parsed
                    articles.append(article)
        except Exception as e:
            print(f"Error fetching RSS feed {feed_url}: {e}")
    return articles

def get_articles_from_arxiv():
    """Fetches recent research papers from arXiv's Computer Science AI category."""
    articles = []
    try:
        search = arxiv.Search(
            query="cat:cs.AI",
            max_results=MAX_ARTICLES_PER_SOURCE,
            sort_by=arxiv.SortCriterion.SubmittedDate
        )
        client = arxiv.Client()
        for result in client.results(search):
            articles.append({'title': result.title, 'url': result.entry_id, 'published': result.published})
    except Exception as e:
        print(f"Error fetching from arXiv: {e}")
    return articles

def get_sensationalism_score(title):
    """Uses the Gemini API to score how sensational and headline-grabbing the title is."""
    prompt = f"""
    On a scale of 1 to 10, rate how provocative, sensational, and suitable for a clickbait headline this article title is. 
    Higher scores for titles that evoke strong emotions, controversy, breakthroughs, or fears. Respond only with the number 1-10.

    Title: "{title}"
    """
    try:
        response = gemini_model.generate_content(prompt)
        score = int(response.text.strip())
        return score if 1 <= score <= 10 else 5
    except Exception as e:
        print(f"Error scoring title '{title}': {e}")
        return 5  # Neutral fallback

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
        return title.upper() + "..."  # Consistent fallback with "..."

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("Starting AI-Drudge content generation...")

    # 1. Fetch articles from all sources
    all_articles = get_articles_from_rss() + get_articles_from_arxiv()
    print(f"Fetched {len(all_articles)} total articles.")

    # Normalize published dates to datetime objects
    for article in all_articles:
        pub = article.get('published')
        if isinstance(pub, time.struct_time):
            article['published'] = datetime.fromtimestamp(time.mktime(pub))
        elif not isinstance(pub, datetime):
            article['published'] = datetime.min

    # Sort by published date descending (most recent first, as a proxy for most viewed/popular)
    all_articles.sort(key=lambda a: a['published'], reverse=True)

    # 2. Score articles for sensationalism and select top 25 for best headline potential
    scored_articles = []
    for article in all_articles:
        if not article.get('title') or not article.get('url'):
            continue
        score = get_sensationalism_score(article['title'])
        scored_articles.append((score, article))

    # Sort by score descending
    scored_articles.sort(key=lambda x: x[0], reverse=True)

    # Select top articles
    top_articles = [art for score, art in scored_articles[:MAX_TOTAL_ARTICLES]]

    # 3. Generate headlines and build the final list
    final_news_items = []
    for article in top_articles:
        print(f"Generating headline for: {article['title']}")
        headline = generate_drudge_headline(article['title'])
        final_news_items.append({'headline': headline, 'url': article['url']})
        print(f"  -> {headline}")

    # 4. Render the HTML template
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("index.html.j2")
    output_html = template.render(news_items=final_news_items)

    # 5. Write the final HTML file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

    print("Successfully generated new index.html with dynamic content.")
