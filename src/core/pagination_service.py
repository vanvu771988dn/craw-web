import asyncio
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

from src.core.article_pipeline_service import ArticlePipelineProcessor, filter_new_discovered_articles
from src.core.errors import CrawlStageError
from src.core.newsnow import TRACKER_ARTICLE_ID_RE, normalize_url
from src.core.newsnow_discovery import (
    DiscoveredArticle,
    build_newsnow_page_context,
    fetch_newsnow_articles_batch,
    parse_initial_newsnow_batch,
)
from src.core.runtime_models import RunStats
from src.core.strategy import PaginationStrategy
from src.database.persistence import Database
from src.utils.file_logger import log_structured_event


def collect_seen_tracker_urls(discovered_articles: list[DiscoveredArticle]) -> set[str]:
    seen_tracker_urls: set[str] = set()
    for article in discovered_articles:
        tracker_url = normalize_url(article.tracker_url)
        if tracker_url:
            seen_tracker_urls.add(tracker_url)
    return seen_tracker_urls


def build_discovered_article_from_link(link_element, start_url: str, position: int) -> DiscoveredArticle | None:
    href = link_element.get("href")
    if not href:
        return None

    tracker_url = normalize_url(urljoin(start_url, href))
    if not tracker_url:
        return None

    text = " ".join(link_element.get_text(" ", strip=True).split()) or None
    tracker_article_id_match = TRACKER_ARTICLE_ID_RE.search(tracker_url)
    return DiscoveredArticle(
        list_page_url=start_url,
        tracker_url=tracker_url,
        grid_title=text,
        grid_source=None,
        grid_time_text=None,
        grid_position=position,
        tracker_article_id=tracker_article_id_match.group(1) if tracker_article_id_match else None,
        timestamp=None,
    )


def _merge_run_stats(target: RunStats, source: RunStats) -> RunStats:
    target.batches += source.batches
    target.discovered += source.discovered
    target.processed += source.processed
    target.saved += source.saved
    target.duplicates += source.duplicates
    target.failed += source.failed
    target.skipped += source.skipped
    return target


@dataclass(slots=True)
class GenericUIPaginationStrategy(PaginationStrategy):
    article_processor: ArticlePipelineProcessor = field(default_factory=ArticlePipelineProcessor)

    async def _process_link_elements(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        link_elements: list,
        start_url: str,
        config: dict,
        seen_tracker_urls: set[str],
    ):
        discovered_articles = [
            article
            for position, link_element in enumerate(link_elements, start=1)
            if (article := build_discovered_article_from_link(link_element, start_url, position)) is not None
        ]
        current_batch = filter_new_discovered_articles(discovered_articles, seen_tracker_urls)
        return await self.article_processor.process(crawler, db, current_batch, config)

    async def crawl(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        page,
        config: dict,
    ) -> RunStats:
        start_url = config.get("crawler", {}).get("start_url")
        link_selector = config.get("crawler", {}).get("content_link_selector")
        load_more_selector = config.get("crawler", {}).get("load_more_selector")
        duplicate_ratio_threshold = config.get("crawler", {}).get("duplicate_ratio_threshold", 0.8)
        max_empty_batches = config.get("crawler", {}).get("max_empty_batches", 2)
        no_new_content_streak = 0
        run_stats = RunStats()
        seen_tracker_urls: set[str] = set()

        while True:
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")
            link_elements = soup.select(link_selector)
            if not link_elements:
                log_structured_event("discovery", "crawl_stopped", reason="no_content_links_found")
                return run_stats

            log_structured_event("discovery", "batch_discovered", discovered=len(link_elements), start_url=start_url)
            batch_stats = await self._process_link_elements(
                crawler,
                db,
                link_elements,
                start_url,
                config,
                seen_tracker_urls,
            )
            log_structured_event(
                "discovery",
                "batch_summary",
                discovered=batch_stats.discovered,
                processed=batch_stats.processed,
                saved=batch_stats.saved,
                duplicates=batch_stats.duplicates,
                failed=batch_stats.failed,
                skipped=batch_stats.skipped,
            )
            run_stats.add_batch(batch_stats)

            if batch_stats.saved == 0:
                no_new_content_streak += 1
            else:
                no_new_content_streak = 0

            duplicate_ratio = batch_stats.duplicates / batch_stats.processed if batch_stats.processed else 0.0
            if batch_stats.processed == 0:
                log_structured_event("discovery", "crawl_stopped", reason="no_processable_links")
                return run_stats
            if duplicate_ratio >= duplicate_ratio_threshold:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="duplicate_ratio_threshold",
                    duplicate_ratio=duplicate_ratio,
                    threshold=duplicate_ratio_threshold,
                )
                return run_stats
            if no_new_content_streak >= max_empty_batches:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="no_new_content_streak",
                    no_new_content_streak=no_new_content_streak,
                )
                return run_stats

            try:
                await page.wait_for_selector(load_more_selector, state="visible", timeout=10000)
                await page.click(load_more_selector)
                await asyncio.sleep(5)
            except Exception as exc:
                log_structured_event("discovery", "crawl_stopped", reason="load_more_unavailable", error=str(exc))
                return run_stats


@dataclass(slots=True)
class NewsNowPaginationStrategy(PaginationStrategy):
    article_processor: ArticlePipelineProcessor = field(default_factory=ArticlePipelineProcessor)

    async def _crawl_ui_fallback(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        page,
        config: dict,
        seen_newsnow_tracker_urls: set[str] | None = None,
    ) -> RunStats:
        start_url = config.get("crawler", {}).get("start_url")
        load_more_selector = config.get("crawler", {}).get("load_more_selector")
        duplicate_ratio_threshold = config.get("crawler", {}).get("duplicate_ratio_threshold", 0.8)
        max_empty_batches = config.get("crawler", {}).get("max_empty_batches", 2)
        seen_newsnow_tracker_urls = set(seen_newsnow_tracker_urls or set())
        no_new_content_streak = 0
        run_stats = RunStats()

        while True:
            html_content = await page.content()
            discovered_articles = parse_initial_newsnow_batch(start_url, html_content)
            current_batch = filter_new_discovered_articles(discovered_articles, seen_newsnow_tracker_urls)
            if not current_batch:
                log_structured_event(
                    "discovery",
                    "batch_discovered",
                    discovered=0,
                    start_url=start_url,
                    mode="ui_newsnow_fallback",
                )
                log_structured_event("discovery", "crawl_stopped", reason="no_new_ui_fallback_links")
                return run_stats

            log_structured_event(
                "discovery",
                "batch_discovered",
                discovered=len(current_batch),
                start_url=start_url,
                mode="ui_newsnow_fallback",
            )
            batch_stats = await self.article_processor.process(crawler, db, current_batch, config)
            log_structured_event(
                "discovery",
                "batch_summary",
                discovered=batch_stats.discovered,
                processed=batch_stats.processed,
                saved=batch_stats.saved,
                duplicates=batch_stats.duplicates,
                failed=batch_stats.failed,
                skipped=batch_stats.skipped,
                mode="ui_newsnow_fallback",
            )
            run_stats.add_batch(batch_stats)

            if batch_stats.saved == 0:
                no_new_content_streak += 1
            else:
                no_new_content_streak = 0

            duplicate_ratio = batch_stats.duplicates / batch_stats.processed if batch_stats.processed else 0.0
            if batch_stats.processed == 0:
                log_structured_event("discovery", "crawl_stopped", reason="no_processable_links")
                return run_stats
            if duplicate_ratio >= duplicate_ratio_threshold:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="duplicate_ratio_threshold",
                    duplicate_ratio=duplicate_ratio,
                    threshold=duplicate_ratio_threshold,
                )
                return run_stats
            if no_new_content_streak >= max_empty_batches:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="no_new_content_streak",
                    no_new_content_streak=no_new_content_streak,
                )
                return run_stats

            try:
                await page.wait_for_selector(load_more_selector, state="visible", timeout=10000)
                await page.click(load_more_selector)
                await asyncio.sleep(5)
            except Exception as exc:
                log_structured_event("discovery", "crawl_stopped", reason="load_more_unavailable", error=str(exc))
                return run_stats

    async def crawl(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        page,
        config: dict,
    ) -> RunStats:
        start_url = config.get("crawler", {}).get("start_url")
        navigation_timeout = config.get("crawler", {}).get("navigation_timeout", 30000)
        duplicate_ratio_threshold = config.get("crawler", {}).get("duplicate_ratio_threshold", 0.8)
        max_empty_batches = config.get("crawler", {}).get("max_empty_batches", 2)
        discovery_retries = config.get("crawler", {}).get("retry_attempts", {}).get("discovery", 2)

        html_content = await page.content()
        page_context = build_newsnow_page_context(start_url, html_content)
        current_batch = parse_initial_newsnow_batch(start_url, html_content)
        if not current_batch:
            raise CrawlStageError(
                stage="discovery",
                code="INITIAL_BATCH_EMPTY",
                message="Initial NewsNow page did not yield any discoverable articles.",
                context={"start_url": start_url},
            )

        run_stats = RunStats()
        no_new_content_streak = 0
        position_offset = 0
        seen_newsnow_tracker_urls = collect_seen_tracker_urls(current_batch)

        while current_batch:
            log_structured_event(
                "discovery",
                "batch_discovered",
                discovered=len(current_batch),
                start_url=start_url,
                mode="backend_newsnow" if position_offset else "initial_dom",
            )
            batch_stats = await self.article_processor.process(crawler, db, current_batch, config)
            log_structured_event(
                "discovery",
                "batch_summary",
                discovered=batch_stats.discovered,
                processed=batch_stats.processed,
                saved=batch_stats.saved,
                duplicates=batch_stats.duplicates,
                failed=batch_stats.failed,
                skipped=batch_stats.skipped,
                mode="backend_newsnow" if position_offset else "initial_dom",
            )
            run_stats.add_batch(batch_stats)

            if batch_stats.saved == 0:
                no_new_content_streak += 1
            else:
                no_new_content_streak = 0

            duplicate_ratio = batch_stats.duplicates / batch_stats.processed if batch_stats.processed else 0.0
            if batch_stats.processed == 0:
                log_structured_event("discovery", "crawl_stopped", reason="no_processable_links")
                return run_stats
            if duplicate_ratio >= duplicate_ratio_threshold:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="duplicate_ratio_threshold",
                    duplicate_ratio=duplicate_ratio,
                    threshold=duplicate_ratio_threshold,
                )
                return run_stats
            if no_new_content_streak >= max_empty_batches:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="no_new_content_streak",
                    no_new_content_streak=no_new_content_streak,
                )
                return run_stats

            last_article = current_batch[-1]
            if not last_article.tracker_article_id or not last_article.timestamp:
                log_structured_event(
                    "discovery",
                    "crawl_stopped",
                    reason="missing_backend_cursor",
                    tracker_article_id=last_article.tracker_article_id,
                    timestamp=last_article.timestamp,
                )
                return run_stats

            position_offset += len(current_batch)
            try:
                next_batch = await fetch_newsnow_articles_batch(
                    page_context,
                    cursor_article_id=last_article.tracker_article_id,
                    cursor_ts=last_article.timestamp,
                    timeout_ms=navigation_timeout,
                    position_offset=position_offset,
                    retries=discovery_retries,
                )
            except CrawlStageError as exc:
                log_structured_event(
                    "discovery",
                    "backend_batch_failed_falling_back_to_ui",
                    code=exc.code,
                    error=exc.message,
                    **exc.context,
                )
                fallback_stats = await self._crawl_ui_fallback(
                    crawler,
                    db,
                    page,
                    config,
                    seen_newsnow_tracker_urls=seen_newsnow_tracker_urls,
                )
                return _merge_run_stats(run_stats, fallback_stats)

            if not next_batch:
                log_structured_event("discovery", "crawl_stopped", reason="empty_backend_batch")
                return run_stats
            seen_newsnow_tracker_urls.update(collect_seen_tracker_urls(next_batch))
            current_batch = next_batch

        return run_stats
