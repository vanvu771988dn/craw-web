# NewsNow Status

## Current State

The NewsNow pipeline is now in a strong modular-monolith state with:

- backend-driven discovery
- tracker resolution with HTML-first parsing and browser fallback
- title-guided extraction
- article candidate scoring and validation gates
- hard dedup and heuristic semantic dedup
- embedding-assisted similarity baseline
- structured logging, metrics summarization, and evaluation-set tooling

## What Is Actually Complete

- Features 1, 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 13, 15 are effectively implemented in code
- Feature 14 is partially complete:
  - regression harness exists
  - representative fixture set exists
  - observed-log builder exists
  - export flow exists

## What Is Still Incomplete

### P1

- real observed evaluation set is still too thin
  - current logs do not yet provide enough `article_saved`-rich samples
- sample-based validation with real multi-domain NewsNow destinations is not yet complete

### P2

- embedding similarity is currently a deterministic hashing baseline
  - good enough as a pluggable stage
  - not yet a true model-based embedding provider

## Available Reports

- [src/main_report_newsnow.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_report_newsnow.py)
  - prints:
    - crawl metrics summary
    - observed evaluation summary
    - fixture evaluation summary

- [src/main_export_evaluation_set.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_export_evaluation_set.py)
  - exports observed evaluation cases from `data/crawl_events.jsonl`

## Implementation Tracking

- [newsnow-implementation-matrix.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-implementation-matrix.md)
  - feature-by-feature `Done / Partial / Todo` view
- [newsnow-runtime-verification-checklist.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-runtime-verification-checklist.md)
  - runtime verification checklist for closing remaining partial work
- [newsnow-windows-runbook.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-windows-runbook.md)
  - exact Windows commands for install, test, crawl, report, and export

## Practical Next Step

1. run the crawler until `article_saved` events accumulate
2. export `evaluation_set.observed.json`
3. compare observed summary vs fixture summary
4. curate stable observed cases into the maintained evaluation set
