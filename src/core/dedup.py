from dataclasses import dataclass
from datetime import datetime, timedelta

from src.core.article_candidates import compute_text_similarity
from src.core.embeddings import compute_hashing_embedding_similarity
from src.database.models import ScrapedData
from src.utils.content_utils import compute_token_overlap


@dataclass(slots=True)
class SemanticDuplicateResult:
    duplicate_status: str
    duplicate_of: int | None = None
    story_cluster_id: str | None = None
    similarity_score: float | None = None


def classify_semantic_duplicate(
    article: ScrapedData,
    recent_articles: list[dict],
    time_window_hours: int = 72,
    embedding_config: dict | None = None,
) -> SemanticDuplicateResult:
    """Classifies an article against recent items as exact, near, same-story, or unique."""
    article_reference_time = article.published_at or article.crawled_at
    best_result = SemanticDuplicateResult(duplicate_status="unique")
    best_rank = 0
    embedding_settings = embedding_config or {}
    embedding_enabled = bool(embedding_settings.get("enabled", False))
    embedding_dimensions = int(embedding_settings.get("dimensions", 128) or 128)
    near_duplicate_threshold = float(embedding_settings.get("near_duplicate_threshold", 0.82) or 0.82)
    same_story_threshold = float(embedding_settings.get("same_story_threshold", 0.62) or 0.62)

    for existing in recent_articles:
        existing_id = existing.get("id")
        if existing_id is None:
            continue

        existing_reference_time = existing.get("published_at") or existing.get("crawled_at")
        if isinstance(article_reference_time, datetime) and isinstance(existing_reference_time, datetime):
            if abs(article_reference_time - existing_reference_time) > timedelta(hours=time_window_hours):
                continue

        title_similarity = compute_text_similarity(article.title or article.grid_title, existing.get("title") or existing.get("grid_title"))
        content_overlap = compute_token_overlap(article.main_content, existing.get("main_content"))
        entity_overlap = compute_token_overlap(article.title or article.grid_title, existing.get("title") or existing.get("grid_title"))
        heuristic_similarity = max(title_similarity, (title_similarity + content_overlap + entity_overlap) / 3)
        embedding_similarity = None
        if embedding_enabled:
            embedding_similarity = compute_hashing_embedding_similarity(
                f"{article.title or article.grid_title}\n{article.main_content}",
                f"{existing.get('title') or existing.get('grid_title')}\n{existing.get('main_content') or ''}",
                dimensions=embedding_dimensions,
            )
        similarity_score = max(
            heuristic_similarity,
            embedding_similarity if embedding_similarity is not None else 0.0,
        )

        existing_fingerprint = existing.get("content_fingerprint")
        if article.content_fingerprint and existing_fingerprint and article.content_fingerprint == existing_fingerprint:
            return SemanticDuplicateResult(
                duplicate_status="exact_duplicate",
                duplicate_of=existing_id,
                story_cluster_id=existing.get("story_cluster_id") or f"story-{existing_id}",
                similarity_score=1.0,
            )

        candidate_result: SemanticDuplicateResult | None = None
        rank = 0
        if title_similarity >= 0.9 and (
            content_overlap >= 0.65
            or entity_overlap >= 0.85
            or (embedding_similarity is not None and embedding_similarity >= near_duplicate_threshold)
        ):
            candidate_result = SemanticDuplicateResult(
                duplicate_status="near_duplicate",
                duplicate_of=existing_id,
                story_cluster_id=existing.get("story_cluster_id") or f"story-{existing_id}",
                similarity_score=round(similarity_score, 4),
            )
            rank = 3
        elif (
            title_similarity >= 0.55
            and (entity_overlap >= 0.4 or content_overlap >= 0.3)
        ) or (
            embedding_similarity is not None and embedding_similarity >= same_story_threshold
        ):
            candidate_result = SemanticDuplicateResult(
                duplicate_status="same_story",
                duplicate_of=existing_id,
                story_cluster_id=existing.get("story_cluster_id") or f"story-{existing_id}",
                similarity_score=round(similarity_score, 4),
            )
            rank = 2

        if candidate_result and rank > best_rank:
            best_result = candidate_result
            best_rank = rank

    return best_result
