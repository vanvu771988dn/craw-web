"""
Extract and inspect window.__INITIAL_STATE__ from NewsNow static HTML.
"""
import urllib.request, re, json

url = 'https://www.newsnow.co.uk/h/Sport/Football/Bundesliga?type=ln'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-GB,en;q=0.9',
})
with urllib.request.urlopen(req, timeout=30) as r:
    html = r.read().decode('utf-8', errors='replace')

# Extract __INITIAL_STATE__
m = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*</script>', html, re.DOTALL)
if not m:
    print("No __INITIAL_STATE__ found!")
    exit(1)

raw = m.group(1)
print(f"Raw JSON length: {len(raw)}")

try:
    state = json.loads(raw)
except Exception as e:
    print(f"JSON parse failed: {e}")
    # Try to save raw for inspection
    with open('scripts/initial_state_raw.txt', 'w', encoding='utf-8') as f:
        f.write(raw[:5000])
    print("Saved first 5000 chars to scripts/initial_state_raw.txt")
    exit(1)

# Print top-level keys
print(f"Top-level keys: {list(state.keys())}")

# Walk through to find articles
def find_articles(obj, depth=0, path=""):
    if depth > 6:
        return
    if isinstance(obj, dict):
        # Check for article-like structure
        if 'timestamp' in obj and ('tracker' in str(obj).lower() or 'headline' in str(obj).lower()):
            print(f"  Found article-like dict at {path}: keys={list(obj.keys())[:10]}")
        for k, v in obj.items():
            find_articles(v, depth+1, f"{path}.{k}")
    elif isinstance(obj, list) and len(obj) > 0:
        # Check if list of articles
        if len(obj) > 3:
            print(f"  List at {path}: len={len(obj)}, type of first item: {type(obj[0]).__name__}")
            if isinstance(obj[0], dict):
                print(f"    First item keys: {list(obj[0].keys())[:15]}")
        find_articles(obj[0], depth+1, f"{path}[0]")

find_articles(state)

# Look specifically for articles/headlines keys
def find_key(obj, target_keys, path="", depth=0):
    if depth > 8:
        return
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.lower() in target_keys:
                print(f"\nKey '{k}' found at path: {path}.{k}")
                if isinstance(v, list) and v:
                    print(f"  List length: {len(v)}")
                    print(f"  First item: {json.dumps(v[0], ensure_ascii=False)[:300]}")
                elif isinstance(v, dict):
                    print(f"  Dict keys: {list(v.keys())[:10]}")
            find_key(v, target_keys, f"{path}.{k}", depth+1)
    elif isinstance(obj, list):
        for i, item in enumerate(obj[:2]):
            find_key(item, target_keys, f"{path}[{i}]", depth+1)

target = {'articles', 'headlines', 'items', 'feed', 'news', 'results', 'stories'}
find_key(state, target)
