from jinja2 import Environment, FileSystemLoader, select_autoescape

# Example article data — replace with your actual data collection logic
articles = [
    {
        "title": "Article 1",
        "summary": "Summary of article 1.",
        "url": "https://example.com/article1",
        "image_url": "https://example.com/image1.jpg",
        "category": "wall",
        "style": "highlight"
    },
    {
        "title": "Article 2",
        "summary": "Summary of article 2.",
        "url": "https://example.com/article2",
        "image_url": "https://example.com/image2.jpg",
        "category": "main",
        "style": "normal"
    },
    # Add more articles here...
]

# Set up Jinja2 environment to load templates from current directory
env = Environment(
    loader=FileSystemLoader(searchpath='.'),
    autoescape=select_autoescape(['html', 'xml'])
)

# Load your template file
template = env.get_template('index.html.j2')

# Render template with articles
rendered_html = template.render(articles=articles)

# Write rendered HTML to index.html
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(rendered_html)

print("✅ index.html successfully generated")
