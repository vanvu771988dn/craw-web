from __future__ import annotations

from typing import Protocol

from crawl4ai import AsyncWebCrawler

from src.core.runtime_models import BatchProcessingStats, RunStats
from src.database.persistence import Database


class DiscoveryStrategy(Protocol):
    async def discover_initial_batch(self, page, config: dict) -> list: ...

    async def discover_next_batch(self, page, config: dict, current_batch: list, position_offset: int) -> list: ...


class PaginationStrategy(Protocol):
    async def crawl(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        page,
        config: dict,
    ) -> RunStats: ...


class LinkResolutionStrategy(Protocol):
    async def resolve(self, crawler: AsyncWebCrawler, tracker_url: str, config: dict): ...


class ContentExtractionStrategy(Protocol):
    async def extract(
        self,
        crawler: AsyncWebCrawler,
        url: str,
        config: dict,
        *,
        expected_title: str | None = None,
        tracker_url: str | None = None,
        tracker_article_id: str | None = None,
    ): ...


class DedupStrategy(Protocol):
    async def apply(self, db: Database, article, config: dict) -> tuple[str, object]: ...


class ArticleBatchProcessor(Protocol):
    async def process(
        self,
        crawler: AsyncWebCrawler,
        db: Database,
        discovered_articles: list,
        config: dict,
    ) -> BatchProcessingStats: ...
