# backend/core/crawl_utils.py
"""Shared crawl utilities extracted from crawler.py"""
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from typing import Optional, Tuple, List, Dict, Any
from .vue_parser import (
    extract_vue_content,
    extract_date_from_vue_data,
    extract_image_from_vue_data,
    strip_vue_bindings,
)
from .ai import _sanitize_content_html


def normalize_selector(selector: str) -> str:
    """Standardize CSS selector, fix smart quotes"""
    if not selector:
        return selector
    selector = selector.replace('‘', "'")
    selector = selector.replace('’', "'")
    selector = selector.replace('“', '"')
    selector = selector.replace('”', '"')
    return selector


def extract_article_info(item, list_rules: dict, base_url: str) -> Optional[Dict[str, str]]:
    """
    Extract URL and title from a list item element.

    Args:
        item: BeautifulSoup element representing a list item
        list_rules: dict with 'link' and 'title' selectors
        base_url: base URL for resolving relative links

    Returns:
        dict with 'url' and 'title' keys, or None if extraction failed
    """
    link_selector = normalize_selector(list_rules.get('link', 'a'))
    title_selector = normalize_selector(list_rules.get('title', ''))

    try:
        link_el = item.select_one(link_selector)
        if not link_el:
            return None

        article_url = link_el.get('href', '')
        if not article_url:
            return None

        if not article_url.startswith('http'):
            article_url = urljoin(base_url, article_url)

        title = ""
        if title_selector:
            title_el = item.select_one(title_selector)
            title = title_el.get_text(strip=True) if title_el else ""

        if not title:
            title = link_el.get_text(strip=True) or "No Title"

        return {"url": article_url, "title": title}
    except (AttributeError, ValueError) as e:
        return None


def parse_article_content(
    c_html: str,
    content_rules: dict,
    is_vue_template: bool = False
) -> Tuple[str, str, Optional[str]]:
    """
    Parse article HTML to extract content, date, and image.

    Args:
        c_html: raw HTML content of article page
        content_rules: dict with selectors (body, date, image, is_vue_template)
        is_vue_template: whether page uses Vue template structure

    Returns:
        (content_text, pub_date, image_url)
    """
    content_text = ""
    pub_date = ""
    image_url = None

    if is_vue_template:
        vue_html, vue_data = extract_vue_content(c_html)
        if vue_html:
            # Handle Vue gallery and sanitize
            from .ai import decode_vue_gallery
            vue_html = decode_vue_gallery(vue_html)
            content_text = _sanitize_content_html(vue_html)
        else:
            content_text = "Vue template extraction failed"

        if vue_data:
            pub_date = extract_date_from_vue_data(vue_data)
            image_url = extract_image_from_vue_data(vue_data)
    else:
        c_soup = BeautifulSoup(c_html, 'html.parser')
        body_el = c_soup.select_one(content_rules.get('body', 'article'))
        content_text = str(body_el) if body_el else "Parsing failed"
        content_text = _sanitize_content_html(content_text) if body_el else content_text

        date_selector = normalize_selector(content_rules.get('date', content_rules.get('time', '')))
        if date_selector:
            date_el = c_soup.select_one(date_selector)
            if date_el:
                pub_date = date_el.get_text(strip=True)

        img_el = c_soup.select_one(content_rules.get('image', 'img'))
        if img_el:
            image_url = img_el.get('src', '')
            if image_url and not image_url.startswith('http'):
                image_url = urljoin(content_rules.get('url', ''), image_url)

    return content_text, pub_date, image_url


def parse_vue_date_and_image(html_content: str) -> Tuple[str, Optional[str]]:
    """
    Extract date and image from Vue template HTML.
    Used by both crawl_site_logic and test_crawl_logic.

    Returns:
        (pub_date, image_url)
    """
    from .vue_parser import extract_vue_json, parse_vue_json

    cleaned = extract_vue_json(html_content)
    if not cleaned:
        return "", None

    try:
        data = parse_vue_json(cleaned)
        if data:
            pub_date = extract_date_from_vue_data(data)
            image_url = extract_image_from_vue_data(data)
            return pub_date, image_url
    except Exception:
        pass

    return "", None