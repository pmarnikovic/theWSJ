import feedparser
from jinja2 import Environment, FileSystemLoader, select_autoescape

import re

def get_article_content(entry):
    """
    Safely retrieves article content, checking for common field names, including image URL.
    """
    title = getattr(entry, 'title', 'No Title Provided')

    # Check for summary or description
    summary = getattr(entry, 'summary', '')
    if not summary:
        summary = getattr(entry, 'description', 'No Summary Available')

    url = getattr(entry, 'link', '#')

    image_url = ""

    # 1. Check media_content
    if hasattr(entry, 'media_content'):
        media = entry.media_content
        if isinstance(media, list) and media:
            image_url = media[0].get('url', '')

    # 2. Check media_thumbnail
    if not image_url and hasattr(entry, 'media_thumbnail'):
        thumbnail = entry.media_thumbnail
        if isinstance(thumbnail, list) and thumbnail:
            image_url = thumbnail[0].get('url', '')

    # 3. Check enclosures
    if not image_url and hasattr(entry, 'enclosures'):
        for enclosure in entry.enclosures:
            if enclosure.get('type', '').startswith('image/'):
                image_url = enclosure.get('href', '')
                break

    # 4. Check entry.content (for Atom feeds like Reddit)
    if not image_url and hasattr(entry, 'content'):
        for content_block in entry.content:
            html = content_block.get('value', '')
            match = re.search(r'<img[^>]+src="([^">]+)"', html)
            if match:
                image_url = match.group(1)
                break

    # 5. Extract from <img> in summary
    if not image_url:
        match = re.search(r'<img[^>]+src="([^">]+)"', summary)
        if match:
            image_url = match.group(1)

    # Final fallback: omit image_url if none found
    if not image_url:
        image_url = None

    return {
        "title": title,
        "summary": summary,
        "url": url,
        **({"image_url": image_url} if image_url else {}),
        "style": "normal"
    }
