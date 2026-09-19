import asyncio
from src.core.newsnow_discovery import build_newsnow_page_context, fetch_newsnow_articles_batch
import urllib.request

async def test():
    url = 'https://www.newsnow.co.uk/h/Sport/Football/Bundesliga?type=ln'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36',
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        html = r.read().decode('utf-8', errors='replace')
    
    ctx = build_newsnow_page_context(url, html)
    
    print("Calling backend with empty cursor...")
    try:
        batch = await fetch_newsnow_articles_batch(
            ctx,
            cursor_article_id="",
            cursor_ts="",
            timeout_ms=10000,
        )
        print(f"Success! Fetched {len(batch)} articles.")
        if batch:
            print(f"First article: id={batch[0].tracker_article_id}, ts={batch[0].timestamp}, url={batch[0].tracker_url}, title={batch[0].grid_title}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test())
