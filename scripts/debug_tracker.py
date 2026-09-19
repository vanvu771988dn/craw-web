import urllib.request, re

url = 'https://c.newsnow.co.uk/A/1317384759?-50647:2220'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
with urllib.request.urlopen(req, timeout=15) as r:
    raw = r.read()
    content_type = r.headers.get('Content-Type', '')
    charset = 'utf-8'
    if 'charset=' in content_type:
        charset = content_type.split('charset=')[-1].strip().split(';')[0].strip()
    html = raw.decode(charset, errors='replace')

print('Charset:', charset)
print('HTML length:', len(html))

# Show all lines mentioning 'url'
for line in html.split('\n'):
    stripped = line.strip()
    if stripped.startswith('url:') or 'clickthroughConfig' in stripped or stripped.startswith("url '"):
        print('FOUND LINE:', repr(stripped))

# Test the exact regex used in newsnow.py
TRACKER_URL_RE = re.compile(r"url:\s*'([^']+)'", re.S)
m = TRACKER_URL_RE.search(html)
if m:
    print('REGEX MATCHED:', m.group(1))
else:
    print('REGEX DID NOT MATCH')
    # Try alternate patterns
    for pat in [r'url:\s*"([^"]+)"', r"\"url\":\s*'([^']+)'", r'\"url\":\s*\"([^\"]+)\"']:
        m2 = re.search(pat, html)
        if m2:
            print(f'ALT PATTERN {pat!r} matched:', m2.group(1))
