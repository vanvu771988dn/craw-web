# src/utils/browser_utils.py

from datetime import datetime, timedelta
from src.utils.datetime_util import parse_date

async def handle_browser_interactions(page, config: dict):
    """Handles general browser interactions like cookie consent."""
    # General-purpose cookie consent handling
    try:
        accept_button = page.locator(
            'button:text-matches("accept|agree|allow|got it|ok", "i"), '
            'a:text-matches("accept|agree|allow|got it|ok", "i")'
        ).first
        if await accept_button.is_visible():
            print("Cookie consent button found, attempting to click...")
            await accept_button.click()
            await page.wait_for_timeout(2000)
            print("Cookie consent button clicked.")
    except Exception as e:
        print(f"Could not find or click cookie consent button: {e}")
