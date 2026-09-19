from crawl4ai import AsyncWebCrawler

from src.core.newsnow import normalize_url
from src.core.newsnow_discovery import DiscoveredArticle, ensure_latest_newsnow_url
from src.core.runtime_models import RunStats
from src.core.site_adapters import select_site_adapter
from src.database.persistence import get_db_instance
from src.utils.browser_utils import handle_browser_interactions
from src.utils.file_logger import log_structured_event


def _normalize_start_url(config: dict) -> tuple[dict, str | None]:
    start_url = config.get("crawler", {}).get("start_url")
    if not start_url:
        return config, start_url

    if "newsnow.co.uk" not in start_url:
        return config, start_url

    normalized_start_url = ensure_latest_newsnow_url(start_url)
    if normalized_start_url == start_url:
        return config, start_url

    log_structured_event(
        "discovery",
        "newsnow_start_url_normalized",
        original_start_url=start_url,
        normalized_start_url=normalized_start_url,
        reason="latest_feed_strategy",
    )
    next_config = dict(config)
    crawler_config = dict(next_config.get("crawler", {}))
    crawler_config["start_url"] = normalized_start_url
    next_config["crawler"] = crawler_config
    return next_config, normalized_start_url


def _log_run_summary(run_stats: RunStats | None) -> None:
    success_rate = (run_stats.saved / run_stats.processed) if run_stats and run_stats.processed else 0.0
    failure_rate = (run_stats.failed / run_stats.processed) if run_stats and run_stats.processed else 0.0
    log_structured_event(
        "discovery",
        "run_summary",
        batches=run_stats.batches if run_stats else 0,
        discovered=run_stats.discovered if run_stats else 0,
        processed=run_stats.processed if run_stats else 0,
        saved=run_stats.saved if run_stats else 0,
        duplicates=run_stats.duplicates if run_stats else 0,
        failed=run_stats.failed if run_stats else 0,
        skipped=run_stats.skipped if run_stats else 0,
        success_rate=round(success_rate, 4),
        failure_rate=round(failure_rate, 4),
    )


async def run_crawl(config: dict):
    """Initializes the crawler runtime and delegates execution to pagination strategies."""
    config, start_url = _normalize_start_url(config)
    if not start_url:
        print("Error: Missing start_url in configuration.")
        return

    db_path = config.get("database", {}).get("path")
    db = get_db_instance(db_path)
    adapter = select_site_adapter(start_url)
    log_structured_event("discovery", "crawl_started", start_url=start_url)

    page = None
    try:
        async with AsyncWebCrawler() as crawler:
            browser = crawler.crawler_strategy.browser_manager.browser
            page = await browser.new_page()
            await page.goto(start_url, timeout=config.get("crawler", {}).get("navigation_timeout", 30000))
            await handle_browser_interactions(page, config)
            log_structured_event("discovery", "site_adapter_selected", adapter=adapter.name, start_url=start_url)
            run_stats = await adapter.pagination_strategy.crawl(crawler, db, page, config)
            _log_run_summary(run_stats)
    except Exception as exc:
        log_structured_event("unknown", "crawl_failed", start_url=start_url, error=str(exc))
        print(f"An unexpected error occurred during the crawl: {exc}")
    finally:
        if page and not page.is_closed():
            await page.close()
        log_structured_event("discovery", "crawl_finished", start_url=start_url)


async def retry_failed_items(config: dict, stage: str | None = None, limit: int = 20) -> RunStats:
    """Retries previously failed items without rerunning the whole crawl."""
    db_path = config.get("database", {}).get("path")
    db = get_db_instance(db_path)
    failed_items = db.list_failed_items(limit=limit, stage=stage)
    discovered_articles: list[DiscoveredArticle] = []
    start_url = config.get("crawler", {}).get("start_url", "")

    seen_urls: set[str] = set()
    for item in failed_items:
        tracker_url = normalize_url(item.get("url"))
        if not tracker_url or tracker_url in seen_urls:
            continue
        seen_urls.add(tracker_url)
        discovered_articles.append(
            DiscoveredArticle(
                list_page_url=start_url,
                tracker_url=tracker_url,
                grid_title=None,
                grid_source=None,
                grid_time_text=None,
                grid_position=0,
                tracker_article_id=None,
                timestamp=None,
            )
        )

    run_stats = RunStats()
    if not discovered_articles:
        return run_stats

    from src.core.article_pipeline_service import process_discovered_articles

    async with AsyncWebCrawler() as crawler:
        batch_stats = await process_discovered_articles(crawler, db, discovered_articles, config)
        run_stats.add_batch(batch_stats)

    log_structured_event(
        "discovery",
        "failed_items_retried",
        stage=stage,
        limit=limit,
        retried=run_stats.processed,
        saved=run_stats.saved,
        failed=run_stats.failed,
        duplicates=run_stats.duplicates,
    )
    return run_stats
