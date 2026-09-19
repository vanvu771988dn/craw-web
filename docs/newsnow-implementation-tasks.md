# NewsNow Implementation Tasks

## Purpose

This file turns the analysis in `docs/newsnow-crawling-analysis.md` into an implementation backlog.

Usage:

- mark a task as `[done]` when implementation is complete
- keep unfinished work as `[todo]`
- add completion notes inline when useful
- do not remove completed items unless they were created by mistake

Status legend:

- `[todo]` not started
- `[doing]` in progress
- `[done]` completed
- `[blocked]` waiting on decision or dependency

## Feature 1: Backend-Driven NewsNow Discovery

Goal:
Replace UI-first list crawling with backend-driven discovery from NewsNow article batches.

Tasks:

- [done] Analyze the `POST /h/app/v1/articles` request and response shape from the target NewsNow page.
- [done] Define a discovery payload builder for NewsNow pagination requests.
- [done] Implement a NewsNow discovery client that fetches article batches without relying on the `View more headlines` button.
- [done] Parse batch responses into structured discovery records.
- [done] Capture list metadata for each discovered item:
  - `list_page_url`
  - `tracker_url`
  - `grid_title`
  - `grid_source`
  - `grid_time_text`
  - `grid_position`
- [done] Add batch ordering metadata so crawl progression can be debugged later.
- [done] Keep UI click pagination only as fallback, not as the primary strategy.
- [done] Add logging for discovery batch size, new items, duplicate items, and empty batches.

Definition of done:

- crawler can fetch multiple NewsNow article batches without pressing the UI button
- each discovered item contains the expected list metadata
- discovery logs show batch-level progress clearly

## Feature 2: Tracker Resolution

Goal:
Resolve NewsNow tracker links into final publisher URLs reliably.

Tasks:

- [done] Implement `resolve_newsnow_tracker_url()` using tracker HTML parsing.
- [done] Parse `clickthroughConfig.url` from tracker HTML.
- [done] Parse and persist tracker metadata:
  - `tracker_article_id`
  - `redirect_delay_ms`
  - `manual_redirect`
  - `tracker_og_title`
  - `tracker_og_image`
- [done] Normalize resolved `final_url` before persistence and dedup checks.
- [done] Add fallback browser-based tracker resolution only when HTML parsing fails.
- [done] Add retry logic for transient tracker resolution failures.
- [done] Add structured logs for resolution success, failure, and fallback usage.

Definition of done:

- most tracker links resolve without waiting for browser redirect
- tracker metadata is persisted and debuggable
- failures are visible by reason, not hidden inside generic crawl errors

## Feature 3: Full-Batch Processing and Batch Stop Logic

Goal:
Fix the current single-link processing bug and move stop logic to batch semantics.

Tasks:

- [done] Remove the `break` in `src/core/crawler.py` that stops processing after one link.
- [done] Ensure the crawler processes every item in a discovered batch.
- [done] Replace the current stop rule of "stop on first existing URL".
- [done] Implement batch-aware stop conditions:
  - no new articles in batch
  - duplicate ratio above threshold
  - last N batches produced no new content
  - optional age threshold
- [done] Add counters for processed, saved, duplicate, failed, and skipped items per batch.
- [done] Log the exact reason why a crawl stops.

Definition of done:

- crawler processes full batches instead of one link per loop
- crawl termination follows batch outcome rather than single-link outcome
- stop reasons are explicit and reproducible

## Feature 4: Metadata Pipeline

Goal:
Preserve enough metadata across list, tracker, and final article stages.

Tasks:

- [done] Define a discovery-stage data model for NewsNow list items.
- [done] Define a tracker-resolution data model.
- [done] Define a final-article capture data model.
- [done] Extend persistence to store both `tracker_url` and `final_url`.
- [done] Persist final article metadata:
  - `canonical_url`
  - `title`
  - `author`
  - `published_at`
  - `updated_at`
  - `source_site`
  - `top_image_url`
  - `main_content`
- [done] Ensure each record keeps enough metadata to trace back to its discovery source.

Definition of done:

- every saved article can be traced from list discovery to tracker to final publisher page
- metadata is sufficient for debugging extraction and dedup later

## Feature 5: Title-Guided Extraction Pipeline

Goal:
Extract the correct article content from multi-domain publisher pages using the NewsNow title as anchor.

Tasks:

- [done] Pass `grid_title` through the pipeline as `expected_title`.
- [done] Update `_process_links()` to preserve title information from discovery.
- [done] Update `_navigate_and_extract()` to accept `expected_title`.
- [done] Update `process_content()` to pass `expected_title` into extraction.
- [done] Update `extract_content_with_ai()` to actually use the title-guided prompt path.
- [done] Add tests for truncated NewsNow titles vs expanded publisher titles.
- [done] Add fuzzy title matching instead of exact title matching.

Definition of done:

- extraction is anchored to the intended NewsNow title
- the title-guided prompt is actually used in the live code path
- title rewrite and title truncation cases are handled reasonably

## Feature 6: Article Candidate Discovery and Scoring

Goal:
Find the most likely main article container before extracting text.

Tasks:

- [done] Implement `find_article_candidates(final_html)`.
- [done] Include semantic candidates such as:
  - `article`
  - `main`
  - `[role='main']`
  - `.article-body`
  - `.entry-content`
  - `.post-content`
  - `.story-body`
- [done] Implement heuristic candidate generation for pages without reliable semantic containers.
- [done] Implement `score_article_candidate(node, expected_title)`.
- [done] Score candidates using:
  - title similarity
  - paragraph count
  - text length
  - text density
  - link density penalty
  - noise keyword penalty
- [done] Implement `select_best_candidate(candidates)`.
- [done] Add fallback to candidate #2 or #3 if the best candidate fails validation.

Definition of done:

- crawler can identify a best-effort article container on multiple publisher domains
- longest text block alone is no longer the extraction strategy

## Feature 7: HTML Noise Removal and Candidate Cleaning

Goal:
Reduce extraction noise before rule-based parsing or AI extraction.

Tasks:

- [done] Extend HTML cleaning beyond `script` and `style`.
- [done] Remove structural noise:
  - `nav`
  - `footer`
  - `aside`
  - `form`
  - `noscript`
- [done] Remove content noise blocks where detectable:
  - social/share modules
  - related/recommended articles
  - newsletter/subscribe prompts
  - comment sections
  - cookie/consent overlays
  - ad containers
- [done] Implement `clean_article_candidate(node)`.
- [done] Ensure cleaned HTML preserves article structure and paragraph boundaries.

Definition of done:

- extracted candidate HTML is materially smaller and cleaner than full page HTML
- paragraph structure is preserved while noisy modules are removed

## Feature 8: Main Content Extraction

Goal:
Extract title and main article body from the selected candidate, not from the whole page.

Tasks:

- [done] Change extraction input from full page HTML to selected candidate HTML.
- [done] Add a rule-based extraction pass for article text before LLM fallback.
- [done] Use the LLM as refinement or fallback, not the first blind extractor on full DOM.
- [done] Preserve original paragraph breaks and heading structure in extracted content.
- [done] Ensure unrelated blocks are not merged into `main_content`.
- [doing] Add sample-based validation using real multi-domain NewsNow destinations.

Definition of done:

- `main_content` comes from the intended article container
- extraction is less noisy and more stable across publishers

## Feature 9: Extraction Validation Gates

Goal:
Prevent low-quality or unrelated content from being saved as successful extraction.

Tasks:

- [done] Implement title similarity validation.
- [done] Implement content-length threshold validation.
- [done] Implement paragraph-count threshold validation.
- [done] Implement noise-pattern detection for obvious bad extractions.
- [done] Reject content that is clearly off-topic relative to `expected_title`.
- [done] Retry extraction with alternate candidates when validation fails.
- [done] Log structured extraction failure reasons when validation ultimately fails.

Definition of done:

- noisy or wrong article content is rejected instead of silently saved
- extraction failures are observable and categorized

## Feature 10: Hard Dedup

Goal:
Prevent duplicate saves for the same article identity.

Tasks:

- [done] Normalize URLs before duplicate checks.
- [done] Implement hard dedup priority:
  - `canonical_url`
  - normalized `final_url`
  - content fingerprint
  - tracker article ID
  - tracker URL
- [done] Add normalized title storage.
- [done] Add content fingerprint generation.
- [done] Update persistence and queries to support the new dedup keys.

Definition of done:

- the crawler does not resave the same article under slightly different URL forms
- dedup decisions are based on content identity, not just tracker link identity

## Feature 11: Semantic Duplicate Handling

Goal:
Distinguish between exact duplicate, near duplicate, and same-story articles.

Tasks:

- [done] Define duplicate status states:
  - `exact_duplicate`
  - `near_duplicate`
  - `same_story`
  - `unique`
- [done] Define persistence fields:
  - `duplicate_status`
  - `duplicate_of`
  - `story_cluster_id`
  - `similarity_score`
- [done] Implement normalized title similarity checks.
- [done] Implement entity overlap checks.
- [done] Implement time-window candidate filtering for semantic comparison.
- [done] Design an embedding-based similarity stage for later rollout.
- [done] Decide product policy for whether near duplicates are dropped, linked, or kept.

Definition of done:

- the system no longer treats all semantically similar articles as the same thing
- same-story grouping can exist without deleting valid multi-source coverage

## Feature 12: Retry and Failure Boundaries

Goal:
Make failures debuggable and stage-specific rather than generic.

Tasks:

- [done] Separate retry logic for:
  - discovery failure
  - tracker resolution failure
  - final page fetch failure
  - extraction failure
  - validation failure
- [done] Add failure reason codes for each stage.
- [done] Ensure failed items can be retried without reprocessing the whole crawl.
- [done] Persist enough context with each failure to support later debugging.

Definition of done:

- failures are classified by stage
- retries are targeted instead of blind reruns

## Feature 13: Logging, Metrics, and Debug Artifacts

Goal:
Make the NewsNow pipeline observable.

Tasks:

- [done] Add structured logs for:
  - discovery
  - tracker resolution
  - capture
  - extraction
  - validation
  - dedup
- [done] Log fields such as:
  - `tracker_url`
  - `final_url`
  - `final_domain`
  - `expected_title`
  - `candidate_count`
  - `selected_candidate_score`
  - `title_similarity`
  - `content_length`
  - `paragraph_count`
  - `duplicate_status`
- [done] Add run-level counters for throughput and failure rate.
- [done] Save raw HTML and candidate HTML debug artifacts for failed extractions when needed.
- [done] Define success metrics for future regression tracking.

Definition of done:

- the team can explain why a crawl succeeded or failed
- extraction quality and crawl throughput can be measured over time

## Feature 14: Test Coverage and Evaluation Set

Goal:
Protect the implementation against regressions across multiple publisher domains.

Tasks:

- [doing] Build a sample set of real NewsNow tracker links and resolved final URLs.
  - local fixture set exists
  - observed-log builder exists
  - export flow exists
  - report flow exists
  - production-like observed sample data is still incomplete
- [done] Include examples from multiple publishers with different DOM structures.
- [done] Add tests for:
  - tracker resolution
  - title-guided extraction
  - candidate scoring
  - validation gates
  - hard dedup
- [done] Add fixtures for truncated-title and rewritten-title scenarios.
- [done] Define expected outputs or evaluation notes for the sample set.

Definition of done:

- the NewsNow pipeline can be regression-tested against realistic multi-domain cases

## Feature 15: Strategy-Based Refactor

Goal:
Prepare the crawler for reuse across similar aggregator sites.

Tasks:

- [done] Separate NewsNow-specific logic from generic crawler flow.
- [done] Define strategy boundaries for:
  - `DiscoveryStrategy`
  - `PaginationStrategy`
  - `LinkResolutionStrategy`
  - `ContentExtractionStrategy`
  - `DedupStrategy`
- [done] Move NewsNow behavior behind a site adapter or strategy implementation.
- [done] Ensure future direct-link sites are not forced into the NewsNow path.

Definition of done:

- NewsNow-specific logic is isolated
- the crawler can support other site types without accumulating special-case code in one file

## Risks to Remember During Implementation

These are not tasks, but they must stay visible while implementing.

- [todo] Do not revert to UI-only pagination just because it is easier to demo.
- [todo] Do not depend on browser redirect timing when tracker HTML parsing is available.
- [todo] Do not extract from full final-page HTML by default.
- [todo] Do not use exact title matching as the only title rule.
- [todo] Do not collapse all semantically similar articles into duplicates.
- [todo] Do not stop a crawl on the first known URL.
- [todo] Do not save noisy extraction output as success.
- [todo] Do not overfit the extractor to one publisher domain.

## Suggested Implementation Order

Recommended sequence:

1. Feature 2: Tracker Resolution
2. Feature 3: Full-Batch Processing and Batch Stop Logic
3. Feature 5: Title-Guided Extraction Pipeline
4. Feature 6: Article Candidate Discovery and Scoring
5. Feature 7: HTML Noise Removal and Candidate Cleaning
6. Feature 8: Main Content Extraction
7. Feature 9: Extraction Validation Gates
8. Feature 10: Hard Dedup
9. Feature 13: Logging, Metrics, and Debug Artifacts
10. Feature 1: Backend-Driven NewsNow Discovery
11. Feature 12: Retry and Failure Boundaries
12. Feature 14: Test Coverage and Evaluation Set
13. Feature 11: Semantic Duplicate Handling
14. Feature 4: Metadata Pipeline
15. Feature 15: Strategy-Based Refactor

Notes:

- this order prioritizes correctness first, then observability, then extensibility
- backend discovery is architecturally important, but extraction correctness should be stabilized early as well
