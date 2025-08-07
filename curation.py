import os
import jinja2
import feedparser
import arxiv
import google.generativeai as genai
import time
from datetime import datetime, timezone
import random
import tldextract
from bs4 import BeautifulSoup
import concurrent.futures
import requests
import pickle
import asyncio
import aiohttp

# --- CONFIGURATION ---

try:
    gemini_api_key = os.getenv('GEMINI_API_KEY')
    if not gemini_api_key:
        raise KeyError("GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=gemini_api_key)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')
except KeyError as e:
    print(f"ERROR: {e}")
    exit(1)

# New: Organized RSS feeds by category
RSS_FEEDS_BY_CATEGORY = {
    "wall": [
        "https://www.reuters.com/rssFeed/businessNews",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=yhoo&region=US&lang=en-US",
        "http://www.marketwatch.com/rss/topstories",
    ],
    "main": [
        "http://rss.cnn.com/rss/cnn_topstories.rss",
        "http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml",
        "https://www.npr.org/rss/rss.php?id=1001",
    ],
    "meme": [
        "https://www.reddit.com/r/wallstreetbets/.rss",
        "https://www.reddit.com/r/stocks/.rss",
        "https://www.forbes.com/feed/",
    ],
    # Your original AI feeds can go here if you want them in their own category
    "ai_news": [
        "http://www.theverge.com/rss/group/ai-artificial-intelligence/index.xml",
        "https://techcrunch.com/category/artificial-intelligence/feed/",
        #... add the rest of your original feeds
    ]
}

MAX_ARTICLES_PER_SOURCE = 2
MAX_TOTAL_ARTICLES = 50 # Increased total articles to accommodate more feeds
MAX_TECHNICAL_ARTICLES = 3
CACHE_FILE = 'rss_cache.pkl'
CACHE_TTL = 1800

# Style options for random assignment
STYLE_CLASSES = ['style1', 'style2', 'style3', 'style4']

# Source mapping for friendly names
SOURCE_MAP = {
    'theverge': 'The Verge',
    'techcrunch': 'TechCrunch',
    'wired': 'Wired',
    'mit': 'MIT News',
    'googleblog': 'Google AI',
    'marktechpost': 'MarkTechPost',
    'unite': 'Unite.AI',
    'venturebeat': 'VentureBeat',
    'futurism': 'Futurism',
    'singularityhub': 'Singularity Hub',
    'openai': 'OpenAI',
    'deepmind': 'DeepMind',
    'analyticsvidhya': 'Analytics Vidhya',
    'oreilly': "O'Reilly",
    'dailyai': 'DailyAI',
    'x': 'X',
    'twitter': 'X',
    'bbc': 'BBC',
    'cnn': 'CNN',
    'nytimes': 'The New York Times',
    'crunchbase': 'Crunchbase',
    'businesswire': 'BusinessWire',
    'prnewswire': 'PR Newswire',
    'reuters': 'Reuters',
    'yahoo': 'Yahoo Finance',
    'marketwatch': 'MarketWatch',
    'reddit': 'Reddit',
    'npr': 'NPR',
    'forbes': 'Forbes',
}

# AI relevance keywords (now used for boosting, not filtering)
AI_KEYWORDS = [
    'ai ', 'artificial intelligence', 'machine learning', 'neural network', 'deep learning',
    'llm', 'generative ai', 'chatgpt', 'gpt', 'model', 'algorithm', 'robotics', 'computer vision',
    'natural language processing', 'nlp', 'reinforcement learning', 'ai hardware', 'ai software',
    'agi', 'autonomous', 'predictive analytics'
]

# M&A keywords for boost
MA_KEYWORDS = ['merger', 'acquisition', 'm&a', 'buyout', 'investment', 'funding round', 'venture capital', 'acquired', 'merged']

# Key people moves keywords
PEOPLE_KEYWORDS = ['hire', 'hires', 'leaves', 'joins', 'promoted', 'ceo', 'executive', 'cfo', 'cto', 'resigns', 'appointment']

# Breakthrough/excitement keywords
BREAKTHROUGH_KEYWORDS = ['breakthrough', 'revolution', 'game-changing', 'transformative', 'new model', 'agi', 'hardware advance', 'software breakthrough', 'innovation', 'first-ever', 'unveils', 'launches']

# Key AI people for extra boost (curated list)
KEY_AI_PEOPLE = [
    'sam altman', 'elon musk', 'jensen huang', 'satya nadella', 'sundar pichai',
    'demis hassabis', 'ila sutskever', 'andrew ng', 'fei-fei li', 'yann lecun',
    'tim cook', 'mark zuckerberg', 'jeff bezos', 'dario amodei'
]

# Updated Fortune tiers (from 2024 data)
fortune_top_20 = [
    'Walmart', 'Amazon', 'Apple', 'UnitedHealth Group', 'Berkshire Hathaway', 'CVS Health', 'ExxonMobil',
    'Alphabet', 'McKesson Corporation', 'Cencora', 'Costco', 'JPMorgan Chase', 'Microsoft', 'Cardinal Health',
    'Chevron Corporation', 'Cigna', 'Ford Motor Company', 'Bank of America', 'General Motors', 'Elevance Health'
]
fortune_21_to_50 = [
    'Citigroup', 'Centene', 'The Home Depot', 'Marathon Petroleum', 'Kroger', 'Phillips 66', 'Fannie Mae',
    'Walgreens Boots Alliance', 'Valero Energy', 'Meta Platforms', 'Verizon Communications', 'AT&T', 'Comcast',
    'Wells Fargo', 'Goldman Sachs', 'Freddie Mac', 'Target Corporation', 'Humana', 'State Farm', 'Tesla',
    'Morgan Stanley', 'Johnson & Johnson', 'Archer Daniels Midland', 'PepsiCo', 'United Parcel Service',
    'FedEx', 'The Walt Disney Company', 'Dell Technologies', "Lowe's", 'Procter & Gamble'
]
fortune_51_to_100 = [
    'Energy Transfer Partners', 'Boeing', 'Albertsons', 'Sysco', 'RTX Corporation', 'General Electric',
    'Lockheed Martin', 'American Express', 'Caterpillar', 'MetLife', 'HCA Healthcare', 'Progressive Corporation',
    'IBM', 'John Deere', 'Nvidia', 'StoneX Group', 'Merck & Co.', 'ConocoPhillips', 'Pfizer', 'Delta Air Lines',
    'TD Synnex', 'Publix', 'Allstate', 'Cisco', 'Nationwide Mutual Insurance Company', 'Charter Communications',
    'AbbVie', 'New York Life Insurance Company', 'Intel', 'TJX', 'Prudential Financial', 'HP', 'United Airlines',
    'Performance Food Group', 'Tyson Foods', 'American Airlines', 'Liberty Mutual', 'Nike', 'Oracle Corporation',
    'Enterprise Products', 'Capital One Financial', 'Plains All American Pipeline', 'World Kinect Corporation',
    'AIG', 'Coca-Cola', 'TIAA', 'CHS', 'Bristol-Myers Squibb', 'Dow Chemical Company', 'Best Buy'
]
fortune_101_to_500 = []

# Popular AI companies (expanded)
popular_ai_companies = [
    'Microsoft', 'NVIDIA', 'Google', 'Alphabet', 'Amazon', 'Meta', 'IBM', 'OpenAI', 'Salesforce',
    'Oracle', 'SAP', 'Baidu', 'Alibaba', 'Tesla', 'Apple', 'Adobe', 'Intel', 'AMD', 'Qualcomm',
    'Anthropic', 'xAI', 'DeepMind', 'Hugging Face', 'Stability AI', 'Cohere', 'Mistral AI'
]

# --- FUNCTIONS ---

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'rb') as f:
            cache = pickle.load(f)
        if time.time() - cache.get('timestamp', 0) < CACHE_TTL:
            return cache.get('articles', [])
    return None

def save_cache(articles):
    with open(CACHE_FILE, 'wb') as f:
        pickle.dump({'timestamp': time.time(), 'articles': articles}, f)

def fetch_feed(feed_url):
    """Fetch a single feed with timeout."""
    try:
        response = requests.get(feed_url, timeout=10)
        response.raise_for_status()
        feed = feedparser.parse(response.content)
    except Exception as e:
        print(f"Error fetching {feed_url}: {e}")
        feed = {'entries': []}
    return feed, feed_url

def get_articles_from_rss():
    """Fetches RSS feeds in parallel, with caching."""
    start_time = time.time()
    cached_articles = load_cache()
    if cached_articles:
        print("Using cached RSS articles")
        return cached_articles

    articles = []
    # Loop through the new category-based dictionary
    for category, urls in RSS_FEEDS_BY_CATEGORY.items():
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_url = {executor.submit(fetch_feed, url): url for url in urls}
            for future in concurrent.futures.as_completed(future_to_url):
                feed, feed_url = future.result()
                extracted = tldextract.extract(feed_url)
                domain = extracted.domain.lower()
                source_name = SOURCE_MAP.get(domain, extracted.domain.capitalize())
                for entry in feed.get('entries', [])[:MAX_ARTICLES_PER_SOURCE]:
                    if entry.get('title') and entry.get('link'):
                        article = {'title': entry.title, 'url': entry.link}
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
                        if not image_url and 'summary' in entry:
                            soup = BeautifulSoup(entry.summary, 'html.parser')
                            img = soup.find('img')
                            if img and img.get('src'):
                                image_url = img['src']
                        article['image_url'] = image_url
                        if 'summary' in entry:
                            article['summary'] = entry.summary
                        else:
                            article['summary'] = "No summary available."
                        if 'published_parsed' in entry and entry.published_parsed:
                            dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                        elif 'updated_parsed' in entry and entry.updated_parsed:
                            dt = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                        else:
                            dt = datetime.min
                        article['published'] = dt.replace(tzinfo=timezone.utc)
                        article['source'] = source_name
                        article['category'] = category # Set the category here
                        articles.append(article)
    save_cache(articles)
    print(f"RSS fetching took {time.time() - start_time:.2f} seconds")
    return articles

def get_articles_from_arxiv():
    """Fetches recent research papers from arXiv (this will not be used in the new category-based layout)."""
    return []

def is_ai_related(title, summary):
    """Placeholder function, as we now use category-specific feeds."""
    return True

async def async_get_headline_and_score(title, summary):
    """Async wrapper for Gemini API call."""
    fallback_headline = title.strip()
    prompt = f"""
    Analyze the following article title and summary.
    First, on a scale of 1 to 20, rate how provocative, sensational, and AI-specific it is. Higher scores for stories evoking strong emotions, controversy, breakthroughs, or business impacts in AI.
    Second, rewrite the title as an ultra-sensational, viral, clickbait-style headline that's irresistible—evoke curiosity, fear, excitement, FOMO, or shock while staying completely factual and not lying. Use sentence case (capitalize first letter and proper names). If a major company or business is mentioned in the title or summary, include it prominently at the beginning. Keep it punchy and under 15 words.
    Third, if this seems technical/academic or a breakthrough in AI HW/SW, rate its importance/impact on a scale of 1-10 (higher for game-changers); otherwise, return 0.

    Respond with the score, the headline, and tech_importance separated by pipe characters (|). For example: 18|Microsoft unleashes AI revolution that could change everything!|8

    Article Title: "{title}"
    Article Summary: "{summary[:500]}"
    """
    try:
        response = await gemini_model.generate_content_async(prompt)
        parts = response.text.strip().split('|', 2)
        if len(parts) == 3:
            score = int(parts[0].strip())
            headline = parts[1].strip().replace('*', '')
            tech_importance = int(parts[2].strip())
            return headline, score, tech_importance
        else:
            return fallback_headline, 5, 0
    except Exception as e:
        print(f"Error processing title '{title}': {e}")
        await asyncio.sleep(2)
        return fallback_headline, 5, 0

def get_related_image_url(headline):
    """Generate or fetch a related image URL based on the headline (placeholder logic)."""
    keywords = headline.lower().split()
    if any(kw in ['ai', 'artificial', 'intelligence', 'machine', 'learning'] for kw in keywords):
        return f"https://source.unsplash.com/600x300/?ai,technology"
    return "https://via.placeholder.com/600x300?text=AI+Headline+Image"

def get_boost(title, summary, source):
    """Calculate boost based on company mentions, M&A, people moves, breakthroughs."""
    text = (title + " " + summary).lower()
    boost = 0
    for company in popular_ai_companies:
        if company.lower() in text:
            boost += 10
    for company in fortune_top_20:
        if company.lower() in text:
            boost += 30
    for company in fortune_21_to_50:
        if company.lower() in text:
            boost += 20
    for company in fortune_51_to_100:
        if company.lower() in text:
            boost += 10
    if any(kw in text for kw in MA_KEYWORDS):
        boost += 25
    if any(kw in text for kw in PEOPLE_KEYWORDS):
        boost += 20
        if any(person in text for person in KEY_AI_PEOPLE):
            boost += 15
    if any(kw in text for kw in BREAKTHROUGH_KEYWORDS):
        boost += 30
    technical_sources = ['arXiv', 'MIT News', "O'Reilly"]
    if source in technical_sources:
        boost += 5
    if source in technical_sources and boost < 10:
        boost -= 5
    return min(max(boost, 0), 100)

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    overall_start = time.time()
    print("Starting content generation for BWNewsHub...")

    fetch_start = time.time()
    all_articles = get_articles_from_rss()
    print(f"Article fetching took {time.time() - fetch_start:.2f} seconds")

    filter_start = time.time()
    unique_articles = []
    seen_urls = set()
    for article in all_articles:
        if article.get('url') and article['url'] not in seen_urls:
            unique_articles.append(article)
            seen_urls.add(article['url'])
    articles_to_process = unique_articles
    print(f"Selected {len(articles_to_process)} articles.")
    print(f"Filtering took {time.time() - filter_start:.2f} seconds")

    process_start = time.time()
    async def process_articles_async():
        tasks = [async_get_headline_and_score(article['title'], article['summary']) for article in articles_to_process]
        return await asyncio.gather(*tasks)

    loop = asyncio.get_event_loop()
    headline_results = loop.run_until_complete(process_articles_async())

    processed_articles = []
    for article, (headline, sens_score, tech_importance) in zip(articles_to_process, headline_results):
        pub_date = article['published']
        if pub_date == datetime.min.replace(tzinfo=timezone.utc):
            pub_date = datetime.now(timezone.utc)
        related_image_url = article.get('image_url') or get_related_image_url(headline)
        style = random.choice(STYLE_CLASSES)
        boost = get_boost(article['title'], article['summary'], article.get('source', ''))
        final_score = sens_score + boost + tech_importance
        processed_articles.append({
            'headline': headline,
            'url': article['url'],
            'score': final_score,
            'image_url': article.get('image_url'),
            'related_image_url': related_image_url,
            'summary': article.get('summary', "No summary available."),
            'source': article.get('source', 'Unknown Source'),
            'published': pub_date.isoformat(),
            'style': style,
            'category': article['category']
        })
        print(f"  -> Category: {article['category']}, Final Score: {final_score}, Headline: {headline}")

    print(f"Article processing (API calls) took {time.time() - process_start:.2f} seconds")

    # Final sorting by date (latest first)
    processed_articles.sort(key=lambda x: x['published'], reverse=True)

    # Group articles by category for the template
    wall_street_articles = [a for a in processed_articles if a['category'] == 'wall']
    main_street_articles = [a for a in processed_articles if a['category'] == 'main']
    meme_street_articles = [a for a in processed_articles if a['category'] == 'meme']

    # Render the HTML template
    template_loader = jinja2.FileSystemLoader(searchpath="./templates")
    template_env = jinja2.Environment(loader=template_loader)
    template = template_env.get_template("index.html.j2")
    output_html = template.render(
        articles=processed_articles,
        wall_street_articles=wall_street_articles,
        main_street_articles=main_street_articles,
        meme_street_articles=meme_street_articles,
        current_year=datetime.now().year
    )

    # Write the final HTML file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

    print(f"Successfully generated new index.html with categorized layout.")
    print(f"Total runtime: {time.time() - overall_start:.2f} seconds")
