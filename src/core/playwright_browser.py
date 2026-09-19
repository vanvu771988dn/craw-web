"""
playwright_browser.py – Shared Playwright + Stealth browser instance.

Provides a single Chromium browser context that is reused across all fetches
to avoid the overhead of launching/closing a browser for every request.

Playwright-Stealth hides bot fingerprints (navigator.webdriver, plugins,
language, etc.) so Cloudflare treats requests as real user traffic.

Usage:
    from src.core.playwright_browser import async_fetch_html, init_browser, close_browser

    await init_browser()
    html = await async_fetch_html("https://example.com")
    await close_browser()

Or use the context manager in run_capture for automatic lifecycle management.
"""

import asyncio
import random
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import stealth_async

# ---------------------------------------------------------------------------
# Module-level state – one browser instance for the whole script run
# ---------------------------------------------------------------------------

_playwright: Optional[Playwright] = None
_browser: Optional[Browser] = None
_context: Optional[BrowserContext] = None

# Semaphore: allow up to 5 parallel page fetches through the browser
_PAGE_SEMAPHORE = asyncio.Semaphore(5)

# Realistic user agent
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


async def init_browser() -> None:
    """Launch a headless Chromium browser with stealth settings."""
    global _playwright, _browser, _context

    if _browser is not None:
        return  # Already initialised

    print("[browser] Launching Playwright Chromium (headless) ...")
    _playwright = await async_playwright().start()
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    _context = await _browser.new_context(
        user_agent=_USER_AGENT,
        locale="en-GB",
        timezone_id="Europe/London",
        viewport={"width": 1280, "height": 800},
        # Accept real-browser headers
        extra_http_headers={
            "Accept-Language": "en-GB,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        },
    )
    print("[browser] Browser ready.")


async def close_browser() -> None:
    """Cleanly shut down the Playwright browser."""
    global _playwright, _browser, _context

    if _context:
        try:
            await _context.close()
        except Exception:
            pass  # Context may already be closed
        _context = None
    if _browser:
        try:
            await _browser.close()
        except Exception:
            pass
        _browser = None
    if _playwright:
        try:
            await _playwright.stop()
        except Exception:
            pass
        _playwright = None
    print("[browser] Browser closed.")


async def async_fetch_html(
    url: str,
    wait_for: str = "domcontentloaded",
    timeout_ms: int = 30000,
    extra_wait_ms: int = 0,
) -> str:
    """
    Fetch a URL using the shared Playwright browser and return the full HTML.

    Args:
        url: The URL to fetch.
        wait_for: Playwright wait_until strategy ('domcontentloaded', 'networkidle', 'load').
        timeout_ms: Navigation timeout in milliseconds.
        extra_wait_ms: Optional additional wait after page load (for JS-rendered content).

    Returns:
        The full page HTML as a string.
    """
    global _context

    if _context is None:
        await init_browser()

    async with _PAGE_SEMAPHORE:
        page: Page = await _context.new_page()  # type: ignore[union-attr]
        try:
            # Apply stealth patches to hide bot fingerprints
            await stealth_async(page)

            await page.goto(url, wait_until=wait_for, timeout=timeout_ms)

            if extra_wait_ms > 0:
                await asyncio.sleep(extra_wait_ms / 1000)

            html = await page.content()
            return html
        finally:
            await page.close()


async def async_fetch_html_no_redirect(
    url: str,
    timeout_ms: int = 15000,
) -> str:
    """
    Fetch a tracker URL and capture the page HTML BEFORE any JS redirect fires.

    NewsNow tracker pages contain the final article URL in a JS config object,
    then redirect via JS after a short delay. We intercept the page body from
    the network response before the redirect executes.

    Returns:
        The raw HTML of the tracker page (contains clickthroughConfig JS object).
    """
    global _context

    if _context is None:
        await init_browser()

    async with _PAGE_SEMAPHORE:
        page: Page = await _context.new_page()  # type: ignore[union-attr]
        try:
            await stealth_async(page)

            html_holder: list[str] = []

            async def handle_response(response):
                # Capture body from the FIRST response to the tracker URL
                if response.url == url and not html_holder:
                    try:
                        body = await response.body()
                        html_holder.append(body.decode("utf-8", errors="replace"))
                    except Exception:
                        pass

            page.on("response", handle_response)

            try:
                await page.goto(url, wait_until="commit", timeout=timeout_ms)
            except Exception as e:
                err_str = str(e)
                # ERR_ABORTED is expected - it means the JS redirect fired.
                # net::ERR_ABORTED and navigation errors are normal for tracker pages.
                if "ERR_ABORTED" not in err_str and "Unable to retrieve" not in err_str:
                    raise

            # If we captured the body via response event, return it
            if html_holder:
                return html_holder[0]

            # Fallback: try page.content() if navigation didn't abort immediately
            try:
                return await page.content()
            except Exception:
                return ""
        finally:
            try:
                await page.close()
            except Exception:
                pass  # Page may already be closed due to redirect/abort

