# backend/core/llm/result_parser.py
"""
Provider-agnostic prompt building and response parsing utilities.

Extracted from backend/core/ai.py so that any LLM provider can reuse
the same prompt templates and the same parsing / validation logic.
"""
import json
import re


def build_list_selector_prompt(url: str, html_snippet: str) -> str:
    """Build the prompt for list/index page CSS selector analysis.

    Args:
        url: The source URL (included as context for the LLM).
        html_snippet: The cleaned HTML to analyse.

    Returns:
        Prompt string ready to send to an LLM.
    """
    return f"""You are a CSS selector expert. Analyze this HTML and extract the article listing structure.

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
{html_snippet}"""


def build_content_selector_prompt(url: str, html_snippet: str) -> str:
    """Build the prompt for content/article page CSS selector analysis.

    Requests selectors for 5 fields: title, body, date, image, author.

    Args:
        url: The source URL (included as context for the LLM).
        html_snippet: The cleaned HTML to analyse.

    Returns:
        Prompt string ready to send to an LLM.
    """
    return f"""You are a CSS selector expert. Analyze this HTML and extract the article content structure.

RULES:
1. title: selector for the article headline/heading element (e.g. "h1.article-title" or "h1.post-heading").
2. body: selector for the MAIN article content area containing the article text and paragraphs (e.g. "div.article-body" or "article.content").
3. date: selector for the publication date element (e.g. "span.publish-date" or "time[datetime]").
4. image: selector for the hero/cover image of the article (e.g. "img.hero-image" or "figure > img").
5. author: selector for the article author name or byline element (e.g. "span.author-name" or "div.author-info").
6. ALWAYS use ALL CSS classes on an element to build compound selectors — never use just one class.
7. For Tailwind/utility classes containing special chars like ':', escape with backslash: md\\:w-full.
8. The goal is PRECISION: each selector should match exactly the intended element and nothing else.

If an element cannot be found reliably, use your best judgment or indicate with an empty string.

Return ONLY raw JSON, no markdown, no explanation:
{{"title": "...", "body": "...", "date": "...", "image": "...", "author": "..."}}

HTML:
{html_snippet}"""


def parse_selector_response(raw_text: str) -> dict:
    """Parse an LLM response into a selector dict.

    Steps:
    1. Remove ``<think>...</think>`` blocks (non-greedy, DOTALL).
    2. Remove markdown code fences (triple-backtick json ... triple-backtick).
    3. Locate the first ``{`` to the last ``}`` to isolate the JSON object.
    4. Parse JSON.
    5. Return parsed dict.

    Raises:
        ValueError: When no valid JSON object can be extracted or parsed.
    """
    # Step 1 – strip <think> blocks
    text = re.sub(r'<think.*?</think>', '', raw_text, flags=re.DOTALL).strip()

    # Step 2 – strip markdown code fences
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    # Step 3 – locate JSON object boundaries
    start = text.find('{')
    end = text.rfind('}')
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"No JSON object found in LLM response: {raw_text[:200]!r}")

    json_str = text[start:end + 1]

    # Step 4 – parse
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse JSON from LLM response: {exc}") from exc


def validate_list_rules(rules: dict) -> dict:
    """Validate that list rules contain all required string fields.

    Required fields: container, item, title, link.

    Args:
        rules: Dict returned by the LLM (after parsing).

    Returns:
        The same ``rules`` dict when valid.

    Raises:
        ValueError: If any required field is missing or not a string.
    """
    required = ("container", "item", "title", "link")
    for field in required:
        if field not in rules:
            raise ValueError(f"List rules missing required field: '{field}'")
        if not isinstance(rules[field], str):
            raise ValueError(
                f"List rules field '{field}' must be a string, got {type(rules[field]).__name__}"
            )
        if not rules[field].strip():
            raise ValueError(f"List rules field '{field}' must not be empty")
    return rules


def validate_content_rules(rules: dict) -> dict:
    """Validate that content rules contain all required string fields.

    Required fields (must not be empty): title, body.
    Optional fields (empty string is OK): date, image, author.

    Args:
        rules: Dict returned by the LLM (after parsing).

    Returns:
        The same ``rules`` dict when valid.

    Raises:
        ValueError: If any required field is missing or not a string.
    """
    required_fields = ("title", "body")
    optional_fields = ("date", "image", "author")
    all_fields = required_fields + optional_fields

    # Check all fields are present and are strings
    for field in all_fields:
        if field not in rules:
            raise ValueError(f"Content rules missing required field: '{field}'")
        if not isinstance(rules[field], str):
            raise ValueError(
                f"Content rules field '{field}' must be a string, got {type(rules[field]).__name__}"
            )

    # Check that required fields are not empty
    for field in required_fields:
        if not rules[field].strip():
            raise ValueError(f"Content rules field '{field}' must not be empty")

    return rules
