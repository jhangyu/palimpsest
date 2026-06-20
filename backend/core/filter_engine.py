"""Article filter engine — recursive tri-state evaluation.

Public API:
    apply_filter(articles, filter_config, available_fields) -> (passed, filtered_out)

Data structures expected in filter_config:
    {
        "mode": "blacklist" | "whitelist",
        "match_whole_word": bool,
        "root": FilterGroup
    }

    FilterGroup = {
        "id": str,
        "type": "group",
        "operator": "and" | "or",
        "children": list[FilterRule | FilterGroup]
    }

    FilterRule = {
        "id": str,
        "type": "rule",
        "field": "title" | "content" | "title_content",
        "match": "contains" | "not_contains" | "equals" | "starts_with" | "ends_with" | "regex",
        "value": str
    }
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

# ---------------------------------------------------------------------------
# ReDoS protection: single shared executor for regex matching
# ---------------------------------------------------------------------------
_regex_executor = ThreadPoolExecutor(max_workers=1)


def _safe_regex_match(pattern: re.Pattern, text: str, timeout_s: float = 0.1) -> bool:
    """Run regex match in a separate thread with timeout to prevent ReDoS."""
    future = _regex_executor.submit(pattern.search, text)
    try:
        return bool(future.result(timeout=timeout_s))
    except (FuturesTimeout, Exception):
        future.cancel()
        return False


# ---------------------------------------------------------------------------
# Regex pre-compilation cache
# ---------------------------------------------------------------------------

def _build_regex_cache(root: dict) -> dict[str, re.Pattern | None]:
    """Walk tree once, compile all regex patterns upfront."""
    cache: dict[str, re.Pattern | None] = {}
    _walk_for_regex(root, cache)
    return cache


def _walk_for_regex(node: dict, cache: dict) -> None:
    """Recursively walk the filter tree and compile regex patterns."""
    if node.get('type') == 'rule':
        if node.get('match') == 'regex':
            value = node.get('value', '')
            if value and value not in cache:
                try:
                    cache[value] = re.compile(value, re.I)
                except re.error:
                    cache[value] = None  # invalid regex → always returns False
    elif node.get('type') == 'group':
        for child in node.get('children', []):
            _walk_for_regex(child, cache)


# ---------------------------------------------------------------------------
# Match operators
# ---------------------------------------------------------------------------

def _match_text(
    field_text: str,
    match_op: str,
    value: str,
    whole_word: bool,
    regex_cache: dict,
) -> bool:
    """Apply a single match operator against field_text."""
    if match_op == 'regex':
        pattern = regex_cache.get(value)
        if pattern is None:
            return False  # invalid/missing compiled pattern
        return _safe_regex_match(pattern, field_text)

    # Case-insensitive comparison for non-regex operators
    compare_text = field_text.lower()
    compare_val = value.lower()

    if match_op == 'contains':
        if whole_word:
            try:
                wp = re.compile(r'\b' + re.escape(value) + r'\b', re.I)
                return bool(wp.search(field_text))
            except re.error:
                return False
        return compare_val in compare_text

    if match_op == 'not_contains':
        if whole_word:
            try:
                wp = re.compile(r'\b' + re.escape(value) + r'\b', re.I)
                return not bool(wp.search(field_text))
            except re.error:
                return True  # invalid pattern → treat as not matching
        return compare_val not in compare_text

    if match_op == 'equals':
        return compare_text == compare_val

    if match_op == 'starts_with':
        return compare_text.startswith(compare_val)

    if match_op == 'ends_with':
        return compare_text.endswith(compare_val)

    # Unknown operator → no match
    return False


# ---------------------------------------------------------------------------
# Tri-state recursive evaluation
# ---------------------------------------------------------------------------

def evaluate_rule(
    rule: dict,
    article: dict,
    available_fields: list[str],
    whole_word: bool,
    regex_cache: dict,
) -> bool | None:
    """Evaluate a single rule against an article.

    Returns:
        True  — rule matches
        False — rule does not match
        None  — required field(s) not available (defer to Stage 2)
    """
    field = rule.get('field', 'title')
    match_op = rule.get('match', 'contains')
    value = rule.get('value', '')

    # Determine available text; return None if required field is missing
    if field == 'title':
        if 'title' not in available_fields:
            return None
        field_text = article.get('title', '') or ''
    elif field == 'content':
        if 'content' not in available_fields:
            return None
        field_text = article.get('content', '') or ''
    elif field == 'title_content':
        # Requires BOTH fields to give a definitive result (C-1 whitelist safety)
        if 'title' not in available_fields or 'content' not in available_fields:
            return None
        title = article.get('title', '') or ''
        content = article.get('content', '') or ''
        field_text = title + ' ' + content
    else:
        # Unknown field → defer
        return None

    return _match_text(field_text, match_op, value, whole_word, regex_cache)


def evaluate_group(
    group: dict,
    article: dict,
    available_fields: list[str],
    whole_word: bool,
    regex_cache: dict,
) -> bool | None:
    """Evaluate a group (AND/OR) recursively.

    Tri-state precedence:
    - AND: False dominates > None defers > True passes
    - OR:  True dominates > None defers > False passes

    Returns bool | None
    """
    operator = group.get('operator', 'and')
    children = group.get('children', [])

    if not children:
        # Empty group semantics: AND() = True, OR() = False
        return True if operator == 'and' else False

    results: list[bool | None] = []
    for child in children:
        child_type = child.get('type')
        if child_type == 'rule':
            r = evaluate_rule(child, article, available_fields, whole_word, regex_cache)
        elif child_type == 'group':
            r = evaluate_group(child, article, available_fields, whole_word, regex_cache)
        else:
            r = None  # unknown node type → defer
        results.append(r)

    if operator == 'and':
        # AND: False dominates > None defers > True passes
        if False in results:
            return False
        if None in results:
            return None
        return True
    else:  # 'or'
        # OR: True dominates > None defers > False passes
        if True in results:
            return True
        if None in results:
            return None
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_filter(
    articles: list[dict],
    filter_config: dict | None,
    available_fields: list[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Apply filter config to a list of articles.

    Parameters
    ----------
    articles : list[dict]
        Articles to filter; each dict must have at least 'title' and optionally 'content'.
    filter_config : dict | None
        FilterConfig object (mode, match_whole_word, root).  None = no filtering.
    available_fields : list[str] | None
        Fields available for evaluation.
        - Stage 1 (title-only, before content fetch): ['title']
        - Stage 2 (full data, before DB write):       ['title', 'content']
        Defaults to ['title', 'content'] when None.

    Returns
    -------
    (passed, filtered_out) : tuple[list[dict], list[dict]]
        Articles that passed the filter and those that were filtered out.

    Notes
    -----
    Tri-state evaluation: rules requiring unavailable fields return None (defer).
    Root None → article is kept and deferred to Stage 2.
    This prevents whitelist rules that need 'content' from falsely dropping
    articles at Stage 1 before content is fetched (C-1 fix).
    """
    if available_fields is None:
        available_fields = ['title', 'content']

    if not filter_config:
        return list(articles), []

    mode = filter_config.get('mode', 'blacklist')
    whole_word = bool(filter_config.get('match_whole_word', False))
    root = filter_config.get('root')

    if not root:
        return list(articles), []

    # Pre-compile all regex patterns once for the entire article batch
    regex_cache = _build_regex_cache(root)

    passed: list[dict] = []
    filtered_out: list[dict] = []

    for article in articles:
        result = evaluate_group(root, article, available_fields, whole_word, regex_cache)

        if result is None:
            # Defer: not enough information → keep article, Stage 2 will decide
            passed.append(article)
        elif mode == 'blacklist':
            # Blacklist: result=True means rule matched → exclude article
            if result:
                filtered_out.append(article)
            else:
                passed.append(article)
        else:  # whitelist
            # Whitelist: result=True means rule matched → keep article
            if result:
                passed.append(article)
            else:
                filtered_out.append(article)

    return passed, filtered_out
