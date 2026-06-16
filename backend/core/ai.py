# backend/core/ai.py
import httpx
import os
import json
import re
from datetime import datetime


def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


MINIMAX_API_URL = "https://api.minimax.io/v1/chat/completions"
MINIMAX_MODEL = "MiniMax-M3"


async def analyze_structure(html_content: str, mode: str = "list", debug_writer=None) -> dict:
    from core.sanitizer import clean_html_for_ai, detect_vue_template

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
        prompt = f"""You are a CSS selector expert. Analyze this HTML and extract the article listing structure.

RULES:
1. container: the DIRECT parent wrapping ALL article cards. Use ALL its classes to form a compound selector so it matches exactly ONE element. Example: "div.grid.sm\\:grid-cols-2.lg\\:grid-cols-3.gap-4.md\\:gap-10" not "div.grid".
2. item: the repeating direct child element of the container representing one article card. If items are <div> or <a> tags, include ALL their classes. Use "> childSelector" relative to container.
3. title: selector for the title element INSIDE each item (e.g. "h2.text-lg.font-medium").
4. link: selector for the <a> tag INSIDE each item that links to the full article. Use href pattern like a[href*="/post/"].
5. ALWAYS use ALL CSS classes on an element to build compound selectors — never use just one class.
6. For Tailwind/utility classes containing special chars like ':', escape with backslash: sm\\:grid-cols-2.
7. The goal is PRECISION: each selector should match exactly the intended elements and nothing else.

BAD example: {{"container": "div.grid", "item": "a", "title": "h2", "link": "a"}}
GOOD example: {{"container": "div.grid.gap-4.md\\:gap-10", "item": "div.flex.items-start.flex-col.gap-1.mb-3", "title": "h2.text-lg.font-medium", "link": "a[href*='/post/view/']"}}

Return ONLY raw JSON, no markdown, no explanation:
{{"container": "...", "item": "...", "title": "...", "link": "..."}}

HTML:
{cleaned_html}"""
    else:
        prompt = f"""
        Analyze the HTML structure. Find the main article content.
        Return raw JSON (no markdown): {{"title": "CSS selector", "body": "CSS selector for main content", "date": "CSS selector"}}
        HTML: {cleaned_html}
        """

    if debug_writer is not None:
        debug_writer.save("03", "ai_prompt.txt", prompt)
    log_with_time(f"Prompt length: {len(prompt)} chars")
    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    log_with_time(f"API Key loaded: {'Yes (' + api_key[:8] + '...)' if api_key else 'NO — MINIMAX_API_KEY is empty'}")
    if not api_key:
        log_with_time("[AI] !!!!! ERROR !!!!! : MINIMAX_API_KEY environment variable is not set")
        return {}

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
            ],
            "thinking": {"type": "disabled"}
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(MINIMAX_API_URL, headers=headers, json=payload, timeout=180.0)
        response.raise_for_status()

        result_data = response.json()

        if debug_writer is not None:
            debug_writer.save("04", "ai_response.json", json.dumps(result_data, ensure_ascii=False, indent=2))

        log_with_time("[AI] Response received!")
        log_with_time(f"[AI] Raw response: {str(result_data)[:500] if result_data else 'EMPTY'}...")

        text = result_data.get("choices", [{}])[0].get("message", {}).get("content", "")
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
