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
            # For arXiv, no direct image; use a placeholder or None
            articles.append({
                'title': result.title,
                'url': result.entry_id,
                'published': result.published,
                'image_url': None  # Or a default image URL if desired
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
        pub_date = article['published']
        if pub_date == datetime.min.replace(tzinfo=timezone.utc):
            pub_date = datetime.now(timezone.utc)
        processed_articles.append({
            'headline': headline,
            'url': article['url'],
            'score': score,
            'image_url': article.get('image_url'),
            'published': pub_date.isoformat()  # Convert to ISO string for template
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
``````jinja2
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="description" content="Daily AI news aggregated from top sources, featuring sensational headlines and breakthroughs in artificial intelligence.">
    <meta name="keywords" content="AI news, artificial intelligence, AI report, machine learning, tech news">
    <title>Exhaustive AI</title>
    
    <!-- Add JSON-LD schema here -->
    {% if main_headline %}
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "NewsArticle",
      "headline": "{{ main_headline.headline }}",
      "image": "{{ main_headline.image_url or 'https://your-default-image-url.com/ai-placeholder.jpg' }}",
      "datePublished": "{{ main_headline.published }}",
      "author": {
        "@type": "Organization",
        "name": "Exhaustive AI"
      },
      "publisher": {
        "@type": "Organization",
        "name": "Exhaustive AI",
        "logo": {
          "@type": "ImageObject",
          "url": "https://your-logo-url.com/logo.png"
        }
      }
    }
    </script>
    {% endif %}
    
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #fff;
            color: #000;
            margin: 0;
            padding: 40px;  /* Increased padding for more space */
            text-align: center;
            line-height: 1.6;  /* Better line spacing */
        }
        h1 {
            font-size: 60px;  /* Larger title */
            font-weight: bold;
            margin: 0 0 40px;  /* More bottom margin */
        }
        .main-headline {
            font-size: 48px;  /* Even larger main headline */
            font-weight: bold;
            margin: 40px 0;  /* Increased spacing */
        }
        .main-headline a {
            color: #000;
            text-decoration: none;
        }
        .main-headline a:hover {
            text-decoration: underline;
        }
        .main-image {
            max-width: 800px;  /* Larger max width for image */
            height: auto;
            margin: 20px auto;
            display: block;
        }
        .columns {
            display: flex;
            justify-content: space-between;  /* Spread columns further */
            text-align: left;
            max-width: 1200px;  /* Limit total width for centering */
            margin: 0 auto;
        }
        .column {
            width: 32%;  /* Slightly narrower columns for more space between */
            padding: 20px;  /* Increased internal padding */
        }
        .headline {
            font-size: 24px;  /* Larger headline font */
            font-weight: bold;
            margin: 20px 0;  /* More vertical spacing between headlines */
        }
        .headline a {
            color: #000;
            text-decoration: none;
        }
        .headline a:hover {
            text-decoration: underline;
        }
        .headline img {
            max-width: 100%;
            height: auto;
            margin: 10px 0;
        }
        footer {
            margin-top: 60px;  /* Space above footer */
            padding-top: 20px;
            border-top: 2px solid #000;  /* Thicker line for separation */
            text-align: left;
        }
        footer h2 {
            font-size: 28px;
            margin-bottom: 20px;
        }
        footer ul {
            list-style-type: none;
            padding: 0;
            columns: 2;  /* Split into two columns for better spread */
            column-gap: 40px;
        }
        footer li {
            margin-bottom: 10px;
        }
        footer a {
            color: #000;
            text-decoration: none;
        }
        footer a:hover {
            text-decoration: underline;
        }
        /* Media queries for mobile optimization */
        @media (max-width: 768px) {  /* Target tablets and phones */
            .columns {
                flex-direction: column;  /* Stack columns vertically */
            }
            .column {
                width: 100%;  /* Full width on mobile */
                padding: 10px;  /* Reduce padding for smaller screens */
            }
            h1 {
                font-size: 36px;  /* Smaller title */
            }
            .main-headline {
                font-size: 28px;  /* Reduce main headline */
            }
            .headline {
                font-size: 18px;  /* Smaller sub-headlines */
            }
            .main-image, .headline img {
                max-width: 100%;  /* Ensure images don't overflow */
            }
        }
        @media (max-width: 480px) {  /* Extra tweaks for very small phones */
            body {
                padding: 20px;  /* Less side padding */
            }
            footer ul {
                columns: 1;  /* Single column in footer for mobile */
            }
        }
    </style>
</head>
<body>
    <h1>Exhaustive AI</h1>
    
    {% if main_headline %}
    <div class="main-headline">
        <a href="{{ main_headline.url }}">{{ main_headline.headline }}</a>
    </div>
    {% if main_headline.image_url %}
    <img src="{{ main_headline.image_url }}" alt="Main article image for {{ main_headline.headline }}" class="main-image" loading="lazy">
    {% endif %}
    {% endif %}
    
    <div class="columns">
        <div class="column">
            {% for item in column1 %}
            <div class="headline">
                <a href="{{ item.url }}">{{ item.headline }}</a>
                {% if item.image_url %}
                <img src="{{ item.image_url }}" alt="Article image for {{ item.headline }}" loading="lazy">
                {% endif %}
            </div>
            {% endfor %}
        </div>
        <div class="column">
            {% for item in column2 %}
            <div class="headline">
                <a href="{{ item.url }}">{{ item.headline }}</a>
                {% if item.image_url %}
                <img src="{{ item.image_url }}" alt="Article image for {{ item.headline }}" loading="lazy">
                {% endif %}
            </div>
            {% endfor %}
        </div>
        <div class="column">
            {% for item in column3 %}
            <div class="headline">
                <a href="{{ item.url }}">{{ item.headline }}</a>
                {% if item.image_url %}
                <img src="{{ item.image_url }}" alt="Article image for {{ item.headline }}" loading="lazy">
                {% endif %}
            </div>
            {% endfor %}
        </div>
    </div>

    <footer>
        <h2>Top 25 AI Websites</h2>
        <ul>
            <li><a href="https://openai.com">OpenAI</a></li>
            <li><a href="https://ai.google">Google AI</a></li>
            <li><a href="https://www.microsoft.com/en-us/ai">Microsoft AI</a></li>
            <li><a href="https://huggingface.co">Hugging Face</a></li>
            <li><a href="https://techcrunch.com/category/artificial-intelligence/">TechCrunch AI</a></li>
            <li><a href="https://venturebeat.com/category/ai/">VentureBeat AI</a></li>
            <li><a href="https://www.wired.com/tag/artificial-intelligence/">Wired AI</a></li>
            <li><a href="https://www.technologyreview.com/topic/artificial-intelligence/">MIT Technology Review</a></li>
            <li><a href="https://aimagazine.com">AI Magazine</a></li>
            <li><a href="https://www.analyticsvidhya.com">Analytics Vidhya</a></li>
            <li><a href="https://www.aitrends.com">AI Trends</a></li>
            <li><a href="https://news.mit.edu/topic/artificial-intelligence2">MIT News AI</a></li>
            <li><a href="https://www.dataversity.net">Dataversity</a></li>
            <li><a href="https://emerj.com">Emerj</a></li>
            <li><a href="https://www.kdnuggets.com">KDnuggets</a></li>
            <li><a href="https://www.analyticsinsight.net">Analytics Insight</a></li>
            <li><a href="https://insidebigdata.com">Inside Big Data</a></li>
            <li><a href="https://www.datasciencecentral.com">Data Science Central</a></li>
            <li><a href="https://developer.ibm.com">IBM Developer</a></li>
            <li><a href="https://intelligence.org">Machine Intelligence Research Institute</a></li>
            <li><a href="https://paperswithcode.com">Papers with Code</a></li>
            <li><a href="https://www.anthropic.com">Anthropic</a></li>
            <li><a href="https://stability.ai">Stability AI</a></li>
            <li><a href="https://www.perplexity.ai">Perplexity AI</a></li>
            <li><a href="https://www.artificialintelligence-news.com">Artificial Intelligence News</a></li>
        </ul>
    </footer>
</body>
</html>
