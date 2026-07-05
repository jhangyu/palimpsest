# Lazy Image Architecture Mapper — Report

## 1. Component Boundaries & Call Chain

### Layer Diagram

```
  [URL]
    │
    ▼
  ┌──────────────────────────────────────┐
  │ scraper.py: fetch_page()            │
  │   Scrapling Fetcher or Playwright    │
  │   → Selector page object             │
  └──────────────────────────────────────┘
    │
    ▼
  ┌──────────────────────────────────────┐
  │ parser.py: parse_listing()          │
  │   page.css() / page.find()          │
  │   → [{url, title}, ...]             │
  └──────────────────────────────────────┘
    │
    ▼  (foreach article)
  ┌──────────────────────────────────────┐
  │ scraper.py: fetch_page(url)         │
  │   → Selector page object             │
  └──────────────────────────────────────┘
    │
    ▼
  ┌──────────────────────────────────────┐
  │ parser.py: parse_article()          │
  │   page.find(body_selector)           │
  │   sanitize_content_html(str(body))   │
  │   → (content, date, image_url, author)
  └──────────────────────────────────────┘
    │
    ▼
  ┌──────────────────────────────────────┐
  │ sanitizer.py: sanitize_content_html │
  │   _resolve_and_clean_lazy(soup)      │
  │   _clean_attributes(soup)            │
  │   → clean HTML string                │
  └──────────────────────────────────────┘
    │
    ▼
  [INSERT INTO articles]
```
