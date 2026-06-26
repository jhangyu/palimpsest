# backend/core/parser.py
"""
---
name: parser
description: "Pure parsing layer: Scrapling-based listing and article parsers; normalize_selector, parse_listing, parse_article with Vue template support"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: null
functions:
  - name: normalize_selector
    line: 15
    purpose: "Standardize CSS selector: fix smart quotes to ASCII quotes"
  - name: extract_article_info
    line: 26
    purpose: "Extract URL and title from a single list item element using rules"
  - name: parse_listing
    line: 66
    purpose: "Parse article list from Scrapling page object or raw HTML string using list_rules"
  - name: parse_article
    line: 132
    purpose: "Parse article content/date/image/author from Scrapling page or raw HTML using content_rules"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""
from urllib.parse import urljoin
from .vue_parser import (
    extract_vue_content,
    extract_date_from_vue_data,
    extract_image_from_vue_data,
    extract_author_from_vue_data,
)
from .sanitizer import sanitize_content_html

__all__ = ['normalize_selector', 'extract_article_info', 'parse_listing', 'parse_article']


def normalize_selector(selector: str) -> str:
    """Standardize CSS selector, fix smart quotes"""
    if not selector:
        return selector
    selector = selector.replace('‘', "'")
    selector = selector.replace('’', "'")
    selector = selector.replace('“', '"')
    selector = selector.replace('”', '"')
    return selector


def extract_article_info(item, list_rules: dict, base_url: str) -> dict[str, str] | None:
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
    except (AttributeError, ValueError):
        return None


def parse_listing(page, list_rules: dict, base_url: str) -> list[dict]:
    """從 Scrapling page 物件解析文章列表。

    Args:
        page: Scrapling page/Adaptor 物件（支援 .css() 查詢）或 raw HTML string
        list_rules: dict with 'container', 'item', 'link', 'title' selectors
        base_url: 用於解析相對 URL

    Returns:
        list of dict with 'url' and 'title' keys
    """
    if isinstance(page, str):
        from scrapling.parser import Selector
        page = Selector(page)

    container_selector = normalize_selector(list_rules.get('container', ''))
    item_selector = normalize_selector(list_rules.get('item', '')) or 'li'
    link_selector = normalize_selector(list_rules.get('link', ''))
    title_selector = normalize_selector(list_rules.get('title', ''))

    # 取得搜尋範圍：嘗試所有匹配的 container，選第一個含有 item 的
    root = page
    if container_selector:
        candidates = page.css(container_selector)
        for candidate in candidates:
            found = candidate.css(item_selector)
            if found:
                root = candidate
                break

    items = root.css(item_selector)

    results = []
    for item in items:
        try:
            # 支援 item 本身就是 link（如 mobile01 的 <a class="c-articleCard">）
            if link_selector:
                link_el = item.find(link_selector)
            else:
                link_el = None

            if not link_el:
                link_el = item  # fallback: item 本身就是 link

            article_url = link_el.attrib.get('href', '')
            if not article_url:
                continue

            if not article_url.startswith('http'):
                article_url = urljoin(base_url, article_url)

            title = ""
            if title_selector:
                title_el = item.find(title_selector)
                if title_el:
                    # .text returns only direct text; fall back to get_all_text()
                    # for elements like <h2><a>Title</a></h2> where .text is empty
                    title = title_el.text.strip() or title_el.get_all_text().strip()

            if not title:
                title = (link_el.text or "").strip() or link_el.get_all_text().strip() or "No Title"

            results.append({"url": article_url, "title": title})
        except (AttributeError, ValueError):
            continue

    return results


def parse_article(page, content_rules: dict, article_url: str) -> tuple[str, str, str | None, str | None]:
    """從 Scrapling page 物件解析文章內容。

    Args:
        page: Scrapling page/Adaptor 物件或 raw HTML string
        content_rules: dict with 'body', 'date', 'image', 'is_vue_template' selectors
        article_url: 文章 URL，用於解析相對圖片 URL

    Returns:
        (content_text, pub_date, image_url, author)
    """
    if isinstance(page, str):
        from scrapling.parser import Selector
        page = Selector(page)

    is_vue_template = content_rules.get('is_vue_template', False)
    content_text = ""
    pub_date = ""
    image_url = None
    author = None

    if is_vue_template:
        # Vue template：從 raw HTML 取出 Vue 資料
        raw_html = page.html_content if hasattr(page, 'html_content') else str(page)
        vue_html, vue_data = extract_vue_content(raw_html)
        if vue_html:
            from .sanitizer import decode_vue_gallery
            vue_html = decode_vue_gallery(vue_html)
            content_text = sanitize_content_html(vue_html)
        else:
            content_text = "Vue template extraction failed"

        if vue_data:
            pub_date = extract_date_from_vue_data(vue_data)
            image_url = extract_image_from_vue_data(vue_data)
            author = extract_author_from_vue_data(vue_data)
    else:
        body_selector = normalize_selector(content_rules.get('body', '')) or 'article'
        body_el = page.find(body_selector)
        if body_el:
            content_text = sanitize_content_html(str(body_el))
        else:
            content_text = "Parsing failed"

        date_selector = normalize_selector(content_rules.get('date', content_rules.get('time', '')))
        if date_selector:
            date_el = page.find(date_selector)
            if date_el:
                pub_date = date_el.text

        img_selector = normalize_selector(content_rules.get('image', '')) or 'img'
        img_el = page.find(img_selector)
        if img_el:
            raw_src = img_el.attrib.get('src', '')
            image_url = (
                (raw_src if raw_src.startswith('http') else '')
                or img_el.attrib.get('data-original', '')
                or img_el.attrib.get('data-src', '')
                or img_el.attrib.get('data-lazy-src', '')
                or img_el.attrib.get('data-lazy', '')
                or raw_src
            )
            if image_url and not image_url.startswith('http'):
                image_url = urljoin(article_url, image_url)

        author_selector = normalize_selector(content_rules.get('author', ''))
        if author_selector:
            author_el = page.find(author_selector)
            if author_el:
                author = (author_el.text or "").strip()

    return content_text, pub_date, image_url, author
