# backend/core/sanitizer.py
"""
---
name: sanitizer
description: "HTML sanitization module: sanitize_content_html keeps only allowed tags, clean_html_for_ai reduces HTML for LLM analysis, decode_vue_gallery converts Vue gallery components"
type: core
target:
  layer: backend
  domain: crawl
spec_doc: null
test_file: null
functions:
  - name: _resolve_lazy_images
    line: 83
    purpose: "Shared helper: resolve lazy-load placeholder src to real URL from data-* attributes"
  - name: sanitize_image_url
    line: 93
    purpose: "Remove query string/fragment after .jpg/.png/.webp in image URLs"
  - name: sanitize_content_html
    line: 105
    purpose: "Sanitize HTML to allowed tags only (p, span, a, img, ul, ol, li, h2-h6, figure, code, strong, em) for RSS output"
  - name: decode_vue_gallery
    line: 186
    purpose: "Convert Vue gallery <div x-data> component to standard ul/li/img HTML"
  - name: clean_html_for_ai
    line: 247
    purpose: "Reduce HTML for AI analysis: list mode finds article container, content mode narrows to article body"
  - name: extract_template_html
    line: 371
    purpose: "Extract the 'html' field from Vue <template> JSON with depth-tracking"
  - name: detect_vue_template
    line: 441
    purpose: "Detect Vue template page and return (extracted_html, is_vue_template, field_name)"
  - name: find_list_container
    line: 452
    purpose: "Heuristic: find element with the most <a> tags as list container"
  - name: find_main_content
    line: 466
    purpose: "Heuristic: find element with the most text content as article body"
  - name: limit_repeated_items
    line: 480
    purpose: "Keep only first N items of repeated same-class divs (reduces AI token count)"
  - name: unwrap_single_child_divs
    line: 515
    purpose: "Remove single-child div wrappers without meaningful class/id"
  - name: flatten_deep_nesting
    line: 557
    purpose: "Flatten divs nested deeper than max_depth by promoting children"
  - name: convert_text_divs_to_p
    line: 605
    purpose: "Convert text-only divs (no child elements) to <p> tags"
run:
  command: "uvicorn backend.main:app --reload --port 8088"
  env:
    DATABASE_URL: "postgresql+asyncpg://palimpsest:pass@localhost:5432/palimpsest"
---
"""

import re
import json
from datetime import datetime
from html import escape
from typing import Optional
from bs4 import BeautifulSoup, Comment


def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ── 允許保留的標籤與屬性白名單 ──────────────────────────────────────────────────

ALLOWED_CONTENT_TAGS = {
    'p', 'span', 'a', 'img',
    'ul', 'ol', 'li',
    'h2', 'h3', 'h4', 'h5', 'h6',
    'figure', 'code', 'strong', 'em',
}
ALLOWED_IMG_ATTRS = {'src', 'alt'}
ALLOWED_A_ATTRS = {'href'}
ALLOWED_UL_ATTRS = {'class'}   # ul 只允許 class（gallery 用）
ALLOWED_LI_ATTRS = set()       # li 不允許屬性
LAZY_SRC_ATTRS = ('data-original', 'data-src', 'data-lazy-src', 'data-lazy')


def _resolve_lazy_images(soup) -> None:
    """Resolve lazy-load placeholder src to real URL from data-* attributes."""
    for img in soup.find_all('img'):
        for attr in LAZY_SRC_ATTRS:
            real_src = img.get(attr)
            if real_src and str(real_src).startswith('http'):
                img['src'] = str(real_src)
                break


def normalize_lazy_images_in_html(html: str) -> str:
    """Normalize lazy-loaded images in raw HTML by resolving data-* src attributes
    to real src so that downstream selectors (e.g. content_rules.image) see the
    resolved URL instead of a placeholder.

    Reuses the shared _resolve_lazy_images() helper — same attribute priority
    (data-original, data-src, data-lazy-src, data-lazy).
    """
    soup = BeautifulSoup(html, 'html.parser')
    _resolve_lazy_images(soup)
    return str(soup)


def sanitize_image_url(url: str) -> str:
    """
    清理圖片 URL，移除 .jpg/.png/.webp 副檔名後的 query string 和 fragment。
    其他 URL 原樣返回。
    """
    if not url:
        return url
    return re.sub(r'(?i)(\.(?:jpg|png|webp))[?#].*$', r'\1', url)


# ── 內部共用 helper ──────────────────────────────────────────────────────────────

def _decompose_noise(soup, include_header: bool = True) -> None:
    """Remove common noise elements (script, style, nav, etc.) from soup in-place."""
    tags = ["script", "style", "svg", "noscript", "iframe",
            "footer", "nav", "aside", "form", "button",
            "input", "select", "textarea"]
    if include_header:
        tags.append("header")
    for element in soup(tags):
        element.decompose()


def _remove_comments(soup) -> None:
    """Remove all HTML comments from soup in-place."""
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()


def _resolve_and_clean_lazy(soup) -> None:
    """Resolve lazy-load src attrs then strip all LAZY_SRC_ATTRS from every img."""
    _resolve_lazy_images(soup)
    for img in soup.find_all('img'):
        for attr in LAZY_SRC_ATTRS:
            if attr in img.attrs:
                del img.attrs[attr]


def _sanitize_img_urls(soup) -> None:
    """Clean img src URLs by removing query strings after common image extensions."""
    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            img['src'] = sanitize_image_url(str(src))


def _compress_whitespace(html: str) -> str:
    """Collapse tag-adjacent whitespace and multi-spaces, then strip."""
    html = re.sub(r'>\s+<', '><', html)
    html = re.sub(r'\s+', ' ', html)
    return html.strip()


def _clean_attributes(soup, keep_class_id: bool = False) -> None:
    """
    Enforce per-tag attribute whitelist across all tags in soup in-place.
    Base rules: img→{src,alt}, a→{href}, ul→class(if gallery),
                span→class(if caption), div→class(if credit), li→{}, others→{}.
    When keep_class_id=True: additionally preserve class and id on every tag.
    """
    for tag in soup.find_all(True):
        if not hasattr(tag, 'attrs') or not tag.attrs:
            continue

        tag_name = tag.name

        if tag_name == 'img':
            allowed = set(ALLOWED_IMG_ATTRS)
        elif tag_name == 'a':
            allowed = set(ALLOWED_A_ATTRS)
        elif tag_name == 'ul':
            classes = tag.attrs.get('class', [])
            allowed = {'class'} if 'gallery' in classes else set()
        elif tag_name == 'span':
            classes = tag.attrs.get('class', [])
            allowed = {'class'} if 'caption' in classes else set()
        elif tag_name == 'div':
            classes = tag.attrs.get('class', [])
            allowed = {'class'} if 'credit' in classes else set()
        elif tag_name == 'li':
            allowed = set()
        else:
            allowed = set()

        if keep_class_id:
            allowed = allowed | {'class', 'id'}

        tag.attrs = {k: v for k, v in tag.attrs.items() if k in allowed}


# ── 核心淨化函式 ─────────────────────────────────────────────────────────────────

def sanitize_content_html(html_content: str) -> str:
    """
    進一步淨化 content mode 取得的 HTML，移除裝飾性元素。
    只保留：<p>, <span>, <a>, <img>, <ul>, <li>
    移除所有 class 屬性和非必要標籤。
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    _decompose_noise(soup, include_header=True)
    _remove_comments(soup)

    # 收集需要移除的標籤（不在允許清單中的）
    to_remove = []
    for tag in soup.find_all(True):
        if tag.name == 'div':
            classes = tag.get('class', [])
            if 'credit' not in classes:
                to_remove.append(tag)
        elif tag.name not in ALLOWED_CONTENT_TAGS:
            to_remove.append(tag)

    for tag in to_remove:
        tag.unwrap()

    _resolve_and_clean_lazy(soup)
    _clean_attributes(soup, keep_class_id=False)
    _sanitize_img_urls(soup)

    return _compress_whitespace(str(soup))


def decode_vue_gallery(html_content: str) -> str:
    """
    將 Vue gallery 元件轉換為標準 HTML。
    處理 <div x-data="gallery"> 結構，其中包含 <template x-ref="src"> 存放 JSON 資料。
    返回解碼後的 HTML 內容。
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    galleries = soup.find_all('div', {'class': 'gallery'})

    if not galleries:
        return html_content

    for gallery in galleries:
        src_template = gallery.find('template', {'x-ref': 'src'})
        if not src_template:
            continue

        json_str = src_template.get_text().strip()
        if not json_str:
            continue

        try:
            # 處理 HTML 實體編碼的斜線
            json_str = json_str.replace('\\/', '/')
            data = json.loads(json_str)
        except (json.JSONDecodeError, KeyError) as e:
            log_with_time(f"[Clean] Gallery JSON parse error: {e}")
            continue

        collection = data.get('collection', [])
        if not collection:
            continue

        # 建立新的 HTML 結構：flat ul/li with image + caption span
        new_html = '<ul class="gallery">'

        for item in collection:
            src_data = item.get('src', {})
            # 使用 'l' size 作為主要顯示圖片
            img_url = src_data.get('l', src_data.get('m', src_data.get('s', '')))
            img_url = sanitize_image_url(img_url)
            title = item.get('title', '')

            if img_url:
                new_html += f'<li><img src="{escape(img_url)}" alt="{escape(title)}" loading="lazy">'
                if title:
                    new_html += f'<span class="caption">{escape(title)}</span>'
                new_html += '</li>'

        new_html += '</ul>'

        if data.get('from'):
            new_html += f'<div class="credit">{escape(data["from"])}</div>'

        # 用解碼後的 HTML 替換 gallery 元件
        new_soup = BeautifulSoup(new_html, 'html.parser')
        gallery.replace_with(new_soup)

    return str(soup)


def clean_html_for_ai(html_content: str, mode: str = "list") -> str:
    """
    清洗 HTML，根據 mode 智能裁剪內容。
    - list mode: 找到文章列表區域，保留 container 結構 + 1-3 個 item 範例
    - content mode: 找到文章主體區域，優先使用 Vue template JSON 中的 html 欄位，
                    並進一步淨化只保留最簡潔的元素
    """
    # Content mode: 檢查是否有 Vue template JSON
    if mode == "content":
        template_html = extract_template_html(html_content)
        if template_html:
            log_with_time(f"[Clean] Found Vue template JSON with html field, length: {len(template_html)}")
            # 處理 Vue gallery 元件，轉換為標準 HTML
            template_html = decode_vue_gallery(template_html)
            # 進一步淨化，移除裝飾性 class 和非必要標籤
            template_html = sanitize_content_html(template_html)
            log_with_time(f"[Clean] Sanitized content HTML, length: {len(template_html)}")
            return template_html if template_html else ""

        # 沒有 Vue template，使用 Scrapling 縮窄內容範圍
        from scrapling.parser import Selector
        page = Selector(html_content)

        # 嘗試語意化容器縮窄
        content_el = (
            page.find('article') or
            page.find('main') or
            page.find('[role="main"]') or
            page.find('.article-content') or
            page.find('.post-content') or
            page.find('#content')
        )
        narrowed_html = str(content_el) if content_el else html_content

        if content_el:
            _heading_check = BeautifulSoup(narrowed_html, 'html.parser')
            if not _heading_check.find(['h1', 'h2', 'h3']):
                _full_soup = BeautifulSoup(html_content, 'html.parser')
                _page_h1 = _full_soup.find('h1')
                if _page_h1:
                    narrowed_html = str(_page_h1) + narrowed_html

        # 用 BeautifulSoup 做噪音移除（與 list mode 一致）
        soup = BeautifulSoup(narrowed_html, 'html.parser')

        # 移除干擾元素（比 list mode 少移除 header — 文章可能有標題在 header 內）
        _decompose_noise(soup, include_header=False)
        _remove_comments(soup)

        # 解析 lazy-load 圖片、清理 data-* 屬性，並保留 class/id 供 AI 分析
        _resolve_and_clean_lazy(soup)
        _clean_attributes(soup, keep_class_id=True)
        _sanitize_img_urls(soup)

        # 不移除 img/video — AI 需要看到圖片結構來生成 selector
        # 不 unwrap 行內標籤 — 保留完整結構供 AI 分析

        content = find_main_content(soup) if not content_el else soup
        cleaned = str(content)
        cleaned = unwrap_single_child_divs(cleaned)
        cleaned = flatten_deep_nesting(cleaned)
        return _compress_whitespace(cleaned) if cleaned else ""

    # 標準清洗流程
    soup = BeautifulSoup(html_content, 'html.parser')

    # 移除干擾元素（含 header）
    _decompose_noise(soup, include_header=True)
    _remove_comments(soup)

    # 移除行內標籤但保留文字
    for tag in soup.find_all(["i", "em", "strong", "b", "u", "s", "small", "mark"]):
        tag.unwrap()

    # 移除多媒體標籤
    for tag in soup.find_all(["video", "audio", "canvas", "path", "circle", "rect", "line", "polygon"]):
        tag.decompose()

    # 解析 lazy-load 圖片、清理 data-* 屬性，並保留 class/id 供 AI 分析
    _resolve_and_clean_lazy(soup)
    _clean_attributes(soup, keep_class_id=True)
    _sanitize_img_urls(soup)

    if mode == "list":
        content = find_list_container(soup)
        content = limit_repeated_items(content, max_items=3)
    else:
        content = find_main_content(soup)

    # 應用 div 簡化函數
    cleaned = str(content)
    cleaned = unwrap_single_child_divs(cleaned)
    cleaned = flatten_deep_nesting(cleaned)
    cleaned = convert_text_divs_to_p(cleaned)

    return _compress_whitespace(cleaned)


def extract_template_html(html_content: str) -> Optional[str]:
    """
    嘗試從 Vue template 中提取 JSON 的 html 欄位。
    使用深度追蹤來正確處理巢狀 <template> 結構。
    返回 None 如果找不到或解析失敗。
    """
    # 找第一個完整的 <template...> 標籤（包含所有屬性）
    first_template_match = re.search(r'<template\b[^>]*>', html_content)
    if not first_template_match:
        return None

    # 找到 <template...> 標籤的結束位置，JSON 內容從這裡開始
    content_start = first_template_match.end()

    # 使用深度追蹤找到正確的 </template> 結尾
    # 深度：遇到 <template 增加深度，遇到 </template> 減少深度
    # 當深度回到 0 時，表示找到了最外層 template 的結尾
    depth = 1
    pos = content_start
    template_end = None

    # 用於匹配 template 相關標籤的正則
    open_tag_pattern = re.compile(r'<template\b', re.IGNORECASE)
    close_tag_pattern = re.compile(r'</template>', re.IGNORECASE)

    while pos < len(html_content) and depth > 0:
        # 找下一個 <template 或 </template>
        next_open = open_tag_pattern.search(html_content, pos)
        next_close = close_tag_pattern.search(html_content, pos)

        if next_close is None:
            # 沒有找到閉合標籤
            break

        if next_open is not None and next_open.start() < next_close.start():
            # 遇到另一個 <template，深度 +1
            depth += 1
            pos = next_open.end()
        else:
            # 遇到 </template>，深度 -1
            depth -= 1
            if depth == 0:
                template_end = next_close.start()
                break
            pos = next_close.end()

    if template_end is None:
        return None

    template_content = html_content[content_start:template_end].strip()

    # 嘗試解析為 JSON
    try:
        # 移除 Vue 綁定語法 (:id=, @click=, v-if=, etc.)
        cleaned = re.sub(r'[:@](\w+)="[^"]*"', '', template_content)
        cleaned = re.sub(r'v-\w+="[^"]*"', '', cleaned)

        data = json.loads(cleaned)

        # 檢查是否有 html 欄位
        if isinstance(data, dict) and 'html' in data:
            html_field = data['html']
            if isinstance(html_field, str) and len(html_field) > 100:
                return html_field
    except (json.JSONDecodeError, KeyError) as e:
        log_with_time(f"[Clean] Template JSON parse error: {e}")

    return None


def detect_vue_template(html_content: str) -> tuple:
    """
    檢測是否為 Vue template 頁面，並提取 JSON 中的內容。
    返回 (extracted_html, is_vue_template, vue_json_field)
    """
    extracted_html = extract_template_html(html_content)
    if extracted_html:
        return (extracted_html, True, "html")
    return (None, False, None)


def find_list_container(soup):
    """找到含最多 <a> 標籤的元素作為列表容器"""
    best_container = None
    max_links = 0

    for tag in soup.find_all(['div', 'section', 'ul', 'ol', 'article']):
        link_count = len(tag.find_all('a'))
        if link_count > max_links:
            max_links = link_count
            best_container = tag

    return best_container if best_container else soup


def find_main_content(soup):
    """找到文字內容最多的元素作為文章主體"""
    best_content = None
    max_text_length = 0

    for tag in soup.find_all(['div', 'article', 'section', 'main']):
        text_length = len(tag.get_text(strip=True))
        if text_length > max_text_length:
            max_text_length = text_length
            best_content = tag

    return best_content if best_content else soup


def limit_repeated_items(container, max_items=3):
    """
    智能限制重複項目：在容器內找到具有相同 class 且出現多次的元素，只保留前 N 個。
    這適用於文章列表中多個 item 有相同 class 的情況。
    """
    # 找出所有出現多次的 div class（在容器內）
    all_divs = container.find_all('div')

    class_counts = {}
    for div in all_divs:
        class_attr = div.get('class')
        if class_attr:
            class_key = ' '.join(class_attr)
            class_counts[class_key] = class_counts.get(class_key, 0) + 1

    # 找出出現超過 max_items 次的 class
    repeated_classes = {c: count for c, count in class_counts.items() if count > max_items}

    log_with_time(f"[Clean] Found {len(repeated_classes)} repeated classes: {repeated_classes}")

    # 對每個重複的 class，只保留前 N 個
    for class_key in repeated_classes:
        items_removed = 0
        for div in container.find_all('div'):
            if not div.attrs:
                continue
            div_class = div.get('class')
            if div_class and ' '.join(div_class) == class_key:
                if items_removed >= max_items:
                    div.decompose()
                items_removed += 1

    return container


def unwrap_single_child_divs(html_content: str) -> str:
    """
    當 div 只有單一子元素且沒有有意義的 class/id 時，移除該 div 包裝但保留內容。
    例如: <div><span>text</span></div> → <span>text</span>
    注意: 不會移除 gallery 相關結構 (ul, li, img, span.caption)。
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # 最多迭代 10 次，避免過深巢狀
    for _ in range(10):
        divs = soup.find_all('div')
        if not divs:
            break

        changed = False
        for div in divs:
            # 跳過有意义的 class 或 id 的 div
            class_attr = div.get('class', [])
            div_id = div.get('id')
            if class_attr or div_id:
                continue

            # 跳過包含 gallery 結構的 div（避免破壞 gallery）
            if div.find('ul', class_='gallery') or div.find('li'):
                continue

            # 檢查是否只有一個子元素
            children = list(div.children)
            if len(children) == 1:
                child = children[0]
                # 只有標籤才處理，跳過文字節點
                if hasattr(child, 'name') and child.name:
                    div.unwrap()
                    changed = True
                    break

        if not changed:
            break

    return str(soup)


def flatten_deep_nesting(html_content: str, max_depth: int = 3) -> str:
    """
    當 div 巢狀深度 > max_depth 時，扁平化處理。
    保持結構但減少不必要的包裝層。
    注意: 不會影響 gallery 的 ul/li 結構（深度通常不會超過 3）。
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    def get_div_depth(tag):
        """計算 div 的巢狀深度"""
        depth = 0
        parent = tag.parent
        while parent:
            if parent.name == 'div':
                depth += 1
            parent = parent.parent
        return depth

    # 迭代多次直到沒有深度 > max_depth 的 div
    for _ in range(10):
        divs = soup.find_all('div')
        if not divs:
            break

        # 找到所有深度超過限制的 div
        deep_divs = [d for d in divs if get_div_depth(d) > max_depth]

        if not deep_divs:
            break

        # 從最深的開始處理
        for div in deep_divs:
            # 檢查這個 div 是否在 gallery 結構內（ul/li）
            if div.find_parent('ul'):
                continue

            # 將 div 的內容提升到父層
            parent = div.parent
            if parent and parent.name == 'div':
                # 在父 div 內替換這個 div 為其內容
                for child in list(div.children):
                    div.insert_before(child)
                div.decompose()
                break

    return str(soup)


def convert_text_divs_to_p(html_content: str) -> str:
    """
    將只包含純文字的 div 轉換為 <p> 標籤。
    例如: <div>just text</div> → <p>just text</p>
    注意: 不會轉換包含子元素的 div。
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    for _ in range(10):
        divs = soup.find_all('div')
        if not divs:
            break

        changed = False
        for div in divs:
            # 跳過有意义的 class 或 id 的 div
            class_attr = div.get('class', [])
            div_id = div.get('id')
            if class_attr or div_id:
                continue

            # 跳過包含 gallery 結構的 div
            if div.find('ul', class_='gallery') or div.find('li'):
                continue

            # 檢查是否只有文字內容（沒有子元素）
            text = div.get_text(strip=True)
            if text and not div.find(True):  # find(True) 找任何子標籤
                new_p = soup.new_tag('p')
                new_p.string = text
                div.replace_with(new_p)
                changed = True
                break

        if not changed:
            break

    return str(soup)


# ── 向後相容別名 ──────────────────────────────────────────────────────────────────
# 供舊有程式碼（如 ai.py、crawler.py）使用底線前綴版本時不中斷
_sanitize_content_html = sanitize_content_html
