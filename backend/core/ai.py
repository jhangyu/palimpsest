# backend/core/ai.py
import json
from datetime import datetime

from core.llm.service import resolve_chain, execute_with_fallback, NoProviderAvailableError
from core.llm.result_parser import (
    build_list_selector_prompt, build_content_selector_prompt,
    parse_selector_response, validate_list_rules, validate_content_rules,
)
from core.llm.models import LLMGenerationRequest


def log_with_time(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


async def analyze_with_providers(
    html_content: str,
    mode: str,
    *,
    user_id: int,
    db,
    tables,
    kek_backend,
    url: str = "",
    debug_writer=None,
) -> dict:
    import traceback
    from core.sanitizer import clean_html_for_ai, detect_vue_template

    log_with_time(f"========== Starting Analysis (providers, mode={mode}) ==========")
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
        prompt = build_list_selector_prompt(url, cleaned_html)
    else:
        prompt = build_content_selector_prompt(url, cleaned_html)

    if debug_writer is not None:
        debug_writer.save("03", "ai_prompt.txt", prompt)
    log_with_time(f"Prompt length: {len(prompt)} chars")

    chain = await resolve_chain(db, tables, kek_backend, user_id=user_id)
    if not chain:
        raise NoProviderAvailableError([])

    request = LLMGenerationRequest(
        prompt=prompt,
        model=None,
        max_tokens=4096,
        temperature=None,
        thinking=False,
        effort="low",
    )

    try:
        result = await execute_with_fallback(chain, request)
    except NoProviderAvailableError:
        raise

    if debug_writer is not None:
        debug_writer.save("04", "ai_response.txt", result.response.text)

    try:
        rules = parse_selector_response(result.response.text)
        if mode == "list":
            validate_list_rules(rules)
        else:
            validate_content_rules(rules)
    except ValueError as e:
        log_with_time(f"[AI] WARNING: parse/validate failed: {e}")
        return {}
    except Exception as e:
        log_with_time(f"[AI] !!!!! ERROR !!!!! : {type(e).__name__}: {e}")
        traceback.print_exc()
        return {}

    if mode == "content" and is_vue_template:
        rules["is_vue_template"] = True
        rules["vue_json_field"] = vue_json_field

    if debug_writer is not None:
        debug_writer.save("05", "final_rules.json", json.dumps(rules, ensure_ascii=False, indent=2))

    log_with_time(f"[AI] Analysis complete via provider: {result.label}")
    log_with_time(f"========== Analysis Complete ==========")
    return rules
