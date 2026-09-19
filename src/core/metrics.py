import json
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass(slots=True)
class CrawlMetricsSummary:
    run_count: int = 0
    total_batches: int = 0
    total_discovered: int = 0
    total_processed: int = 0
    total_saved: int = 0
    total_duplicates: int = 0
    total_failed: int = 0
    total_skipped: int = 0
    success_rate: float = 0.0
    failure_rate: float = 0.0
    duplicate_ratio: float = 0.0
    tracker_html_success_rate: float = 0.0
    tracker_browser_fallback_rate: float = 0.0
    extraction_acceptance_rate: float = 0.0
    extraction_rejection_rate: float = 0.0
    avg_content_length: float = 0.0
    avg_paragraph_count: float = 0.0
    avg_title_similarity: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def load_structured_events(log_path: str | Path) -> list[dict]:
    path = Path(log_path)
    if not path.exists():
        return []

    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        events.append(json.loads(stripped))
    return events


def summarize_crawl_events(events: list[dict]) -> CrawlMetricsSummary:
    summary = CrawlMetricsSummary()

    tracker_html_successes = 0
    tracker_browser_fallback_successes = 0
    extraction_acceptances = 0
    extraction_rejections = 0
    total_content_length = 0
    total_paragraph_count = 0
    total_title_similarity = 0.0
    title_similarity_count = 0

    for event in events:
        stage = event.get("stage")
        name = event.get("event")

        if stage == "discovery" and name == "run_summary":
            summary.run_count += 1
            summary.total_batches += int(event.get("batches", 0) or 0)
            summary.total_discovered += int(event.get("discovered", 0) or 0)
            summary.total_processed += int(event.get("processed", 0) or 0)
            summary.total_saved += int(event.get("saved", 0) or 0)
            summary.total_duplicates += int(event.get("duplicates", 0) or 0)
            summary.total_failed += int(event.get("failed", 0) or 0)
            summary.total_skipped += int(event.get("skipped", 0) or 0)

        if stage == "tracker_resolution" and name == "tracker_html_parsed":
            tracker_html_successes += 1
        if stage == "tracker_resolution" and name == "browser_fallback_succeeded":
            tracker_browser_fallback_successes += 1

        if stage == "extraction" and name == "candidate_accepted":
            extraction_acceptances += 1
            total_content_length += int(event.get("content_length", 0) or 0)
            total_paragraph_count += int(event.get("paragraph_count", 0) or 0)
            title_similarity = event.get("title_similarity")
            if title_similarity is not None:
                total_title_similarity += float(title_similarity)
                title_similarity_count += 1

        if stage == "extraction" and name == "candidate_rejected":
            extraction_rejections += 1

    summary.success_rate = round(_safe_ratio(summary.total_saved, summary.total_processed), 4)
    summary.failure_rate = round(_safe_ratio(summary.total_failed, summary.total_processed), 4)
    summary.duplicate_ratio = round(_safe_ratio(summary.total_duplicates, summary.total_processed), 4)
    summary.tracker_html_success_rate = round(
        _safe_ratio(tracker_html_successes, tracker_html_successes + tracker_browser_fallback_successes),
        4,
    )
    summary.tracker_browser_fallback_rate = round(
        _safe_ratio(tracker_browser_fallback_successes, tracker_html_successes + tracker_browser_fallback_successes),
        4,
    )
    summary.extraction_acceptance_rate = round(
        _safe_ratio(extraction_acceptances, extraction_acceptances + extraction_rejections),
        4,
    )
    summary.extraction_rejection_rate = round(
        _safe_ratio(extraction_rejections, extraction_acceptances + extraction_rejections),
        4,
    )
    summary.avg_content_length = round(_safe_ratio(total_content_length, extraction_acceptances), 2)
    summary.avg_paragraph_count = round(_safe_ratio(total_paragraph_count, extraction_acceptances), 2)
    summary.avg_title_similarity = round(_safe_ratio(total_title_similarity, title_similarity_count), 4)
    return summary


def summarize_crawl_events_file(log_path: str | Path) -> CrawlMetricsSummary:
    return summarize_crawl_events(load_structured_events(log_path))
