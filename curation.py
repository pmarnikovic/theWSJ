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

# List of RSS feeds to parse for AI news (enhanced with more business/M&A focused sources)
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
    # Added for M&A and business focus
    "https://www.crunchbase.com/text/rss/search/funding_rounds",  # General funding/M&A; will filter for AI
    "https://www.businesswire.com/rss/topic/Artificial+Intelligence",  # BusinessWire AI press releases (M&A, hires)
    "https://www.prnewswire.com/rss/artificial-intelligence-news.rss",  # PR Newswire AI (business announcements)
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
    'crunchbase': 'Crunchbase',
    'businesswire': 'BusinessWire',
    'prnewswire': 'PR Newswire',
    # Add more as needed for other sources
}

# AI relevance keywords (to filter non-AI stories)
AI_KEYWORDS = [
    'ai ', 'artificial intelligence', 'machine learning', 'neural network', 'deep learning', 
    'llm', 'generative ai', 'chatgpt', 'gpt', 'model', 'algorithm', 'robotics', 'computer vision',
    'natural language processing', 'nlp', 'reinforcement learning', 'ai hardware', 'ai software',
    'agi', 'autonomous', 'predictive analytics'  # Add more as needed
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
    'tim cook', 'mark zuckerberg', 'jeff bezos', 'dario amodei'  # Add more
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
fortune_101_to_500 = []  # Can add if needed for minor boosts

# Popular AI companies (expanded)
popular_ai_companies = [
    'Microsoft', 'NVIDIA', 'Google', 'Alphabet', 'Amazon', 'Meta', 'IBM', 'OpenAI', 'Salesforce',
    'Oracle', 'SAP', 'Baidu', 'Alibaba', 'Tesla', 'Apple', 'Adobe', 'Intel', 'AMD', 'Qualcomm',
    'Anthropic', 'xAI', 'DeepMind', 'Hugging Face', 'Stability AI', 'Cohere', 'Mistral AI'
    # Add more from Forbes AI 50 or similar
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

def is_ai_related(title, summary):
    """Check if the article is AI-related using keywords."""
    text = (title + " " + summary).lower()
    return any(kw in text for kw in AI_KEYWORDS)

def get_headline_and_score(title, summary):
    """Uses a single Gemini API call to get both a headline and a sensationalism score. Enhanced for sensationalism and business names."""
    fallback_headline = title.strip()
    prompt = f"""
    Analyze the following article title and summary.
    First, on a scale of 1 to 20, rate how provocative, sensational, and AI-specific it is. Higher scores for stories evoking strong emotions, controversy, breakthroughs, or business impacts in AI.
    Second, rewrite the title as an ultra-sensational, viral, clickbait-style headline that's irresistible—evoke curiosity, fear, excitement, FOMO, or shock while staying completely factual and not lying. Use sentence case (capitalize first letter and proper names). If a major company or business is mentioned in the title or summary, include it prominently at the beginning. Keep it punchy and under 15 words.
    Third, if this seems technical/academic or a breakthrough in AI HW/SW, rate its importance/impact on a scale of 1-10 (higher for game-changers); otherwise, return 0.

    Respond with the score, the headline, and tech_importance separated by pipe characters (|). For example: 18|Microsoft unleashes AI revolution that could change everything!|8

    Article Title: "{title}"
    Article Summary: "{summary[:500]}"  # Limit summary length for prompt
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

def get_boost(title, summary, source):
    """Calculate boost based on company mentions, M&A, people moves, breakthroughs."""
    text = (title + " " + summary).lower()
    boost = 0

    # Boost for popular AI companies
    for company in popular_ai_companies:
        if company.lower() in text:
            boost += 10  # Increased boost for AI business involvement

    # Tiered boosts for Fortune companies
    for company in fortune_top_20:
        if company.lower() in text:
            boost += 30  # High for top 20
    for company in fortune_21_to_50:
        if company.lower() in text:
            boost += 20
    for company in fortune_51_to_100:
        if company.lower() in text:
            boost += 10
    # For 101-500: boost += 5 if added

    # M&A boost
    if any(kw in text for kw in MA_KEYWORDS):
        boost += 25  # High priority for M&A

    # Key people moves boost
    if any(kw in text for kw in PEOPLE_KEYWORDS):
        boost += 20
        # Extra if key AI person mentioned
        if any(person in text for person in KEY_AI_PEOPLE):
            boost += 15

    # Breakthrough/excitement boost
    if any(kw in text for kw in BREAKTHROUGH_KEYWORDS):
        boost += 30  # High for game-changers

    # Small boost for technical articles (smaller mixture)
    if source == 'arXiv':
        boost += 5

    # Penalty for overly technical without company mentions or excitement
    technical_sources = ['arXiv', 'MIT News', "O'Reilly"]
    if source in technical_sources and boost < 10:
        boost -= 5

    return min(max(boost, 0), 100)  # Cap boost, no negative

# --- MAIN EXECUTION ---

if __name__ == "__main__":
    print("Starting content generation for Exhaustive AI...")

    # 1. Fetch and deduplicate articles
    all_articles = get_articles_from_rss() + get_articles_from_arxiv()
    seen_urls = set()
    unique_articles = []
    for article in all_articles:
        if article.get('url') and article['url'] not in seen_urls:
            # AI relevance filter
            if is_ai_related(article['title'], article['summary']):
                unique_articles.append(article)
                seen_urls.add(article['url'])
            else:
                print(f"Discarded non-AI article: {article['title']}")

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
    print(f"Selected the top {len(articles_to_process)} most recent AI-related articles.")

    # 3. Generate headlines, scores, and random styles for each article
    processed_articles = []
    for article in articles_to_process:
        print(f"Processing: {article['title']}")
        headline, sens_score, tech_importance = get_headline_and_score(article['title'], article['summary'])
        pub_date = article['published']
        if pub_date == datetime.min.replace(tzinfo=timezone.utc):
            pub_date = datetime.now(timezone.utc)
        related_image_url = get_related_image_url(headline)  # Add related image
        style = random.choice(['style1', 'style2', 'style3', 'style4'])  # Random style per headline
        # New: Calculate boost
        boost = get_boost(article['title'], article['summary'], article.get('source', ''))
        final_score = sens_score + boost + tech_importance
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
        print(f"  -> Sens Score: {sens_score}, Boost: {boost}, Tech Imp: {tech_importance}, Final Score: {final_score}, Headline: {headline}, Related Image: {related_image_url}, Style: {style}")
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
