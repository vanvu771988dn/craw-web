# NewsNow Windows Runbook

## Goal

This runbook gives the team exact Windows commands for:

- installing dependencies
- running tests
- running the crawler
- generating NewsNow metrics and evaluation reports
- exporting observed evaluation cases

It is designed for this repository layout and its current entrypoints.

## Assumptions

- the repo root is the current working directory
- Python will be available through the project virtual environment
- the virtual environment path is `.venv\Scripts\python.exe`

## 1. Install Dependencies

Runtime dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Runtime + test dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

## 2. Run the Test Suite

Full test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Single test file examples:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_crawler.py
.\.venv\Scripts\python.exe -m pytest tests\test_newsnow_regression.py
.\.venv\Scripts\python.exe -m pytest tests\test_metrics.py
```

## 3. Run the NewsNow Crawler

Default crawl run:

```powershell
.\.venv\Scripts\python.exe -m src.main
```

What this should do:

- load `config\config.yaml`
- initialize `data\crawler.db`
- run the NewsNow crawl pipeline
- append structured events to `data\crawl_events.jsonl`

## 4. Generate Metrics and Evaluation Summary

Run the report entrypoint:

```powershell
.\.venv\Scripts\python.exe -m src.main_report_newsnow
```

Expected sections:

- `Metrics Summary`
- `Observed Evaluation Summary`
- `Fixture Evaluation Summary`

## 5. Export the Observed Evaluation Set

Run the export entrypoint:

```powershell
.\.venv\Scripts\python.exe -m src.main_export_evaluation_set
```

Expected output:

- `tests\fixtures\newsnow\evaluation_set.observed.json`

## 6. One-Command Verification Helper

The repo includes a PowerShell helper script:

```powershell
.\scripts\run_newsnow_verification.ps1
```

Default behavior:

- install runtime and test dependencies
- run tests
- run report
- run export

Useful variants:

```powershell
.\scripts\run_newsnow_verification.ps1 -RunCrawl
.\scripts\run_newsnow_verification.ps1 -RunTests -RunReport
.\scripts\run_newsnow_verification.ps1 -RunExport
```

## 7. Verification Order

Recommended order for the first runtime validation:

1. install dependencies
2. run the full test suite
3. run a small crawl
4. generate the report
5. export observed evaluation cases
6. compare observed cases against fixture cases

## 8. Files to Inspect After a Run

- `data\crawler.db`
- `data\crawl_events.jsonl`
- `tests\fixtures\newsnow\evaluation_set.observed.json`

## 9. What Good Looks Like

- tests pass
- the crawl completes without fatal crash
- `article_saved` events appear in `crawl_events.jsonl`
- the report prints non-empty metrics
- the export command writes observed evaluation cases

## 10. Common Failure Points

- missing Python package dependencies
- invalid or stale virtual environment
- model/runtime dependency required by `crawl4ai`
- insufficient crawl log data for meaningful observed evaluation output

## Recommendation

Use this runbook together with:

- [newsnow-runtime-verification-checklist.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-runtime-verification-checklist.md)
- [newsnow-implementation-matrix.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-implementation-matrix.md)
