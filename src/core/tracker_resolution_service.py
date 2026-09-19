from crawl4ai import AsyncWebCrawler

from src.core.newsnow import TrackerResolutionResult, normalize_url, resolve_newsnow_tracker_url
from src.core.navigation import handle_navigation
from src.utils.file_logger import log_structured_event


async def resolve_with_browser_fallback(
    crawler: AsyncWebCrawler,
    tracker_url: str,
    config: dict,
) -> TrackerResolutionResult | None:
    """Falls back to browser navigation when tracker HTML parsing fails."""
    browser = crawler.crawler_strategy.browser_manager.browser
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    page = await context.new_page()
    try:
        await handle_navigation(page, tracker_url, config)
        final_url = normalize_url(page.url)
        if not final_url or final_url == normalize_url(tracker_url):
            log_structured_event(
                "tracker_resolution",
                "browser_fallback_failed",
                tracker_url=tracker_url,
                final_url=final_url,
            )
            return None

        log_structured_event(
            "tracker_resolution",
            "browser_fallback_succeeded",
            tracker_url=tracker_url,
            final_url=final_url,
        )
        return TrackerResolutionResult(
            tracker_url=tracker_url,
            final_url=final_url,
            tracker_article_id=None,
            redirect_delay_ms=None,
            manual_redirect=None,
            tracker_og_title=None,
            tracker_og_image=None,
            used_browser_fallback=True,
        )
    finally:
        await page.close()
        await context.close()


async def resolve_final_destination(
    crawler: AsyncWebCrawler,
    tracker_url: str,
    config: dict,
) -> TrackerResolutionResult | None:
    """Resolves a NewsNow tracker URL, preferring HTML parsing over browser redirects."""
    navigation_timeout = config.get("crawler", {}).get("navigation_timeout", 30000)
    try:
        resolution = await resolve_newsnow_tracker_url(tracker_url, timeout_ms=navigation_timeout)
        if resolution.final_url:
            return resolution
        log_structured_event(
            "tracker_resolution",
            "tracker_html_missing_final_url",
            tracker_url=tracker_url,
        )
    except Exception as exc:
        log_structured_event(
            "tracker_resolution",
            "tracker_html_resolution_failed",
            tracker_url=tracker_url,
            error=str(exc),
        )

    fallback_resolution = await resolve_with_browser_fallback(crawler, tracker_url, config)
    if fallback_resolution:
        return fallback_resolution

    log_structured_event(
        "tracker_resolution",
        "tracker_resolution_failed",
        tracker_url=tracker_url,
    )
    return None
