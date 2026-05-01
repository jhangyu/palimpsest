# backend/core/ai.py
import httpx
from bs4 import BeautifulSoup, Comment
import os
import json
from datetime import datetime

def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")

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

        # 建立新的 HTML 結構
        new_html = '<div class="gallery-decoded">'

        title = data.get('title', '') or ''
        if title:
            new_html += f'<div class="gallery-title">{title}</div>'

        new_html += '<div class="gallery-images">'

        for item in collection:
            src_data = item.get('src', {})
            # 使用 'l' size 作為主要顯示圖片
            img_url = src_data.get('l', src_data.get('m', src_data.get('s', '')))
            title = item.get('title', '')

            if img_url:
                new_html += f'<figure class="gallery-item">'
                new_html += f'<img src="{img_url}" alt="{title}" loading="lazy">'
                if title:
                    new_html += f'<figcaption>{title}</figcaption>'
                new_html += f'</figure>'

        new_html += '</div>'

        if data.get('from'):
            new_html += f'<div class="gallery-credit">{data["from"]}</div>'

        new_html += '</div>'

        # 用解碼後的 HTML 替換 gallery 元件
        new_soup = BeautifulSoup(new_html, 'html.parser')
        gallery.replace_with(new_soup)

    return str(soup)

MINIMAX_API_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-M2.7"

ALLOWED_CONTENT_TAGS = {'p', 'span', 'a', 'img', 'figure', 'figcaption', 'div'}
ALLOWED_IMG_ATTRS = {'src', 'alt', 'loading'}
ALLOWED_A_ATTRS = {'href'}
ALLOWED_DIV_ATTRS = {'class'}  # div 只允許 class，且僅用於 gallery-decoded 容器

def _sanitize_content_html(html_content: str) -> str:
    """
    進一步淨化 content mode 取得的 HTML，移除裝飾性元素。
    只保留：<p>, <span>, <a>, <img>, <figure>, <figcaption>, <div>（gallery-decoded 容器）
    移除所有 class 屬性和非必要標籤。
    """
    import re
    soup = BeautifulSoup(html_content, 'html.parser')

    # 收集需要移除的標籤（不在允許清單中的）
    to_remove = []
    for tag in soup.find_all(True):  # True = 所有標籤
        if tag.name not in ALLOWED_CONTENT_TAGS:
            to_remove.append(tag)

    # 移除不在允許清單中的標籤，但保留其文字內容
    for tag in to_remove:
        tag.unwrap()

    # 清理允許標籤的屬性
    for tag in soup.find_all(True):
        if not hasattr(tag, 'attrs') or not tag.attrs:
            continue

        tag_name = tag.name
        allowed = None

        if tag_name == 'img':
            allowed = ALLOWED_IMG_ATTRS
        elif tag_name == 'a':
            allowed = ALLOWED_A_ATTRS
        elif tag_name == 'div':
            # 只允許 div 的 class 屬性，且僅當值為 gallery-decoded 時
            allowed = ALLOWED_DIV_ATTRS
            # 如果 div 沒有 gallery-decoded class，移除 class 屬性
            if 'class' in tag.attrs:
                classes = tag.attrs.get('class', [])
                if 'gallery-decoded' not in classes:
                    del tag.attrs['class']
                    if not tag.attrs:
                        continue
        elif tag_name in ('p', 'span', 'figure', 'figcaption'):
            # 這些標籤不允許任何屬性，直接清空
            tag.attrs = {}
        else:
            # 其他允許的標籤，清空所有屬性
            pass

        if allowed is not None:
            tag.attrs = {
                key: value for key, value in tag.attrs.items()
                if key in allowed
            }

    # 處理 gallery-decoded div 包裝問題：移除多餘的 div 但保留內部內容
    # 如果有多層嵌套的 gallery-decoded，扁平化處理
    result = str(soup)
    # 清理空白的文字節點
    result = re.sub(r'>\s+<', '><', result)
    result = re.sub(r'\s+', ' ', result)
    return result.strip()


def clean_html_for_ai(html_content: str, mode: str = "list") -> str:
    """
    清洗 HTML，根據 mode 智能裁剪內容。
    - list mode: 找到文章列表區域，保留 container 結構 + 1-3 個 item 範例
    - content mode: 找到文章主體區域，優先使用 Vue template JSON 中的 html 欄位，
                    並進一步淨化只保留最簡潔的元素
    """
    import re

    # Content mode: 檢查是否有 Vue template JSON
    if mode == "content":
        template_html = extract_template_html(html_content)
        if template_html:
            log_with_time(f"[Clean] Found Vue template JSON with html field, length: {len(template_html)}")
            # 處理 Vue gallery 元件，轉換為標準 HTML
            template_html = decode_vue_gallery(template_html)
            # 進一步淨化，移除裝飾性 class 和非必要標籤
            template_html = _sanitize_content_html(template_html)
            log_with_time(f"[Clean] Sanitized content HTML, length: {len(template_html)}")
            return template_html if template_html else ""

        # 沒有 Vue template，使用標準流程
        soup = BeautifulSoup(html_content, 'html.parser')
        content = find_main_content(soup)
        cleaned = str(content)
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = _sanitize_content_html(cleaned)
        return cleaned.strip() if cleaned else ""
    
    # 標準清洗流程
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 移除干擾元素
    for element in soup(["script", "style", "svg", "noscript", "iframe", "footer", "header", "nav", "aside", "form", "button", "input", "select", "textarea"]):
        element.decompose()
    
    # 移除註解
    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        comment.extract()
    
    # 移除行內標籤但保留文字
    for tag in soup.find_all(["span", "i", "em", "strong", "b", "u", "s", "small", "mark"]):
        tag.unwrap()
    
    # 移除多媒體標籤
    for tag in soup.find_all(["img", "video", "audio", "canvas", "path", "circle", "rect", "line", "polygon"]):
        tag.decompose()
    
    # 清理屬性，只保留 class, id, href
    for tag in soup.recursiveChildGenerator():
        if hasattr(tag, 'attrs'):
            tag.attrs = {
                key: value for key, value in tag.attrs.items()
                if key in ['class', 'id', 'href']
            }
    
    if mode == "list":
        content = find_list_container(soup)
        content = limit_repeated_items(content, max_items=3)
    else:
        content = find_main_content(soup)
    
    cleaned = str(content)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned


def extract_template_html(html_content: str) -> str:
    """
    嘗試從 Vue template 中提取 JSON 的 html 欄位。
    使用深度追蹤來正確處理巢狀 <template> 結構。
    返回 None 如果找不到或解析失敗。
    """
    import re
    import json

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
            div_class = div.get('class')
            if div_class and ' '.join(div_class) == class_key:
                if items_removed >= max_items:
                    div.replace_with(BeautifulSoup(f"<!-- removed_item -->", 'html.parser'))
                items_removed += 1
    
    return container


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

async def analyze_structure(html_content: str, mode: str = "list", debug_writer=None) -> dict:
    log_with_time(f"========== Starting Analysis (mode={mode}) ==========")
    log_with_time(f"Original HTML length: {len(html_content)} chars")
    is_vue_template = False
    vue_json_field = None
    if mode == "content":
        _, is_vue_template, vue_json_field = detect_vue_template(html_content)
        log_with_time(f"[AI] Vue template detected: {is_vue_template}, field: {vue_json_field}")

    cleaned_html = clean_html_for_ai(html_content, mode=mode)
    log_with_time(f"Cleaned HTML length: {len(cleaned_html)} chars")

    if debug_writer is not None:
        debug_writer.save("02", "cleaned_html.html", cleaned_html)

    if mode == "list":
        prompt = f"""
        Analyze the HTML structure. Find the list of articles.
        Return raw JSON (no markdown): {{"container": "CSS selector for the list wrapper", "item": "CSS selector for article item", "title": "CSS selector for title inside item", "link": "CSS selector for 'a' tag inside item"}}
        HTML: {cleaned_html}
        """
    else:
        prompt = f"""
        Analyze the HTML structure. Find the main article content.
        Return raw JSON (no markdown): {{"title": "CSS selector", "body": "CSS selector for main content", "date": "CSS selector"}}
        HTML: {cleaned_html}
        """

    if debug_writer is not None:
        debug_writer.save("03", "ai_prompt.txt", prompt)
    log_with_time(f"Prompt length: {len(prompt)} chars")
    api_key = os.getenv("MINIMAX_API_KEY")
    log_with_time(f"API Key loaded: {'Yes' if api_key else 'NO - MISSING!'}")

    try:
        log_with_time("[AI] Calling MiniMax API...")

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": MINIMAX_MODEL,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }

        response = httpx.post(MINIMAX_API_URL, headers=headers, json=payload, timeout=180.0)
        response.raise_for_status()

        result_data = response.json()

        if debug_writer is not None:
            debug_writer.save("04", "ai_response.json", json.dumps(result_data, ensure_ascii=False, indent=2))

        log_with_time("[AI] Response received!")
        log_with_time(f"[AI] Raw response: {str(result_data)[:500] if result_data else 'EMPTY'}...")

        text = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
        import re
        text = re.sub(r'<think.*?</think>', '', text, flags=re.DOTALL).strip()
        if text.startswith("```"):
            text = text.replace("```json", "").replace("```", "")
            log_with_time(f"[AI] Cleaned markdown, text: {text[:200]}...")

        result = json.loads(text)

        if mode == "content" and is_vue_template:
            result["is_vue_template"] = True
            result["vue_json_field"] = vue_json_field
            log_with_time(f"[AI] Added Vue template flags to result")

        if debug_writer is not None:
            debug_writer.save("05", "final_rules.json", json.dumps(result, ensure_ascii=False, indent=2))

        log_with_time(f"[AI] Parsed JSON result: {result}")
        log_with_time(f"========== Analysis Complete ==========")
        return result
    except Exception as e:
        log_with_time(f"[AI] !!!!! ERROR !!!!! : {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        log_with_time(f"========== Analysis FAILED ==========")
        return {}
