"""
Test script to verify _sanitize_content_html works correctly.
Tests the content extraction and sanitization on a real article.
"""
from playwright.sync_api import sync_playwright
import json

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to Create Feed page
        print("Opening Create Feed page...")
        page.goto('http://localhost:5174/add', wait_until='networkidle', timeout=30000)
        page.wait_for_timeout(2000)  # Extra wait for React to mount

        # Enter the URL
        print("Entering URL...")
        url_input = page.locator('input[type="text"], input[placeholder*="URL"]').first
        url_input.fill("https://www.shoppingdesign.com.tw/post/view/13327")

        # Click Analyze Content button
        print("Clicking Analyze Content...")
        # Look for button that says "Content" or "分析 Content"
        content_btn = page.locator('button:has-text("Content"), button:has-text("內容")').first
        content_btn.click()

        # Wait for analysis to complete
        print("Waiting for content analysis...")
        page.wait_for_timeout(30000)  # AI takes time

        # Get the preview content
        preview_html = page.locator('[class*="preview"], [class*="content"]').last.inner_html()

        print("\n=== RAW PREVIEW HTML (first 3000 chars) ===")
        print(preview_html[:3000] if len(preview_html) > 3000 else preview_html)
        print(f"\n... Total length: {len(preview_html)} chars")

        # Check tags
        import re
        all_tags = re.findall(r'<(\w+)', preview_html)
        unique_tags = sorted(set(all_tags))
        print(f"\n=== Unique tags found ===")
        print(unique_tags)

        # Check for class attributes
        class_attrs = re.findall(r'class="[^"]*"', preview_html)
        print(f"\n=== Class attributes found ({len(class_attrs)}) ===")
        for c in class_attrs[:10]:
            print(f"  {c}")

        browser.close()
        print("\n=== Test Complete ===")

if __name__ == "__main__":
    main()