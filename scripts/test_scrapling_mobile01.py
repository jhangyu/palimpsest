#!/usr/bin/env python3
"""
Test script: scrape mobile01.com news listing with Scrapling.
Target: https://www.mobile01.com/newslist.php?type=0&c=20&date=2026
"""

import json
import sys
from dataclasses import dataclass, asdict
from typing import Optional


TARGET_URL = "https://www.mobile01.com/newslist.php?type=0&c=20&date=2026"


@dataclass
class Article:
    title: str
    url: str
    date: Optional[str] = None
    category: Optional[str] = None
    author: Optional[str] = None
    thumbnail: Optional[str] = None
    summary: Optional[str] = None


def try_fetcher(url: str) -> tuple[object | None, str]:
    """Try basic Fetcher (httpx-based, no browser)."""
    try:
        from scrapling import Fetcher
        print("[Fetcher] Sending request...")
        page = Fetcher(auto_match=False).get(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )
        print(f"[Fetcher] Status: {page.status}")
        return page, "Fetcher"
    except Exception as e:
        print(f"[Fetcher] Failed: {e}")
        return None, "Fetcher"


def parse_articles(page) -> list[Article]:
    """Parse article data from the page using multiple selector strategies."""
    articles: list[Article] = []

    # Strategy 1: common list-item selectors on mobile01
    # mobile01 news listing typically uses <ul> with <li> items
    selectors_to_try = [
        # mobile01 specific
        ".c-articleCard",
        "[class*='articleCard']",
        # direct news list items
        "li.news-item",
        "li[class*='news']",
        ".news-list li",
        "ul.list li",
        # generic article wrappers
        "article",
        ".article-item",
        ".post-item",
        # table rows (older sites)
        "table tr",
    ]

    raw_html_snippet = str(page.html_content)[:500] if hasattr(page, 'html_content') else ""
    print(f"\n[Parser] Page content length: {len(str(page.content)) if hasattr(page, 'content') else 'N/A'}")

    # First dump the raw page title to confirm we got the right page
    titles = page.css("title")
    if titles:
        print(f"[Parser] Page <title>: {titles[0].text}")

    found_with = None
    candidates = []

    for sel in selectors_to_try:
        try:
            items = page.css(sel)
            if items and len(items) > 2:
                print(f"[Parser] Found {len(items)} items with selector: {sel}")
                candidates = items
                found_with = sel
                break
        except Exception:
            continue

    # If no specific selector worked, fall back to all <a> tags with href containing news paths
    if not candidates:
        print("[Parser] No list selector matched — falling back to link extraction")
        all_links = page.css("a[href]")
        print(f"[Parser] Total <a> tags: {len(all_links)}")

        for link in all_links:
            href = link.attrib.get("href", "")
            text = (link.text or "").strip()
            if not text or len(text) < 5:
                continue
            if any(k in href for k in ["topicdetail", "newsdetail", "articledetail", "news"]):
                full_url = href if href.startswith("http") else f"https://www.mobile01.com/{href}"
                articles.append(Article(title=text, url=full_url))

        return articles

    # Parse structured data from .c-articleCard elements
    # Each card is an <a> element itself with href, containing img, desc, date, author
    for card in candidates:
        try:
            # The card itself is the <a> tag
            href = card.attrib.get("href", "")
            if not href:
                # Maybe card is a container; look for inner <a>
                inner = card.css("a[href]")
                if inner:
                    href = inner[0].attrib.get("href", "")
                    card = inner[0]

            if not href:
                continue

            url = href if href.startswith("http") else f"https://www.mobile01.com/{href}"

            # Title: from .l-articleCardDesc text or img alt
            title = ""
            desc_el = card.css(".l-articleCardDesc")
            if desc_el:
                title = (desc_el[0].text or "").strip()
            if not title:
                img_el = card.css("img[alt]")
                if img_el:
                    title = (img_el[0].attrib.get("alt") or "").strip()
            if not title:
                continue

            # Date: .o-fNotes first occurrence (left side = date)
            date = None
            notes = card.css(".o-fNotes")
            if notes:
                date = (notes[0].text or "").strip()

            # Author: .o-fNotes second occurrence (right side = author)
            author = None
            if len(notes) >= 2:
                author = (notes[1].text or "").strip()

            # Thumbnail
            img_el = card.css("img[src]")
            thumbnail = img_el[0].attrib.get("src") if img_el else None

            articles.append(Article(
                title=title,
                url=url,
                date=date,
                author=author,
                thumbnail=thumbnail,
            ))
        except Exception as e:
            print(f"[Parser] Item parse error: {e}")
            continue

    return articles


def print_results(articles: list[Article], fetcher_name: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"Results via {fetcher_name}: {len(articles)} articles found")
    print("=" * 60)

    if not articles:
        print("No articles extracted.")
        return

    for i, art in enumerate(articles[:20], 1):  # show first 20
        print(f"\n[{i}] {art.title}")
        print(f"     URL: {art.url}")
        if art.date:
            print(f"     Date: {art.date}")
        if art.category:
            print(f"     Category: {art.category}")
        if art.author:
            print(f"     Author: {art.author}")
        if art.thumbnail:
            print(f"     Thumb: {art.thumbnail[:80]}...")
        if art.summary:
            print(f"     Summary: {art.summary[:100]}...")

    if len(articles) > 20:
        print(f"\n... and {len(articles) - 20} more articles.")

    # Dump JSON for further use
    output_path = "/Users/jhangyu/project/palimpsest/scripts/mobile01_articles.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([asdict(a) for a in articles], f, ensure_ascii=False, indent=2)
    print(f"\nFull results saved to: {output_path}")


def diagnose_page(page) -> None:
    """Print page structure hints when extraction fails."""
    print("\n[Diagnose] Checking page structure...")
    for sel, label in [
        ("ul", "<ul> elements"),
        ("li", "<li> elements"),
        ("article", "<article> elements"),
        ("div[class]", "<div> with class"),
        ("a[href]", "<a> links"),
    ]:
        try:
            els = page.css(sel)
            print(f"  {label}: {len(els)}")
        except Exception:
            pass

    # Print first 2000 chars of body text
    try:
        body = page.css("body")
        if body:
            text = body[0].text or ""
            print(f"\n[Diagnose] Body text snippet (first 500 chars):\n{text[:500]}")
    except Exception:
        pass

    # Show a sample of class names present on the page
    try:
        all_els = page.css("[class]")
        classes = set()
        for el in all_els[:100]:
            c = el.attrib.get("class", "")
            classes.update(c.split())
        print(f"\n[Diagnose] Sample CSS classes: {sorted(classes)[:40]}")
    except Exception:
        pass


def main() -> None:
    print(f"Target URL: {TARGET_URL}\n")

    # Step 1: Try basic Fetcher
    page, fetcher_name = try_fetcher(TARGET_URL)

    if page is None:
        print("Fetcher failed completely. Aborting (browser fetchers require playwright install).")
        sys.exit(1)

    # Check if we got real content (not a CAPTCHA/block page)
    content_str = ""
    try:
        content_str = str(page.content)
    except Exception:
        try:
            content_str = str(page.html_content)
        except Exception:
            pass

    is_blocked = (
        len(content_str) < 1000
        or "captcha" in content_str.lower()
        or "403" in content_str[:200]
        or "access denied" in content_str.lower()
    )

    if is_blocked:
        print(f"[Warning] Response looks like a block/CAPTCHA (length={len(content_str)}).")
        print("Content preview:", content_str[:300])
        print("\nNote: For this site you may need StealthyFetcher (Playwright + stealth).")
        print("Install with: pip install scrapling[playwright] && scrapling install")
        diagnose_page(page)
        sys.exit(1)

    articles = parse_articles(page)

    if not articles:
        print("\n[Warning] No articles extracted. Diagnosing page structure...")
        diagnose_page(page)
    else:
        print_results(articles, fetcher_name)


if __name__ == "__main__":
    main()
