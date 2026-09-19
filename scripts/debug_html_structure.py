import asyncio, re
from src.core.playwright_browser import init_browser, close_browser, async_fetch_html

async def debug():
    await init_browser()
    try:
        html = await async_fetch_html(
            'https://www.newsnow.co.uk/h/Sport/Football/Premier+League?type=ln',
            timeout_ms=30000
        )
        text = html.replace('\\"', '"').replace('\\/', '/')
        url_matches = list(re.finditer(r'https://c\.newsnow\.co\.uk/A/\d+\?[^\x27\"\s]+', text))
        print(f'Total tracker URLs found: {len(url_matches)}')
        if url_matches:
            m = url_matches[0]
            start = max(0, m.start() - 800)
            end = min(len(text), m.end() + 800)
            window = text[start:end]
            print('--- WINDOW AROUND FIRST TRACKER URL ---')
            print(window)
            print('--- END ---')
            # Also search for data-time in whole doc
            dt_matches = re.findall(r'data-time="([^"]+)"', text)
            print(f'data-time occurrences in full HTML: {len(dt_matches)}')
            ts_matches = re.findall(r'"timestamp":"([^"]+)"', text)
            print(f'"timestamp" occurrences in full HTML: {len(ts_matches)}')
            # Print first 3 to see format
            for t in dt_matches[:3]:
                print(f'  data-time: {t}')
    finally:
        await close_browser()

asyncio.run(debug())
