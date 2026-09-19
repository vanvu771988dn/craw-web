from crawl4ai import AsyncWebCrawler
from playwright.async_api import TimeoutError

from src.core.errors import CrawlStageError
from src.core.newsnow import normalize_url
from src.core.processing import process_content
from src.core.navigation import handle_navigation
from src.database.models import ScrapedData
from src.utils.file_logger import log_structured_event


async def navigate_and_extract(
    crawler: AsyncWebCrawler,
    url: str,
    config: dict,
    *,
    expected_title: str | None = None,
    tracker_url: str | None = None,
    tracker_article_id: str | None = None,
) -> ScrapedData | None:
    """Navigates to a final article URL and runs the content extraction pipeline."""
    log_structured_event(
        "capture",
        "navigation_started",
        final_url=url,
        tracker_url=tracker_url,
        tracker_article_id=tracker_article_id,
        expected_title=expected_title,
    )

    context = None
    page = None
    try:
        browser = crawler.crawler_strategy.browser_manager.browser
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        )
        page = await context.new_page()
        await handle_navigation(page, url, config)
        final_html = await page.content()
        final_url = normalize_url(page.url) or url
        return await process_content(
            crawler,
            final_html,
            final_url,
            config,
            expected_title=expected_title,
            tracker_url=tracker_url,
            tracker_article_id=tracker_article_id,
        )
    except TimeoutError:
        raise CrawlStageError(
            stage="capture",
            code="FINAL_PAGE_TIMEOUT",
            message=f"Navigation failed for {url} due to a timeout.",
            context={"final_url": url, "tracker_url": tracker_url, "tracker_article_id": tracker_article_id},
        )
    finally:
        if page:
            await page.close()
        if context:
            await context.close()
