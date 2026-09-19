import re
from bs4 import BeautifulSoup

def test_parse_new_html():
    with open('scripts/initial_state_raw.txt', 'r', encoding='utf-8') as f:
        html = f.read()

    # The HTML string might be embedded in JS, let's unescape it loosely if needed
    html = html.replace('\\"', '"').replace('\\n', '\n').replace('\\/', '/')
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.select('a[href*="https://c.newsnow.co.uk/A/"]')
    print(f"Found {len(links)} links")
    for link in links[:3]:
        url = link.get('href')
        title = link.get_text(strip=True)
        print(f"URL: {url}, Title: {title}")

test_parse_new_html()
