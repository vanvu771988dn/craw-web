import re

def test_extract(html):
    text = html.replace('\\"', '"').replace('\\/', '/')
    url_matches = list(re.finditer(r'https://c\.newsnow\.co\.uk/A/(\d+)\?[^\'"\s]+', text))
    seen = set()
    articles = []
    
    for i, m in enumerate(url_matches):
        tracker_url = m.group(0)
        article_id = m.group(1)
        if tracker_url in seen:
            continue
        seen.add(tracker_url)
        
        start = max(0, m.start() - 600)
        end = min(len(text), m.end() + 600)
        window = text[start:end]
        
        ts_match = re.search(r'data-time="([^"]+)"', window) or re.search(r'timestamp":"([^"]+)"', window)
        title_match = re.search(r'class="article-title[^>]*>([^<]+)</span>', window) or re.search(r'"title":"([^"]+)"', window)
        
        ts = ts_match.group(1) if ts_match else None
        title = title_match.group(1) if title_match else None
        
        if not ts:
            continue
            
        articles.append((tracker_url, ts, title))
    return articles

import urllib.request
url = 'https://www.newsnow.co.uk/h/Sport/Football/Bundesliga?type=ln'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode('utf-8', errors='replace')

arts = test_extract(html)
print(f"Extracted {len(arts)} articles.")
if arts:
    print(arts[:3])
