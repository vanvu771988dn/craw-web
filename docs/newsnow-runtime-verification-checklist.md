# NewsNow Runtime Verification Checklist

## Goal

This checklist is for the first runtime verification pass once Python and test tooling are available in the environment.

Use it to answer three questions:

1. does the pipeline run end to end
2. does it produce the expected artifacts and metrics
3. are Feature 8 and Feature 14 strong enough to be marked fully complete

## Preconditions

- Python is installed and available in `PATH`
- test dependencies are installed
- crawl configuration is valid for the target environment
- output directories are writable
- a NewsNow start URL is configured

## Phase 1: Static Validation

- Run unit and regression tests.
- Confirm that the following test groups pass:
  - crawler orchestration
  - tracker resolution
  - extraction and validation
  - dedup
  - metrics
  - evaluation-set export/report
- Confirm that no import errors or missing-module errors exist after the refactor.

Expected outcome:

- baseline test suite passes cleanly
- module wiring is intact

## Phase 2: Controlled Crawl Run

- Run a small crawl against a known NewsNow page.
- Capture one short run intended for verification, not scale.
- Confirm that the crawler emits:
  - discovery events
  - resolution events
  - capture events
  - extraction events
  - dedup events
  - article save events
- Confirm that batch counters are populated:
  - processed
  - saved
  - duplicate
  - failed
  - skipped

Expected outcome:

- the end-to-end pipeline completes without crashing
- at least some articles reach `article_saved`

## Phase 3: Artifact Verification

- Inspect `crawl_events.jsonl`.
- Confirm that events include enough fields to debug failures:
  - `tracker_url`
  - `final_url`
  - `expected_title`
  - `candidate_count`
  - `title_similarity`
  - `content_length`
  - `paragraph_count`
  - `duplicate_status`
- Confirm that failed extraction cases write debug artifacts when expected.
- Confirm that metadata persistence includes:
  - tracker metadata
  - final article metadata
  - dedup metadata

Expected outcome:

- failed cases are diagnosable
- successful cases are traceable from discovery to persistence

## Phase 4: Metrics Verification

- Run [main_report_newsnow.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_report_newsnow.py).
- Verify that the report prints:
  - metrics summary
  - observed evaluation summary
  - fixture evaluation summary
- Review at least these metrics:
  - `success_rate`
  - `failure_rate`
  - `duplicate_ratio`
  - `tracker_html_success_rate`
  - `tracker_browser_fallback_rate`
  - `extraction_acceptance_rate`
  - `avg_content_length`
  - `avg_paragraph_count`
  - `avg_title_similarity`

Expected outcome:

- metrics can be generated from logs without manual cleanup
- the numbers look internally consistent

## Phase 5: Evaluation Set Verification

- Run [main_export_evaluation_set.py](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/src/main_export_evaluation_set.py).
- Generate or refresh `evaluation_set.observed.json`.
- Compare observed cases against fixture cases.
- Confirm that observed cases span multiple publisher domains.
- Manually inspect a sample of cases for:
  - correct resolved final URL
  - reasonable title match
  - clean main content
  - sane duplicate classification

Expected outcome:

- observed evaluation data is usable for regression tracking
- sample quality is good enough to harden Feature 8 and Feature 14

## Exit Criteria

Mark Feature 8 as fully complete only if:

- real multi-domain observed samples exist
- extracted content quality is acceptable across those samples
- validation gates are rejecting obviously bad captures

Mark Feature 14 as fully complete only if:

- observed evaluation set has meaningful real-run coverage
- report/export flows work on those real logs
- regression tests plus observed samples provide confidence against future breakage

## Failure Triage

If the run fails, classify the break by stage:

- discovery
- tracker resolution
- final page fetch
- extraction
- validation
- dedup
- persistence
- reporting/export

Then capture:

- failing input URL
- failure reason code
- whether retry succeeded
- whether fallback path was used
- whether debug artifact was produced

## Recommended Commands

These are the first commands the team should run once the runtime is available:

1. test suite command for the project
2. one small NewsNow crawl run
3. `src/main_report_newsnow.py`
4. `src/main_export_evaluation_set.py`

## Success Metrics For Sign-Off

Use these as initial sign-off checks:

- crawl completes without fatal crash
- `article_saved` events are present
- observed evaluation set contains real multi-domain cases
- extraction acceptance rate is stable
- tracker browser fallback rate stays low
- duplicate classification looks sane on manual spot checks

## Recommendation

Do not treat the remaining work as missing architecture. Treat it as production validation depth.

The current highest-value next step is not more refactor. It is:

1. run the system
2. collect real samples
3. verify metrics
4. close the remaining partial features with evidence
