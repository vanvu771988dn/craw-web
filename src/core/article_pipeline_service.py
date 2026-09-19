from dataclasses import dataclass

from crawl4ai import AsyncWebCrawler

from src.core.article_capture_service import navigate_and_extract
from src.core.dedup import classify_semantic_duplicate
from src.core.errors import CrawlStageError
from src.core.newsnow import TrackerResolutionResult, normalize_url
from src.core.newsnow_discovery import DiscoveredArticle
from src.core.retry import retry_async
from src.core.runtime_models import BatchProcessingStats
from src.core.strategy import ArticleBatchProcessor
from src.core.tracker_resolution_service import resolve_final_destination
from src.database.models import ScrapedData
from src.database.persistence import Database
from src.utils.file_logger import log_structured_event


def apply_discovery_and_tracker_metadata(
    scraped_data: ScrapedData,
    article: DiscoveredArticle,
    resolution: TrackerResolutionResult,
) -> ScrapedData:
    scraped_data.list_page_url = article.list_page_url
    scraped_data.grid_title = article.grid_title
    scraped_data.grid_source = article.grid_source
    scraped_data.grid_time_text = article.grid_time_text
    scraped_data.grid_position = article.grid_position
    scraped_data.tracker_url = resolution.tracker_url or article.tracker_url
    scraped_data.tracker_article_id = resolution.tracker_article_id or article.tracker_article_id
    scraped_data.redirect_delay_ms = resolution.redirect_delay_ms
    scraped_data.manual_redirect = resolution.manual_redirect
    scraped_data.tracker_og_title = resolution.tracker_og_title
    scraped_data.tracker_og_image = resolution.tracker_og_image
    if not scraped_data.source_site and article.grid_source:
        scraped_data.source_site = article.grid_source
    return scraped_data


def filter_new_discovered_articles(
    discovered_articles: list[DiscoveredArticle],
    seen_tracker_urls: set[str],
) -> list[DiscoveredArticle]:
    new_articles: list[DiscoveredArticle] = []
    for article in discovered_articles:
        tracker_url = normalize_url(article.tracker_url)
        if not tracker_url or tracker_url in seen_tracker_urls:
            continue
        seen_tracker_urls.add(tracker_url)
        new_articles.append(article)
    return new_articles


async def process_discovered_articles(
    crawler: AsyncWebCrawler,
    db: Database,
    discovered_articles: list[DiscoveredArticle],
    config: dict,
) -> BatchProcessingStats:
    stats = BatchProcessingStats(discovered=len(discovered_articles))
    seen_tracker_urls: set[str] = set()
    fetch_attempts = config.get("crawler", {}).get("retry_attempts", {}).get("final_page_fetch", 2)
    semantic_duplicate_window_hours = config.get("crawler", {}).get("semantic_duplicate_window_hours", 72)
    embedding_config = (
        config.get("crawler", {})
        .get("semantic_similarity", {})
        .get("embedding", {})
    )

    for article in discovered_articles:
        tracker_url = normalize_url(article.tracker_url)
        if not tracker_url:
            log_structured_event("discovery", "link_skipped_missing_href")
            stats.skipped += 1
            continue
        if tracker_url in seen_tracker_urls:
            log_structured_event(
                "discovery",
                "link_skipped_duplicate_in_batch",
                tracker_url=tracker_url,
            )
            stats.skipped += 1
            continue

        seen_tracker_urls.add(tracker_url)
        expected_title = article.grid_title if article.grid_title and len(article.grid_title.strip()) >= 15 else None
        stats.processed += 1

        try:
            resolution = await resolve_final_destination(crawler, tracker_url, config)
            if not resolution or not resolution.final_url:
                raise CrawlStageError(
                    stage="tracker_resolution",
                    code="FINAL_URL_NOT_RESOLVED",
                    message="Failed to resolve tracker URL into a final destination.",
                    context={"tracker_url": tracker_url, "expected_title": expected_title},
                )

            if not expected_title and resolution.tracker_og_title:
                expected_title = resolution.tracker_og_title

            final_url = normalize_url(resolution.final_url)
            if db.article_exists(tracker_url=tracker_url, final_url=final_url):
                log_structured_event(
                    "dedup",
                    "duplicate_detected_before_capture",
                    tracker_url=tracker_url,
                    final_url=final_url,
                    duplicate_status="existing_tracker_or_final_url",
                )
                stats.duplicates += 1
                continue

            if db.article_exists(
                tracker_url=tracker_url,
                final_url=final_url,
                tracker_article_id=resolution.tracker_article_id or article.tracker_article_id,
            ):
                log_structured_event(
                    "dedup",
                    "duplicate_detected_before_capture",
                    tracker_url=tracker_url,
                    final_url=final_url,
                    tracker_article_id=resolution.tracker_article_id or article.tracker_article_id,
                    duplicate_status="existing_tracker_article_id",
                )
                stats.duplicates += 1
                continue

            async def navigate_operation():
                return await navigate_and_extract(
                    crawler,
                    final_url,
                    config,
                    expected_title=expected_title,
                    tracker_url=tracker_url,
                    tracker_article_id=resolution.tracker_article_id or article.tracker_article_id,
                )

            scraped_data = await retry_async(
                navigate_operation,
                attempts=fetch_attempts,
                stage="capture",
                event="final_page_fetch_retry",
                context={"tracker_url": tracker_url, "final_url": final_url},
            )
            if not scraped_data:
                stats.failed += 1
                continue

            scraped_data = apply_discovery_and_tracker_metadata(scraped_data, article, resolution)
            duplicate_of, duplicate_reason = db.find_existing_article(scraped_data)
            if duplicate_of:
                log_structured_event(
                    "dedup",
                    "duplicate_detected_before_save",
                    tracker_url=scraped_data.tracker_url,
                    final_url=scraped_data.final_url,
                    canonical_url=scraped_data.canonical_url,
                    tracker_article_id=scraped_data.tracker_article_id,
                    normalized_title=scraped_data.normalized_title,
                    duplicate_status="exact_duplicate",
                    duplicate_of=duplicate_of,
                    duplicate_reason=duplicate_reason,
                )
                stats.duplicates += 1
                continue

            semantic_duplicate = classify_semantic_duplicate(
                scraped_data,
                db.list_recent_articles(),
                time_window_hours=semantic_duplicate_window_hours,
                embedding_config=embedding_config,
            )
            scraped_data.duplicate_status = semantic_duplicate.duplicate_status
            scraped_data.duplicate_of = semantic_duplicate.duplicate_of
            scraped_data.story_cluster_id = semantic_duplicate.story_cluster_id
            scraped_data.similarity_score = semantic_duplicate.similarity_score
            if scraped_data.duplicate_status == "unique":
                scraped_data.story_cluster_id = (
                    scraped_data.story_cluster_id
                    or f"story-{scraped_data.tracker_article_id or scraped_data.normalized_title or 'unknown'}"
                )

            db.save_scraped_data(scraped_data)
            log_structured_event(
                "capture",
                "article_saved",
                tracker_url=scraped_data.tracker_url,
                final_url=scraped_data.final_url,
                tracker_article_id=scraped_data.tracker_article_id,
                canonical_url=scraped_data.canonical_url,
                duplicate_status=scraped_data.duplicate_status,
                duplicate_of=scraped_data.duplicate_of,
                story_cluster_id=scraped_data.story_cluster_id,
                similarity_score=scraped_data.similarity_score,
                normalized_title=scraped_data.normalized_title,
            )
            stats.saved += 1
        except CrawlStageError as exc:
            error_fields = {
                "tracker_url": tracker_url,
                "code": exc.code,
                "error": exc.message,
                **exc.context,
            }
            log_structured_event(exc.stage, "stage_failed", **error_fields)
            db.log_error(tracker_url, exc.message, stage=exc.stage, code=exc.code, context=exc.context)
            stats.failed += 1
        except Exception as exc:
            log_structured_event(
                "unknown",
                "stage_failed",
                tracker_url=tracker_url,
                code="UNEXPECTED_ERROR",
                error=str(exc),
            )
            db.log_error(tracker_url, str(exc), stage="unknown", code="UNEXPECTED_ERROR")
            stats.failed += 1

    return stats


@dataclass(slots=True)
class ArticlePipelineProcessor(ArticleBatchProcessor):
    async def process(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        discovered_articles: list[DiscoveredArticle],
        config: dict,
    ) -> BatchProcessingStats:
        return await process_discovered_articles(crawler, db, discovered_articles, config)
