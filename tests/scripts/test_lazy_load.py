#!/usr/bin/env python3
"""
Test: verify /images/preimg.png placeholder URLs are replaced with real image URLs
in the full content parse pipeline.
"""
import sys
sys.path.insert(0, '/Users/jhangyu/project/palimpsest/backend')

pass_count = 0
fail_count = 0
skip_count = 0

# ─── Test 1: sanitize_content_html with lazy-load images ──────────────────────
print("=== Test 1: sanitize_content_html ===")
try:
    from core.sanitizer import sanitize_content_html

    html = '''
<article>
  <p>Article text</p>
  <figure>
    <img src="/images/preimg.png" data-original="https://yti.yam.com/20260625/09511958.jpg" alt="test" loading="lazy">
    <figcaption>Caption</figcaption>
  </figure>
  <figure>
    <img src="/images/preimg.png" data-src="https://cdn.example.com/photo2.jpg" alt="test2" loading="lazy">
  </figure>
  <img fetchpriority="high" src="https://yti.yam.com/20260625/09511802.jpg" alt="hero">
</article>
'''
    result = sanitize_content_html(html)
    print(result)

    assert '/images/preimg.png' not in result, "FAIL: placeholder still present"
    assert 'https://yti.yam.com/20260625/09511958.jpg' in result, "FAIL: data-original URL not resolved"
    assert 'https://cdn.example.com/photo2.jpg' in result, "FAIL: data-src URL not resolved"
    assert 'https://yti.yam.com/20260625/09511802.jpg' in result, "FAIL: hero image URL lost"
    print("PASS")
    pass_count += 1
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 2: feedparser preserves data-original ───────────────────────────────
# IMPORTANT: import core.feed_parser FIRST — it sets feedparser.SANITIZE_HTML = 0
# which is the fix under review. Without this import the flag is not set.
print("\n=== Test 2: feedparser preserves data-original ===")
_feed_content = None
try:
    import core.feed_parser  # triggers feedparser.SANITIZE_HTML = 0 side-effect
    import feedparser

    rss_content = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<item>
<title>Test</title>
<description><![CDATA[
<p>Text</p>
<img src="/images/preimg.png" data-original="https://yti.yam.com/real.jpg" alt="test">
]]></description>
</item>
</channel>
</rss>'''

    feed = feedparser.parse(rss_content)
    content = feed.entries[0].summary
    print(content)

    assert 'data-original' in content, "FAIL: feedparser stripped data-original (SANITIZE_HTML=0 not active)"
    print("PASS")
    pass_count += 1
    _feed_content = content  # save for Test 3
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 3: Full pipeline (feedparser → sanitize_content_html) ───────────────
print("\n=== Test 3: Full pipeline ===")
if _feed_content is None:
    print("SKIP: Test 2 failed or errored, cannot test pipeline")
    skip_count += 1
else:
    try:
        result = sanitize_content_html(_feed_content)
        print(result)

        assert '/images/preimg.png' not in result, "FAIL: placeholder still in final output"
        assert 'https://yti.yam.com/real.jpg' in result, "FAIL: real URL not in final output"
        print("PASS")
        pass_count += 1
    except AssertionError as e:
        print(f"FAIL: {e}")
        fail_count += 1
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback; traceback.print_exc()
        fail_count += 1

# ─── Test 4: Real travel.yam.com HTML from debug log ─────────────────────────
print("\n=== Test 4: Real travel.yam.com HTML ===")
try:
    import glob
    debug_dirs = glob.glob('/Users/jhangyu/project/palimpsest/log/debug/2026-06-26/analyze_content_travel_yam_com_*')
    if not debug_dirs:
        print("SKIP: no debug log found")
        skip_count += 1
    else:
        raw_path = debug_dirs[0] + '/01_raw_html.html'
        with open(raw_path, 'r') as f:
            raw_html = f.read()
        result = sanitize_content_html(raw_html)

        if '/images/preimg.png' in result:
            print("FAIL: placeholder /images/preimg.png still present in output")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result, 'html.parser')
            for img in soup.find_all('img'):
                print(f"  src={img.get('src')}")
            fail_count += 1
        else:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(result, 'html.parser')
            imgs = soup.find_all('img')
            print(f"Found {len(imgs)} images, all with real URLs:")
            for img in imgs:
                print(f"  src={img.get('src')}")
            print("PASS")
            pass_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 5: normalize_lazy_images_in_html — data-original ──────────────────
print("\n=== Test 5: normalize_lazy_images_in_html — data-original ===")
try:
    from core.sanitizer import normalize_lazy_images_in_html

    html = '''<article>
<img src="/images/preimg.png" data-original="https://yti.yam.com/20260625/09511958.jpg" alt="test" loading="lazy">
</article>'''
    result = normalize_lazy_images_in_html(html)

    assert '/images/preimg.png' not in (result_bs := __import__('bs4').BeautifulSoup(result, 'html.parser')).find('img').get('src', ''), \
        f"FAIL: placeholder /images/preimg.png still in src: {result_bs.find('img').get('src')}"
    assert 'https://yti.yam.com/20260625/09511958.jpg' in result_bs.find('img').get('src', ''), \
        "FAIL: data-original URL not resolved to src"
    print("PASS")
    pass_count += 1
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 6: normalize_lazy_images_in_html — data-src ────────────────────────
print("\n=== Test 6: normalize_lazy_images_in_html — data-src ===")
try:
    from core.sanitizer import normalize_lazy_images_in_html

    html = '''<article>
<img src="/images/lazyload.png" data-src="https://cdn.example.com/photo2.jpg" alt="test2" loading="lazy">
</article>'''
    result = normalize_lazy_images_in_html(html)
    from bs4 import BeautifulSoup as _BS
    img = _BS(result, 'html.parser').find('img')

    assert '/images/lazyload.png' not in img.get('src', ''), \
        f"FAIL: placeholder /images/lazyload.png still in src: {img.get('src')}"
    assert 'https://cdn.example.com/photo2.jpg' in img.get('src', ''), \
        "FAIL: data-src URL not resolved to src"
    print("PASS")
    pass_count += 1
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 7: normalize_lazy_images_in_html — data-lazy-src ───────────────────
print("\n=== Test 7: normalize_lazy_images_in_html — data-lazy-src ===")
try:
    from core.sanitizer import normalize_lazy_images_in_html

    html = '''<article>
<img src="/images/preimg.png" data-lazy-src="https://cdn.example.com/lazy-photo.jpg" alt="test3">
</article>'''
    result = normalize_lazy_images_in_html(html)
    from bs4 import BeautifulSoup as _BS
    img = _BS(result, 'html.parser').find('img')

    assert '/images/preimg.png' not in img.get('src', ''), \
        f"FAIL: placeholder still in src: {img.get('src')}"
    assert 'https://cdn.example.com/lazy-photo.jpg' in img.get('src', ''), \
        "FAIL: data-lazy-src URL not resolved to src"
    print("PASS")
    pass_count += 1
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 8: normalize_lazy_images_in_html — data-lazy ───────────────────────
print("\n=== Test 8: normalize_lazy_images_in_html — data-lazy ===")
try:
    from core.sanitizer import normalize_lazy_images_in_html

    html = '''<article>
<img src="/images/placeholder.svg" data-lazy="https://cdn.example.com/lazy-loaded.jpg" alt="test4">
</article>'''
    result = normalize_lazy_images_in_html(html)
    from bs4 import BeautifulSoup as _BS
    img = _BS(result, 'html.parser').find('img')

    assert '/images/placeholder.svg' not in img.get('src', ''), \
        f"FAIL: placeholder still in src: {img.get('src')}"
    assert 'https://cdn.example.com/lazy-loaded.jpg' in img.get('src', ''), \
        "FAIL: data-lazy URL not resolved to src"
    print("PASS")
    pass_count += 1
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Test 9: normalize_lazy_images_in_html — all four attrs, priority order ──
print("\n=== Test 9: normalize_lazy_images_in_html — all four attrs ===")
try:
    from core.sanitizer import normalize_lazy_images_in_html

    html = '''<article>
<img src="/images/preimg.png"
     data-original="https://cdn.example.com/original.jpg"
     data-src="https://cdn.example.com/src.jpg"
     data-lazy-src="https://cdn.example.com/lazy-src.jpg"
     data-lazy="https://cdn.example.com/lazy.jpg"
     alt="test">
</article>'''
    result = normalize_lazy_images_in_html(html)
    from bs4 import BeautifulSoup as _BS
    img = _BS(result, 'html.parser').find('img')

    # data-original has highest priority (first in LAZY_SRC_ATTRS)
    assert '/images/preimg.png' not in img.get('src', ''), \
        f"FAIL: placeholder still in src: {img.get('src')}"
    assert img.get('src') == 'https://cdn.example.com/original.jpg', \
        f"FAIL: expected data-original URL (highest priority), got: {img.get('src')}"
    print("PASS")
    pass_count += 1
except AssertionError as e:
    print(f"FAIL: {e}")
    fail_count += 1
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
    fail_count += 1

# ─── Summary ──────────────────────────────────────────────────────────────────
print(f"\n{'='*50}")
print(f"SUMMARY: {pass_count} PASS, {fail_count} FAIL, {skip_count} SKIP")
if fail_count > 0:
    sys.exit(1)
