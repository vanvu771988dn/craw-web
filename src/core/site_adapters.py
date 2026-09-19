from __future__ import annotations

from dataclasses import dataclass

from src.core.pagination_service import GenericUIPaginationStrategy, NewsNowPaginationStrategy
from src.core.strategy import PaginationStrategy


@dataclass(frozen=True, slots=True)
class SiteAdapter:
    name: str
    pagination_strategy: PaginationStrategy


def select_site_adapter(start_url: str | None) -> SiteAdapter:
    if start_url and "newsnow.co.uk" in start_url:
        return SiteAdapter(
            name="newsnow",
            pagination_strategy=NewsNowPaginationStrategy(),
        )

    return SiteAdapter(
        name="generic_ui",
        pagination_strategy=GenericUIPaginationStrategy(),
    )
