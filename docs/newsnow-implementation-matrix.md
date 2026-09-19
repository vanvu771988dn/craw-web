# NewsNow Implementation Matrix

## Summary

This matrix converts the backlog into a practical delivery view:

- `Done`: implemented in code and reflected in the current architecture
- `Partial`: core code exists, but production validation or real-data coverage is still incomplete
- `Todo`: not implemented

Current result:

- `Done`: 13 features
- `Partial`: 2 features
- `Todo`: 0 features

## Feature Matrix

| Feature | Status | Notes |
| --- | --- | --- |
| Feature 1: Backend-Driven NewsNow Discovery | Done | Backend batch discovery, metadata capture, ordering, UI fallback, and discovery logging are implemented. |
| Feature 2: Tracker Resolution | Done | HTML-first resolution, metadata persistence, normalization, retry, and browser fallback are implemented. |
| Feature 3: Full-Batch Processing and Batch Stop Logic | Done | Batch processing, counters, stop rules, and explicit stop reasons are implemented. |
| Feature 4: Metadata Pipeline | Done | Discovery, tracker, and final article metadata are persisted with traceability. |
| Feature 5: Title-Guided Extraction Pipeline | Done | `expected_title` is preserved across the pipeline and used in extraction and validation. |
| Feature 6: Article Candidate Discovery and Scoring | Done | Candidate discovery, scoring, ranking, and fallback candidate retry are implemented. |
| Feature 7: HTML Noise Removal and Candidate Cleaning | Done | Structural and content noise removal exists at candidate cleaning and extraction stages. |
| Feature 8: Main Content Extraction | Partial | Candidate-based extraction is implemented, but sample-based validation using real multi-domain NewsNow destinations is still incomplete. |
| Feature 9: Extraction Validation Gates | Done | Validation gates, rejection reasons, and alternate-candidate retry are implemented. |
| Feature 10: Hard Dedup | Done | Canonical/final URL, fingerprint, tracker identity, and normalized title dedup are implemented. |
| Feature 11: Semantic Duplicate Handling | Done | Duplicate states, persistence fields, heuristic semantic checks, and embedding-assisted baseline exist. |
| Feature 12: Retry and Failure Boundaries | Done | Stage-specific retry and failure classification exist, including targeted retry flow. |
| Feature 13: Logging, Metrics, and Debug Artifacts | Done | Structured logs, run metrics, debug artifacts, and metrics summarization are implemented. |
| Feature 14: Test Coverage and Evaluation Set | Partial | Regression harness, fixtures, export/report flows, and evaluation builder exist, but real observed sample coverage is still thin. |
| Feature 15: Strategy-Based Refactor | Done | NewsNow logic is separated behind adapter/strategy boundaries in the modular-monolith design. |

## What Partial Actually Means

### Feature 8

Implemented:

- candidate-based extraction
- rule-based pass before LLM fallback
- paragraph preservation
- validation gates

Still missing:

- stable validation against a broader set of real NewsNow -> publisher captures
- confidence that extraction quality holds across more publisher layouts seen in production

### Feature 14

Implemented:

- regression tests
- representative fixtures
- evaluation-set builder
- observed export flow
- reporting flow

Still missing:

- a larger maintained observed sample set from real crawl runs
- enough `article_saved`-rich events to claim production-like regression depth

## Practical Interpretation

If the question is "Is the NewsNow pipeline implemented?", the honest answer is:

- yes for core code and architecture
- not yet fully proven by real-data validation depth

If the question is "What should the team do next?", the answer is:

1. run more real crawls
2. export observed evaluation cases
3. curate stable real cases into the maintained evaluation set
4. use that set to close Feature 8 and Feature 14 completely

## Related Docs

- [newsnow-status.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-status.md)
- [newsnow-implementation-tasks.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-implementation-tasks.md)
- [newsnow-evaluation-set.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-evaluation-set.md)
- [newsnow-success-metrics.md](/abs/path/c:/Users/Hi/Desktop/MyProject/CrawWeb/docs/newsnow-success-metrics.md)
