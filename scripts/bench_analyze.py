"""
Benchmark: analyze list 全流程分段計時。
直接呼叫後端模組，不經 HTTP server，精確定位瓶頸。

用法: cd backend && python -m scripts.bench_analyze [URL]
  或: cd /Users/jhangyu/project/palimpsest && python scripts/bench_analyze.py [URL]
"""
import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
os.chdir(os.path.join(os.path.dirname(__file__), '..', 'backend'))

env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

TARGET_URL = sys.argv[1] if len(sys.argv) > 1 else "https://www.shoppingdesign.com.tw/post"

def ts():
    return time.time()

def fmt(label, start, end):
    d = end - start
    bar = "█" * int(d * 2)
    print(f"  {label:<40s} {d:6.2f}s  {bar}")
    return d

async def main():
    print(f"Target: {TARGET_URL}")
    print(f"{'=' * 70}")

    # ── 1. Scrapling fetch ──
    t0 = ts()
    from core.scraper import fetch_page
    t_import_scraper = ts()

    page = await fetch_page(TARGET_URL)
    t_fetch = ts()

    if page is None:
        print("FATAL: fetch_page returned None")
        return

    html = page.html_content
    print(f"\nRaw HTML: {len(html):,} chars")

    # ── 2. Sanitizer ──
    from core.sanitizer import clean_html_for_ai
    t_import_sanitizer = ts()

    cleaned = clean_html_for_ai(html, mode="list")
    t_sanitize = ts()

    print(f"Cleaned HTML: {len(cleaned):,} chars")

    # ── 3. Build prompt ──
    prompt = f"""Analyze this HTML and identify the article listing structure.

Rules for generating CSS selectors:
1. PRECISE selectors: use MULTIPLE classes to uniquely identify elements.
2. container: the DIRECT parent element wrapping ALL article items.
3. item: the repeating element for each article card.
4. title: selector for the title element INSIDE each item.
5. link: selector for the anchor tag INSIDE each item.

Return ONLY raw JSON (no markdown, no explanation):
{{"container": "CSS selector", "item": "CSS selector", "title": "CSS selector", "link": "CSS selector"}}

HTML:
{cleaned}"""

    t_prompt = ts()
    print(f"Prompt: {len(prompt):,} chars")

    # ── 4. AI API call (httpx) ──
    import httpx
    import json
    import re

    api_key = os.getenv("MINIMAX_API_KEY", "").strip()
    if not api_key:
        print("FATAL: MINIMAX_API_KEY not set")
        return

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "MiniMax-M3",
        "messages": [{"role": "user", "content": prompt}],
        "thinking": {"type": "disabled"},
    }

    t_api_start = ts()

    async with httpx.AsyncClient() as client:
        t_client_ready = ts()
        resp = await client.post(
            "https://api.minimax.io/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=180.0,
        )
    t_api_end = ts()

    resp.raise_for_status()
    data = resp.json()
    t_parse_resp = ts()

    usage = data.get("usage", {})
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    think_match = re.search(r'<think.*?</think>', text, flags=re.DOTALL)
    think_len = len(think_match.group()) if think_match else 0
    text_clean = re.sub(r'<think.*?</think>', '', text, flags=re.DOTALL).strip()
    if text_clean.startswith("```"):
        text_clean = text_clean.replace("```json", "").replace("```", "").strip()

    # ── 5. JSON parse ──
    try:
        result = json.loads(text_clean)
        t_json = ts()
    except json.JSONDecodeError as e:
        t_json = ts()
        print(f"\nJSON parse error: {e}")
        print(f"Raw text: {text_clean[:300]}")
        result = {}

    # ── Results ──
    print(f"\n{'─' * 70}")
    print("Timing breakdown:")
    print(f"{'─' * 70}")
    total = 0.0
    total += fmt("import scraper", t0, t_import_scraper)
    total += fmt("fetch_page (HTTP GET)", t_import_scraper, t_fetch)
    total += fmt("import sanitizer", t_fetch, t_import_sanitizer)
    total += fmt("clean_html_for_ai", t_import_sanitizer, t_sanitize)
    total += fmt("build prompt", t_sanitize, t_prompt)
    total += fmt("create httpx client", t_api_start, t_client_ready)
    total += fmt("MiniMax API round-trip", t_client_ready, t_api_end)
    total += fmt("parse response JSON", t_api_end, t_parse_resp)
    total += fmt("json.loads result", t_parse_resp, t_json)
    print(f"{'─' * 70}")
    print(f"  {'TOTAL':<40s} {t_json - t0:6.2f}s")

    print(f"\nMiniMax usage:")
    print(f"  input tokens:  {usage.get('prompt_tokens', '?')}")
    print(f"  output tokens: {usage.get('completion_tokens', '?')}")
    print(f"  think tokens:  ~{think_len} chars")

    if result:
        print(f"\nResult: {json.dumps(result, ensure_ascii=False)}")

asyncio.run(main())
