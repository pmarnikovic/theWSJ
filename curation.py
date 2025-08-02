import os
import jinja2
import feedparser
import arxiv
import google.generativeai as genai
import time
from datetime import datetime, timezone
import random  # Added for random styles
import tldextract  # Added for better source parsing
from bs4 import BeautifulSoup  # Added for parsing embedded images in summaries

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
    "https://dailyai.com/feed/",
    "https://news.microsoft.com/source/topics/ai/feed/",  # Microsoft AI: Business innovations, enterprise stories
    "https://www.fastcompany.com/section/artificial-intelligence/rss",  # Fast Company AI: Strategic business impacts
    "https://aibusiness.com/rss.xml",  # AI Business: Enterprise AI adoption and strategies
    "https://www.eweek.com/artificial-intelligence/feed/",  # eWeek AI: Enterprise tech reviews, large-company focus
    "https://www.infoworld.com/artificial-intelligence/feed/",  # InfoWorld AI: Business AI tools and strategies
    "https://news.crunchbase.com/sections/ai/feed/",  # Crunchbase AI: Funding, business deals in AI
    "https://aws.amazon.com/blogs/aws/category/artificial-intelligence/feed/",  # AWS AI: Enterprise cloud AI strategies
    "https://emerj.com/feed/",  # Emerj: AI for Global 2000/enterprise leaders
    "https://stratechery.com/feed/",  # Stratechery: Tech/AI business strategy analysis
    "https://www.enterpriseai.news/feed/",  # EnterpriseAI: AI adoption in large companies
]

MAX_ARTICLES_PER_SOURCE = 3
MAX_TOTAL_ARTICLES = 25
MAX_TECHNICAL_ARTICLES = 3

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
    # Added more mappings for potential future sources or variations
    'x': 'X',
    'twitter': 'X',
    'bbc': 'BBC',
    'cnn': 'CNN',
    'nytimes': 'The New York Times',
    # Add more as needed for other sources
}

# New: Company lists for scoring boosts (based on 2024 Fortune 500 and top AI reports)
# Fortune tiers (expand with full lists from fortune.com/ranking/fortune500/2024/)
fortune_top_20 = [
    'Walmart', 'Amazon', 'Apple', 'UnitedHealth Group', 'Berkshire Hathaway', 'CVS Health', 'ExxonMobil',
    'Alphabet', 'McKesson', 'Cencora', 'Costco', 'JPMorgan Chase', 'Microsoft', 'Cardinal Health',
    'Chevron', 'Cigna', 'Ford Motor', 'Bank of America', 'General Motors', 'Elevance Health'
]
fortune_21_to_50 = [  # Approximate/known from public data; verify and expand
    'Home Depot', 'Verizon', 'Pfizer', 'PepsiCo', 'UPS', 'Walt Disney', 'Energy Transfer', 'Fannie Mae',
    'Goldman Sachs', 'Sysco', 'RTX', 'Boeing', 'Citigroup', 'IBM', 'HCA Healthcare', 'Lockheed Martin',
    'Morgan Stanley', 'Intel', 'HP', 'Dow', 'Caterpillar', 'Merck', 'World Fuel Services', 'New York Life Insurance',
    'AbbVie', 'Plains All American Pipeline', 'Enterprise Products Partners', 'Abbott Laboratories', 'CHS'
    # Add more up to 50
]
fortune_51_to_100 = [  # Approximate; expand as needed
    'Tesla', 'Delta Air Lines', 'American Airlines Group', 'Publix Super Markets', 'Meta Platforms', 'NVIDIA',
    'Oracle', 'Thermo Fisher Scientific', 'Nike', 'Best Buy', 'Bristol-Myers Squibb', 'Phillips 66',
    'USAA', 'FedEx', 'State Farm Insurance', 'Freddie Mac', 'Comcast', 'Wells Fargo', '3M', 'ConocoPhillips',
    # Add more up to 100
]
fortune_101_to_500 = []  # Add lower-tier companies if desired for minor boosts

# Popular AI companies (established leaders for extra boost)
popular_ai_companies = [
    'Microsoft', 'NVIDIA', 'Google', 'Alphabet', 'Amazon', 'Meta', 'IBM', 'OpenAI', 'Salesforce',
    'Oracle', 'SAP', 'Baidu', 'Alibaba', 'Tesla', 'Apple', 'Adobe', 'Intel', 'AMD', 'Qualcomm'
    # Add more from reports like eWeek or Forbes AI 50
]

# --- FUNCTIONS ---

def get_articles_from_rss():
    """Fetches and parses articles from the list of RSS feeds."""
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            # Extract source from URL using tldextract
            extracted = tldextract.extract(feed_url)
            domain = extracted.domain.lower()
            source_name = SOURCE_MAP.get(domain, extracted.domain.capitalize())
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
                    # Check for embedded image in summary if still none
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
                    # Use published or updated date
                    if 'published_parsed' in entry and entry.published_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.published_parsed))
                    elif 'updated_parsed' in entry and entry.updated_parsed:
                        dt = datetime.fromtimestamp(time.mktime(entry.updated_parsed))
                    else:
                        dt = datetime.min
                    article['published'] = dt.replace(tzinfo=timezone.utc)
                    article['source'] = source_name  # Add mapped source
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
    Second, rewrite the title as an ultra-irresistible, punchy, viral headline that's attention-grabbing like top BuzzFeed or Daily Mail styles—evoke curiosity, fear, or excitement while staying factual. Use sentence case, like normal grammar: capitalize the first letter and proper names, but keep the rest lowercase.
    Third, if this seems technical/academic, rate its importance/impact on a scale of 1-5 (higher for breakthroughs); otherwise, return 0.

    Respond with the score, the headline, and tech_importance separated by pipe characters (|). For example: 8|Scientists unleash 'child' AI... fears grow...|3

    Article Title: "{title}"
    """
    try:
        response = gemini_model.generate_content(prompt)
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
        time.sleep(2)  # Backoff on error
        return fallback_headline, 5, 0

def get_related_image_url(headline):
    """Generate or fetch a related image URL based on the headline (placeholder logic)."""
    keywords = headline.lower().split()
    if any(kw in ['ai', 'artificial', 'intelligence', 'machine', 'learning'] for kw in keywords):
        return f"https://source.unsplash.com/600x300/?ai,technology"  # Generic AI image
    return "https://via.placeholder.com/600x300?text=AI+Headline+Image"  # Fallback

def get_company_boost(title, summary, source):
    """Calculate boost based on company mentions in title/summary."""
    text = (title + " " + summary).lower()
    boost = 0

    # Boost for popular AI companies
    for company in popular_ai_companies:
        if company.lower() in text:
            boost += 3  # Strong boost for AI business involvement

    # Tiered boosts for Fortune companies
    for company in fortune_top_20:
        if company.lower() in text:
            boost += 5
    for company in fortune_21_to_50:
        if company.lower() in text:
            boost += 4
    for company in fortune_51_to_100:
        if company.lower() in text:
            boost += 3
    # For 101-500: boost += 2 per match, if you add the list

    # Small boost for technical articles (smaller mixture)
    if source == 'arXiv':
        boost += 1

    # Penalty for overly technical without company mentions
    technical_sources = ['arXiv', 'MIT News', "O'Reilly"]
    if source in technical_sources and boost == 0:
        boost -= 2

    return min(max(boost, -2), 10)  # Cap boost, allow small penalty

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

    # New: Limit technical articles
    technical_sources = ['arXiv', 'MIT News', "O'Reilly"]  # Add any others
    technical_articles = [a for a in unique_articles if a['source'] in technical_sources]
    non_technical_articles = [a for a in unique_articles if a['source'] not in technical_sources]
    
    # Sort and limit technical
    technical_articles.sort(key=lambda x: x['published'], reverse=True)
    technical_articles = technical_articles[:MAX_TECHNICAL_ARTICLES]
    
    # Recombine and sort by date
    unique_articles = non_technical_articles + technical_articles
    unique_articles.sort(key=lambda x: x['published'], reverse=True)
    articles_to_process = unique_articles[:MAX_TOTAL_ARTICLES]  # Limit before processing
    print(f"Selected the top {len(articles_to_process)} most recent articles.")

    # 3. Generate headlines, scores, and random styles for each article
    processed_articles = []
    for article in articles_to_process:
        print(f"Processing: {article['title']}")
        headline, sens_score, tech_importance = get_headline_and_score(article['title'])
        pub_date = article['published']
        if pub_date == datetime.min.replace(tzinfo=timezone.utc):
            pub_date = datetime.now(timezone.utc)
        related_image_url = get_related_image_url(headline)  # Add related image
        style = random.choice(['style1', 'style2', 'style3', 'style4'])  # Random style per headline
        # New: Calculate company boost
        company_boost = get_company_boost(article['title'], article['summary'], article.get('source', ''))
        final_score = sens_score + company_boost
        if article['source'] in technical_sources:
            final_score += tech_importance
        processed_articles.append({
            'headline': headline,
            'url': article['url'],
            'score': final_score,  # Use final_score for sorting
            'image_url': article.get('image_url'),
            'related_image_url': related_image_url,
            'summary': article.get('summary', "No summary available."),
            'source': article.get('source', 'Unknown Source'),
            'published': pub_date.isoformat(),
            'style': style  # Add random style class
        })
        print(f"  -> Sens Score: {sens_score}, Boost: {company_boost}, Tech Imp: {tech_importance}, Final Score: {final_score}, Headline: {headline}, Related Image: {related_image_url}, Style: {style}")
        time.sleep(1)  # Delay between API calls to respect rate limits

    # 4. Sort by final score to find the main headline
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
        column3=column3,
        current_year=datetime.now().year  # Added to support footer variable
    )

    # 8. Write the final HTML file
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(output_html)

    print(f"Successfully generated new index.html with Drudge-style layout.")
