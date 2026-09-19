from src.core.metrics import summarize_crawl_events


def test_summarize_crawl_events_computes_regression_metrics():
    events = [
        {
            "stage": "tracker_resolution",
            "event": "tracker_html_parsed",
        },
        {
            "stage": "tracker_resolution",
            "event": "browser_fallback_succeeded",
        },
        {
            "stage": "extraction",
            "event": "candidate_accepted",
            "content_length": 900,
            "paragraph_count": 4,
            "title_similarity": 0.8,
        },
        {
            "stage": "extraction",
            "event": "candidate_accepted",
            "content_length": 600,
            "paragraph_count": 3,
            "title_similarity": 0.6,
        },
        {
            "stage": "extraction",
            "event": "candidate_rejected",
        },
        {
            "stage": "discovery",
            "event": "run_summary",
            "batches": 3,
            "discovered": 50,
            "processed": 20,
            "saved": 12,
            "duplicates": 5,
            "failed": 3,
            "skipped": 0,
        },
    ]

    summary = summarize_crawl_events(events)

    assert summary.run_count == 1
    assert summary.total_batches == 3
    assert summary.total_discovered == 50
    assert summary.total_processed == 20
    assert summary.total_saved == 12
    assert summary.total_duplicates == 5
    assert summary.total_failed == 3
    assert summary.success_rate == 0.6
    assert summary.failure_rate == 0.15
    assert summary.duplicate_ratio == 0.25
    assert summary.tracker_html_success_rate == 0.5
    assert summary.tracker_browser_fallback_rate == 0.5
    assert summary.extraction_acceptance_rate == 0.6667
    assert summary.extraction_rejection_rate == 0.3333
    assert summary.avg_content_length == 750.0
    assert summary.avg_paragraph_count == 3.5
    assert summary.avg_title_similarity == 0.7
