#!/usr/bin/env python3
"""E2E test: verify lazy-load image URLs are resolved in all sanitizer paths."""
import sys
import os
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import httpx
from bs4 import BeautifulSoup
from core.sanitizer import sanitize_content_html, clean_html_for_ai

TARGET_URL = "https://travel.yam.com/article/140209"


def check_no_preimg(html, test_name):
    """Check that no img has src containing preimg placeholder. Return (pass, details)."""
    soup = BeautifulSoup(html, 'html.parser')
    imgs = soup.find_all('img')
    failures = []
    for img in imgs:
        src = img.get('src', '')
        if 'preimg' in str(src):
            failures.append(f"  FOUND placeholder: src={src}")
    if failures:
        print(f"FAIL: {test_name}")
        for f in failures:
            print(f)
        return False
    else:
        print(f"PASS: {test_name}")
        for img in imgs:
            print(f"  src={img.get('src', '')}")
        return True


# Fetch raw HTML — try live first, fall back to debug log
print(f"Fetching {TARGET_URL} ...")
try:
    resp = httpx.get(TARGET_URL, timeout=15, follow_redirects=True,
                     headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    raw_html = resp.text
    print(f"  OK: {len(raw_html)} bytes from live URL")
except Exception as e:
    print(f"  Live fetch failed ({e}), falling back to debug log")
    debug_dirs = sorted(glob.glob(
        '/Users/jhangyu/project/palimpsest/log/debug/2026-06-26/analyze_content_travel_yam_com_*'
    ))
    raw_html_path = debug_dirs[-1] + '/01_raw_html.html' if debug_dirs else None
    if not raw_html_path or not os.path.exists(raw_html_path):
        print("SKIP: no debug log found either")
        sys.exit(1)
    with open(raw_html_path, 'r') as f:
        raw_html = f.read()
    print(f"  OK: {len(raw_html)} bytes from debug log")

results = []

# Test 1: sanitize_content_html resolves lazy-load
print()
print("=" * 60)
print("Test 1: sanitize_content_html with travel.yam.com body")
print("=" * 60)
from scrapling.parser import Selector
page = Selector(raw_html)
body_el = page.find('article.article_content') or page.find('article') or page.find('main') or page.find('body')
body_html = str(body_el) if body_el else raw_html
result1 = sanitize_content_html(body_html)
results.append(check_no_preimg(result1, "sanitize_content_html"))

# Test 2: clean_html_for_ai content mode resolves lazy-load
print()
print("=" * 60)
print("Test 2: clean_html_for_ai(mode='content') with raw HTML")
print("=" * 60)
result2 = clean_html_for_ai(raw_html, mode="content")
results.append(check_no_preimg(result2, "clean_html_for_ai content mode"))

# Test 3: clean_html_for_ai list mode
print()
print("=" * 60)
print("Test 3: clean_html_for_ai(mode='list') with raw HTML")
print("=" * 60)
result3 = clean_html_for_ai(raw_html, mode="list")
results.append(check_no_preimg(result3, "clean_html_for_ai list mode"))

# Summary
print()
print("=" * 60)
passed = sum(results)
total = len(results)
print(f"SUMMARY: {passed}/{total} PASS, {total - passed}/{total} FAIL")
if passed == total:
    print("ALL TESTS PASSED")
else:
    print("SOME TESTS FAILED")
    sys.exit(1)
