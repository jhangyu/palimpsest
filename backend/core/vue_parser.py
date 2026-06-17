# backend/core/vue_parser.py
"""Shared Vue template JSON parsing utilities"""
import re
import json
from typing import Optional, Tuple
from datetime import datetime


def log_with_time(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# Keys to search for date extraction (order matters)
DATE_KEYS = ['to_publish_time', 'updated_at', 'date', 'my_publish_date', 'publish_time']
# Keys to search for image extraction (order matters)
IMAGE_KEYS = ['large', 'medium', 'feature_picture', 'thumbnail', 'cover', 'hero_image', 'cover_image']
# Keys to search for author extraction (order matters)
AUTHOR_KEYS = ['author', 'writer', 'editor', 'author_name', 'nickname']


def strip_vue_bindings(text: str) -> str:
    """Remove Vue binding syntax (:attr=, @click=, v-if=, etc.)"""
    text = re.sub(r'[:@](\w+)="[^"]*"', '', text)
    text = re.sub(r'v-\w+="[^"]*"', '', text)
    return text


def extract_vue_json(html_content: str) -> Optional[str]:
    """
    Extract Vue template JSON content.
    Returns the JSON string between <template> tags, with Vue bindings stripped.
    Returns None if no valid template found.
    """
    first_template_match = re.search(r'<template\b[^>]*>', html_content)
    if not first_template_match:
        return None

    content_start = first_template_match.end()

    # Track nested template tags depth
    depth = 1
    pos = content_start
    template_end = None

    open_tag_pattern = re.compile(r'<template\b', re.IGNORECASE)
    close_tag_pattern = re.compile(r'</template>', re.IGNORECASE)

    while pos < len(html_content) and depth > 0:
        next_open = open_tag_pattern.search(html_content, pos)
        next_close = close_tag_pattern.search(html_content, pos)

        if next_close is None:
            break

        if next_open is not None and next_open.start() < next_close.start():
            depth += 1
            pos = next_open.end()
        else:
            depth -= 1
            if depth == 0:
                template_end = next_close.start()
                break
            pos = next_close.end()

    if template_end is None:
        return None

    template_content = html_content[content_start:template_end].strip()
    return strip_vue_bindings(template_content)


def parse_vue_json(template_content: str) -> Optional[dict]:
    """Parse cleaned template content as JSON"""
    try:
        return json.loads(template_content)
    except json.JSONDecodeError as e:
        log_with_time(f"[VueParser] JSON parse error: {e}")
        return None


def extract_date_from_vue_data(data: dict) -> str:
    """Extract publication date from parsed Vue JSON data"""
    for key in DATE_KEYS:
        if key in data and data[key]:
            return str(data[key])
    return datetime.now().isoformat()


def extract_image_from_vue_data(data: dict) -> Optional[str]:
    """Extract image URL from parsed Vue JSON data"""
    for key in IMAGE_KEYS:
        if key in data and data[key]:
            return data[key]
    return None


def extract_author_from_vue_data(data: dict) -> Optional[str]:
    """Extract author name from parsed Vue JSON data"""
    for key in AUTHOR_KEYS:
        if key in data and data[key]:
            val = data[key]
            if isinstance(val, dict):
                return val.get('nickname') or val.get('name') or str(val)
            return str(val)
    return None


def extract_vue_content(html_content: str) -> Tuple[Optional[str], Optional[dict]]:
    """
    Extract content HTML and parsed data from Vue template page.

    Returns:
        (content_html, vue_data) - content_html is the html field if present,
        vue_data is the parsed JSON dict
    """
    cleaned = extract_vue_json(html_content)
    if not cleaned:
        return None, None

    data = parse_vue_json(cleaned)
    if not data:
        return None, None

    # Check for 'html' field (primary content)
    if isinstance(data, dict) and 'html' in data:
        html_field = data['html']
        if isinstance(html_field, str) and len(html_field) > 100:
            return html_field, data

    return None, data

