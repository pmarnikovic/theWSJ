import os
import jinja2
import feedparser
import arxiv
import google.generativeai as genai
import time
from datetime import datetime, timezone
import random  # Added for random headline styles

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
            source_name = feed.feed.get('title', 'Unknown Source').split()[0] if feed.feed.get('title') else 'Unknown'  # Get short source name
            for entry in feed.entries[:MAX_ARTICLES_PER_SOURCE]:
                if entry.get('title') and entry.get('link'):
                    article = {'title': entry.title, 'url': entry.link}
                    # Extract image URL if available
                    image_url = None
                    if 'media_content' in entry and entry.media_content:
                        image_url = entry.media_content[0].get('url')
                    elif 'media_thumbnail' in entry and entry.media_thumbnail:
                        image_url = entry.media_thumbnail[0].get('url')
                    elif 'enclosures' in entry and entry.enclosures:
                        for enc in entry.enclosures:
                            if 'image' in enc.get('type', ''):
                                image_url = enc.get('href')
                                break
                    article['image_url'] = image_url
                    if 'summary' in entry:
                        article['summary'] = entry.summary
                    else:
                        article['summary'] = "No summary available."
                    if 'published_parsed' in entry and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        article['published'] = dt.replace(tzinfo=timezone.utc)
                    else:
                        article['published'] = datetime.min.replace(tzinfo=timezone.utc)  # Use min to sort last if missing
                    article['source'] = source_name  # Add short source
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
            articles.append({
                'title': result.title,
                'url': result.entry_id,
                'published': result.published,
                'image_url': None,
                'summary': result.summary if result.summary else "No summary available.",
                'source': 'arXiv'  # Add short source
            })
    except Exception as e:
        print(f"Error fetching from arXiv: {e}")
    return articles

def get_headline_and_score(title):
    """Uses a single Gemini API call to get both a headline and a sensationalism score."""
    fallback_headline = title.strip()
    prompt = f"""
    Analyze the following article title. First, on a scale of 1 to 10, rate how provocative and sensational it is. Higher scores for titles that evoke strong emotions, controversy, or breakthroughs.
    Second, rewrite the title as an irresistible, punchy, and sensational headline in sentence case, like normal grammar: capitalize the first letter and proper names, but keep the rest lowercase.

    Respond with the score and the headline separated by a pipe character (|). For example: 8|Scientists unleash 'child' AI... fears grow...

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
            return fallback_headline, 5
    except Exception as e:
        print(f"Error processing title '{title}': {e}")
        return fallback_headline, 5

def get_related_image_url(headline):
    """Generate or fetch a related image URL based on the headline (placeholder logic)."""
    keywords = headline.lower().split()
    if any(kw in ['ai', 'artificial', 'intelligence', 'machine', 'learning'] for kw in keywords):
        return f"https://source.unsplash.com/600x300/?ai,technology"  # Generic AI image
    return "https://via.placeholder.com/600x300?text=AI+Headline+Image"  # Fallback

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
        pub_date = article['published']
        if pub_date == datetime.min.replace(tzinfo=timezone.utc):
            pub_date = datetime.now(timezone.utc)
        related_image_url = get_related_image_url(headline)  # Add related image
        processed_articles.append({
            'headline': headline,
            'url': article['url'],
            'score': score,
            'image_url': article.get('image_url'),
            'related_image_url': related_image_url,
            'summary': article.get('summary', "No summary available."),
            'source': article.get('source', 'Unknown Source'),
            'published': pub_date.isoformat()
        })
        print(f"  -> Score: {score}, Headline: {headline}, Related Image: {related_image_url}")

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
