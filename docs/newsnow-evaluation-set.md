# NewsNow Evaluation Set

## Purpose

This document explains how the NewsNow evaluation set is represented and how it can evolve from local representative fixtures into production-like observed samples.

## Current Sources

The evaluation set currently has two source types:

- `local_fixture`
  - hand-maintained representative cases committed in the repo
- `observed_log`
  - cases that can be extracted automatically from structured crawl events once enough runtime data exists

## Current Files

- [tests/fixtures/newsnow/evaluation_set.json](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/tests/fixtures/newsnow/evaluation_set.json)
- [tests/fixtures/newsnow/EVALUATION_NOTES.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/tests/fixtures/newsnow/EVALUATION_NOTES.md)
- [src/core/evaluation_set.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/core/evaluation_set.py)

## Automatic Builder

The builder in `src/core/evaluation_set.py` can derive evaluation cases from structured events when these are present:

- `capture.article_saved`
- `tracker_resolution.tracker_html_parsed` or `tracker_resolution.browser_fallback_succeeded`
- `extraction.candidate_accepted`

This allows the project to move from synthetic local fixtures toward observed real-world cases without changing the data model.

An export entrypoint also exists:

- [src/main_export_evaluation_set.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_export_evaluation_set.py)

It writes observed cases to:

- `tests/fixtures/newsnow/evaluation_set.observed.json`

## Current Limitation

The current `data/crawl_events.jsonl` does not yet contain enough complete saved-article events to produce a meaningful real observed sample set automatically.

So:

- the regression harness exists
- the data model for real observed cases exists
- the actual observed sample set is still incomplete

## Recommended Next Step

1. run the crawler until `article_saved` events exist in sufficient quantity
2. build observed evaluation cases from `crawl_events.jsonl`
3. review and curate the generated cases
4. merge stable observed cases into the maintained evaluation set
