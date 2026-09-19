# NewsNow Success Metrics

## Purpose

This document defines the minimum metrics used to evaluate crawl quality, throughput, and regression risk for the NewsNow pipeline.

It complements:

- [docs/architecture.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/architecture.md)
- [docs/newsnow-implementation-tasks.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-implementation-tasks.md)

## Metric Groups

### 1. Throughput Metrics

- `run_count`
  - Number of crawl runs represented in the log window.
- `total_batches`
  - Number of processed discovery batches.
- `total_discovered`
  - Number of discovered list items.
- `total_processed`
  - Number of items that entered the article pipeline.
- `total_saved`
  - Number of successfully persisted articles.

### 2. Outcome Metrics

- `success_rate = total_saved / total_processed`
- `failure_rate = total_failed / total_processed`
- `duplicate_ratio = total_duplicates / total_processed`

Interpretation:

- high `success_rate` usually means pipeline stability is improving
- high `failure_rate` signals extraction, navigation, or resolution regressions
- high `duplicate_ratio` may be normal for mature feeds, but a sudden jump can indicate broken stop logic or dedup drift

### 3. Resolution Metrics

- `tracker_html_success_rate`
  - Share of tracker resolutions handled by HTML parsing without browser fallback
- `tracker_browser_fallback_rate`
  - Share of tracker resolutions that required browser fallback

Interpretation:

- rising browser fallback rate is usually a cost/performance warning
- sudden drops in HTML success rate often indicate tracker parsing breakage

### 4. Extraction Quality Metrics

- `extraction_acceptance_rate`
  - Accepted extraction candidates / total accepted + rejected candidates
- `extraction_rejection_rate`
  - Rejected extraction candidates / total accepted + rejected candidates
- `avg_content_length`
  - Mean extracted content length for accepted candidates
- `avg_paragraph_count`
  - Mean extracted paragraph count for accepted candidates
- `avg_title_similarity`
  - Mean title similarity for accepted candidates where similarity was logged

Interpretation:

- falling `avg_content_length` can indicate truncation or noisy candidate selection
- falling `avg_paragraph_count` can indicate broken article boundary detection
- falling `avg_title_similarity` can indicate anchor-title matching regressions

## Minimum Regression Targets

These are initial targets, not hard SLOs:

- `success_rate >= 0.60`
- `failure_rate <= 0.25`
- `tracker_html_success_rate >= 0.50`
- `extraction_acceptance_rate >= 0.60`
- `avg_content_length >= 500`
- `avg_paragraph_count >= 3`
- `avg_title_similarity >= 0.60`

These should be recalibrated after enough production-like runs exist.

## Current Implementation

Metrics can now be derived from structured logs via:

- [src/core/metrics.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/core/metrics.py)

Current summary support:

- aggregate metrics from in-memory event lists
- aggregate metrics from `data/crawl_events.jsonl`

Related observability tooling:

- [src/main_export_evaluation_set.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_export_evaluation_set.py)
- [src/main_report_newsnow.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_report_newsnow.py)
- [src/core/evaluation_set.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/core/evaluation_set.py)

## What Is Still Missing

- environment-specific time series storage
- dashboarding
- alert thresholds
- real benchmark baselines from live multi-domain NewsNow runs

## Recommended Next Step

1. collect several real crawl runs
2. compute summaries from `crawl_events.jsonl`
3. compare against the regression targets above
4. refine thresholds before introducing more aggressive extraction or dedup changes
