import urllib.request, re
from src.core.newsnow_discovery import TRACKER_ARTICLE_ID_RE, TRACKER_URL_RE, DiscoveredArticle

def parse_html_regex(url, html):
    # Unescape common JS sequences just in case
    text = html.replace('\\"', '"').replace('\\/', '/')
    
    # 1. Find all tracker URLs
    # tracker_urls pattern: https://c.newsnow.co.uk/A/1317294644?-50647:2220
    url_matches = list(re.finditer(r'https://c\.newsnow\.co\.uk/A/(\d+)\?[^\'"\s]+', text))
    print(f"Found {len(url_matches)} URLs")
    
    # Let's look for timestamps and titles NEAR each URL
    for m in url_matches[:3]:
        tracker_url = m.group(0)
        article_id = m.group(1)
        
        # window 1000 chars before and after
        start = max(0, m.start() - 500)
        end = min(len(text), m.end() + 500)
        window = text[start:end]
        
        ts_match = re.search(r'data-time="([^"]+)"|timestamp":"([^"]+)"', window)
        title_match = re.search(r'class="article-title[^>]*>([^<]+)</span>|"title":"([^"]+)"', window)
        
        ts = ts_match.group(1) or ts_match.group(2) if ts_match else None
        title = title_match.group(1) or title_match.group(2) if title_match else None
        
        print(f"URL: {tracker_url}")
        print(f"  ID: {article_id}")
        print(f"  TS: {ts}")
        print(f"  Title: {title}")

url = 'https://www.newsnow.co.uk/h/Sport/Football/Bundesliga?type=ln'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode('utf-8', errors='replace')

parse_html_regex(url, html)
