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
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                if entry.get('title') and entry.get('link'):
                    article = {'title': entry.title, 'url': entry.link}
                    if 'published_parsed' in entry and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        article['published'] = dt.replace(tzinfo=timezone.utc)
                    else:
                        article['published'] = datetime.min.replace(tzinfo=timezone.utc)  # Use min to sort last if missing
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

def get_headline_and_score(title):
    """Uses a single Gemini API call to get both a headline and a sensationalism score."""
    fallback_headline = title.upper().strip() + "..."
    prompt = f"""
    Analyze the following article title. First, on a scale of 1 to 10, rate how provocative and sensational it is. Higher scores for titles that evoke strong emotions, controversy, or breakthroughs.
    Second, rewrite the title as an irresistible, punchy, and sensational headline in all-caps, in the style of Matt Drudge.

    Respond with the score and the headline separated by a pipe character (|). For example: 8|SCIENTISTS UNLEASH 'CHILD' AI... FEARS GROW...

    Article Title: "{title}"
    """
    try:
        response = gemini_model.generate_content(prompt)
        parts = response.text.strip().split('|', 1)
        if len(parts) == 2:
            score = int(parts[0].strip())
            headline = parts[1].strip().replace('*', '')
            return headline, score
        else:
            # If the model doesn't respond in the correct format, fallback
            return fallback_headline, 5
    except Exception as e:
        print(f"Error processing title '{title}': {e}")
        return fallback_headline, 5

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("Starting content generation for Exhaustive AI...")

    # 1. Fetch and deduplicate articles
    all_articles = get_articles_from_rss() + get_articles_from_arxiv()
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article.get('url') and article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])

    # 2. Sort by date and take the most recent
    unique_articles.sort(key=lambda x: x['published'], reverse=True)
    articles_to_process = unique_articles[:MAX_TOTAL_ARTICLES]  # Limit before processing
    print(f"Selected the top {len(articles_to_process)} most recent articles.")

    # 3. Generate headlines and scores for each article
    processed_articles = []
    for article in articles_to_process:
        print(f"Processing: {article['title']}")
        headline, score = get_headline_and_score(article['title'])
        processed_articles.append({
            'headline': headline,
            'url': article['url'],
            'score': score
        })
        print(f"  -> Score: {score}, Headline: {headline}")

    # 4. Sort by score to find the main headline
    processed_articles.sort(key=lambda x: x['score'], reverse=True)

    # 5. Separate the main headline from the rest
    main_headline = processed_articles[0] if processed_articles else None
    other_headlines = processed_articles[1:]

    # 6. Split the rest into three columns for the template
    col_size = (len(other_headlines) + 2) // 3  # Distribute items evenly
    column1 = other_headlines[0:col_size]
    column2 = other_headlines[col_size:col_size*2]
    column3 = other_headlines[col_size*2:]

    # 7. Render the HTML template
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("index.html.j2")
    output_html = template.render(
        main_headline=main_headline,
        column1=column1,
        column2=column2,
        column3=column3
    )

    # 8. Write the final HTML file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

    print(f"Successfully generated new index.html with Drudge-style layout.")
