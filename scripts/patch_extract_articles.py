"""Fix extract_initial_articles in url_capture.py to parse Playwright-rendered DOM."""
import re

path = "src/url_capture.py"
content = open(path, encoding="utf-8").read()

# Find function boundaries by line numbers
lines = content.splitlines(keepends=True)
start_line = None
end_line = None

for i, line in enumerate(lines):
    if "def extract_initial_articles(" in line:
        start_line = i
    if start_line is not None and i > start_line and line.startswith("def "):
        end_line = i
        break

print(f"Function found: lines {start_line+1} to {end_line}")
print("First 3 lines:")
for l in lines[start_line:start_line+3]:
    print(repr(l))

NEW_FUNC = '''def extract_initial_articles(html: str, start_url: str) -> list[DiscoveredArticle]:
    """Parse Playwright-rendered NewsNow Vue.js DOM to extract article metadata."""
    text = html

    # In the rendered DOM, tracker URLs appear inside href attributes
    url_matches = list(re.finditer(
        r\'href="(https://c\\.newsnow\\.co\\.uk/A/(\\d+)\\?[^"\\s]+)"\',
        text
    ))
    print(f"[DEBUG] Found {len(url_matches)} tracker URLs in initial HTML")
    seen = set()
    articles = []

    for m in url_matches:
        tracker_url = m.group(1)
        article_id = m.group(2)
        if tracker_url in seen:
            continue
        seen.add(tracker_url)

        # Wider search window - timestamp is up to 1500 chars after the URL
        s = max(0, m.start() - 300)
        e = min(len(text), m.end() + 1500)
        window = text[s:e]

        # Vue.js renders timestamp as data-timestamp="<unix_epoch>"
        ts_match = (
            re.search(r\'data-timestamp="(\\d+)"\', window)
            or re.search(r\'data-time="([^"]+)"\', window)
            or re.search(r\'"timestamp":"([^"]+)"\', window)
        )

        # Title inside <span class="article-title ...">
        title_match = re.search(
            r\'class="article-title[^"]*"[^>]*>([^<]+)</span>\',
            window
        )

        ts = ts_match.group(1) if ts_match else None
        title = title_match.group(1).strip() if title_match else None

        if not ts:
            continue

        articles.append(DiscoveredArticle(
            list_page_url=start_url,
            tracker_url=tracker_url,
            grid_title=title,
            grid_source=None,
            grid_time_text=ts,
            grid_position=len(articles) + 1,
            tracker_article_id=article_id,
            timestamp=ts,
        ))

    print(f"[DEBUG] Final parsed articles: {len(articles)}")
    return articles

'''

# Replace lines start_line..end_line with new function
new_lines = lines[:start_line] + [NEW_FUNC] + lines[end_line:]
new_content = "".join(new_lines)

open(path, "w", encoding="utf-8").write(new_content)
print("Done! File updated.")
