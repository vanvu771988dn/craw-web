# NewsNow Crawling Analysis and Implementation Guide

## Purpose

This document records:

- what is wrong with the current NewsNow crawler
- what must be changed
- why those changes are necessary
- which risks and trade-offs future developers must understand before modifying the code

This document should be treated as the implementation guide for the NewsNow adapter and the baseline design reference for similar aggregator sites.

## Scope

Primary list page:

- `https://www.newsnow.co.uk/h/Sport/Football?type=ln`

The same design assumptions may apply to other NewsNow sections and other aggregator-style sites.

## Executive Summary

NewsNow is not a normal article site.

It is an aggregator with this effective flow:

1. list page
2. tracker link
3. final publisher URL
4. final publisher article page

Because of that, the crawler must not be built as:

- click UI
- read DOM links
- open tracker in browser
- wait for redirect
- extract full page blindly

That approach is brittle and is the main reason the current crawler is unreliable.

The correct model for NewsNow is:

1. discover article entries from the NewsNow backend
2. resolve tracker links into final publisher URLs
3. capture content from final publisher pages
4. isolate the correct article container
5. validate extracted content before save
6. deduplicate at both URL and semantic levels

## What Was Verified

### 1. NewsNow list entries are tracker links

The list page exposes links like:

- `https://c.newsnow.co.uk/A/...`

These are not the final article URLs.

Current selector is valid for discovery:

- `a[href*='https://c.newsnow.co.uk/A/']`

### 2. Tracker HTML contains the final publisher URL

Tracker pages on `c.newsnow.co.uk` contain a JavaScript object like:

```js
var clickthroughConfig = {
  url: 'https://publisher.example/article',
  delay: 1000,
  manualRedirect: false
};
```

This means:

- the final URL can usually be extracted directly from tracker HTML
- browser redirect waiting is not the correct primary resolution method

Important:

- the value is inside `clickthroughConfig = { url: '...' }`
- do not assume the format is `clickthroughConfig.url = ...`

### 3. Final URLs resolve to many different domains

A live probe of 10 article links from the configured NewsNow page resolved to multiple publishers, including:

- `www.barcablaugranes.com`
- `www.si.com`
- `www.goal.com`
- `www.sportsmole.co.uk`
- `en.people.cn`
- `www.philadelphiaunion.com`
- `www.football-espana.net`
- `www.forbes.com`
- `www.dailymail.com`

Conclusion:

- final article pages are multi-domain
- final DOM structure is not stable across publishers
- one hardcoded selector strategy will not work

### 4. Final article pages vary significantly in structure

Observed behaviors across sampled final pages:

- some pages expose `<article>`
- some expose `<main>` and `<article>`
- some expose `<article>` but no `<main>`
- some expose neither reliable `<article>` nor `<main>`
- some pages have close title matches to the NewsNow title
- some pages rewrite or expand the title substantially

Conclusion:

- extraction must use title-guided selection and DOM heuristics
- extraction cannot rely on one CSS selector
- extraction cannot rely on exact title equality

### 5. Pagination is backend-driven

The list page "View more headlines" behavior triggers:

- `POST https://www.newsnow.co.uk/h/app/v1/articles`

Conclusion:

- UI clicking is only a surface over backend pagination
- backend pagination should be the primary pagination strategy

### 6. Current crawler processes only one link per loop

The current implementation in `src/core/crawler.py` contains a `break` inside the link-processing loop.

Impact:

- only one article is processed per pagination cycle
- throughput is very low
- coverage is poor
- batch semantics are broken

### 7. Current extraction flow does not use the title anchor

The current codebase already contains a title-guided extraction prompt, but the title is not actually passed through the real processing flow.

Impact:

- the extractor operates without a reliable anchor
- it is much more likely to capture unrelated page content

## Core Problems

### Problem 1. Wrong crawl abstraction

The crawler treats NewsNow as a UI-driven article site instead of an aggregator with a backend list and tracker resolution layer.

### Problem 2. Wrong extraction abstraction

The crawler treats the final publisher page as something the LLM can reliably parse from raw full-page HTML.

This is wrong because final pages contain:

- related articles
- newsletters
- sidebars
- ads
- author boxes
- comment modules
- recommendation widgets

### Problem 3. Missing article targeting

The crawler has the NewsNow list title available, but does not use it to constrain extraction against the final page.

### Problem 4. Weak dedup model

The current design is too dependent on raw link identity.

For NewsNow and similar aggregators, that is insufficient because:

- tracker URLs are not content identity
- final URLs may differ due to normalization issues
- multiple publishers may cover the same story

### Problem 5. Weak stop condition

Stopping because one known URL exists is too naive for a batch-oriented discovery source.

## Required Design

Use a 4-stage pipeline for NewsNow:

1. Discovery
2. Resolution
3. Capture
4. Post-processing and dedup

### Stage 1. Discovery

Primary strategy:

- call `POST /h/app/v1/articles`

Collect at least:

- `list_page_url`
- `tracker_url`
- `grid_title`
- `grid_source`
- `grid_time_text`
- `grid_position`
- access or paywall indicators if available
- batch ordering metadata

Why:

- this is the most stable representation of NewsNow article discovery
- it reduces UI coupling
- it aligns the crawler with the site's real pagination model

### Stage 2. Resolution

Primary strategy:

- fetch tracker HTML
- parse `clickthroughConfig.url`
- resolve `final_url`

Fallback:

- browser navigation on the tracker URL if parsing fails

Also persist:

- `tracker_article_id`
- `redirect_delay_ms`
- `manual_redirect`
- `tracker_og_title`
- `tracker_og_image`

Why:

- tracker parsing is more stable and more debuggable than redirect waiting

### Stage 3. Capture

Primary strategy:

- fetch or open `final_url`
- capture final page HTML
- isolate the most likely article container
- extract title and article body from that container
- validate quality before persistence

Why:

- full page HTML from publisher domains is too noisy
- the correct article container must be isolated before extraction

### Stage 4. Post-processing and dedup

Perform:

- URL normalization
- hard dedup
- semantic duplicate classification
- story clustering if required

Why:

- multiple publishers may write the same story
- same idea does not always mean same article

## Content Extraction Strategy

## Goal

Captured content must be the main article content related to the intended title.

It must not be:

- related articles
- sidebars
- recommendations
- navigation text
- ad copy
- comments
- newsletter modules
- unrelated long text blocks

## Required Extraction Model

Use a hybrid strategy:

1. title-guided candidate discovery
2. rule-based candidate scoring
3. cleaned candidate extraction
4. LLM refinement or fallback
5. strict validation before save

### Step 1. Pass the expected title through the pipeline

The NewsNow list title must be passed through:

- discovery result
- resolution stage
- capture stage
- extraction stage

Suggested parameter:

- `expected_title`

Why:

- on multi-domain publisher pages, the title is the strongest anchor for identifying the intended article

### Step 2. Find article candidates in the final DOM

Search for candidate containers using:

- `article`
- `main`
- `[role='main']`
- `.article-body`
- `.entry-content`
- `.post-content`
- `.story-body`
- `.article-content`
- other high-text containers

If no obvious semantic containers exist:

- score generic block elements heuristically

### Step 3. Score candidates

Each candidate should be scored using multiple signals:

- title similarity against `expected_title`
- number of paragraphs
- text length
- text density
- link density penalty
- noise keyword penalty
- location penalty if inside obvious non-article regions

Recommended principle:

- title similarity is the strongest signal
- longest text alone is not enough

### Step 4. Clean the selected candidate

Remove known noise before extraction:

- `script`
- `style`
- `nav`
- `footer`
- `aside`
- `form`
- `noscript`
- social/share blocks
- related or recommended blocks
- newsletter or subscription blocks
- comment blocks
- cookie or consent blocks
- obvious ad containers

Why:

- this reduces extraction noise
- this lowers LLM token waste
- this improves deterministic extraction quality

### Step 5. Extract from candidate HTML, not full page HTML

The extractor must work on:

- selected candidate HTML

It must not default to:

- raw full publisher page HTML

Why:

- full page extraction increases noise and hallucination risk
- candidate HTML makes the task narrower and more stable

### Step 6. Use LLM as refinement or fallback

The LLM should not be the first and only mechanism used against full page HTML.

Preferred role of the LLM:

- refine the title and body from already isolated article HTML
- act as fallback if rule-based extraction is incomplete

Why:

- this improves controllability
- this reduces the chance of unrelated content being returned
- this lowers latency and cost

### Step 7. Validate extracted output

Do not save extracted content unless it passes quality checks.

Recommended checks:

- title similarity passes threshold
- content length passes threshold
- paragraph count passes threshold
- text does not contain too many noise patterns
- text is not obviously off-topic relative to `expected_title`

Fallback behavior:

- try another candidate
- otherwise log a structured extraction failure
- do not save noisy content as success

## Semantic Dedup Strategy

News aggregation creates three different duplication categories:

1. exact duplicate
2. near duplicate
3. same story, different article

These must not be treated as the same thing.

### Exact duplicate

Examples:

- same canonical URL
- same normalized final URL
- almost identical content

Action:

- do not create a new article record

### Near duplicate

Examples:

- different publisher wording
- substantially same content
- rewritten syndication

Action:

- keep configurable
- either mark as `duplicate_of`
- or keep as a separate record with duplicate metadata

### Same story, different article

Examples:

- multiple publishers covering the same event
- similar idea
- different details, emphasis, or structure

Action:

- do not drop by default
- group into a `story_cluster_id` if the product needs story-level grouping

### Recommended dedup priority

Hard dedup:

1. `canonical_url`
2. normalized `final_url`
3. content fingerprint
4. tracker article ID
5. tracker URL

Semantic dedup or clustering:

- normalized title similarity
- entity overlap
- time or event overlap
- embedding similarity on title plus early body paragraphs

Important:

- do not treat every semantically similar article as a duplicate
- otherwise valid multi-source reporting will be lost

## Stop Condition Strategy

Do not stop because one URL already exists.

Use batch-aware stop logic such as:

- stop if a batch returns no new articles
- stop if duplicate ratio in a batch exceeds a threshold
- stop if the last N batches produced no new content
- optionally stop by article age threshold

Why:

- NewsNow is a batch discovery source
- one known link does not imply the rest of the batch is old

## Required Code Changes

### P0

- remove the single-link `break` behavior in `src/core/crawler.py`
- process full batches
- replace UI-first pagination with backend-driven discovery
- add `resolve_newsnow_tracker_url()`
- persist both `tracker_url` and `final_url`
- pass `expected_title` through the extraction pipeline
- add article candidate discovery and scoring
- extract from candidate HTML, not full page HTML
- validate extracted output before save
- replace single-URL stop condition with batch stop logic

### P1

- normalize URLs before dedup
- persist list, tracker, and final article metadata separately
- add retry boundaries for:
  - tracker resolution failure
  - final page timeout
  - extraction failure
  - AI fallback failure
- add structured extraction logs
- add semantic duplicate classification fields

### P2

- add bounded concurrency for final article capture
- add queue or state transitions:
  - discovered
  - resolved
  - captured
  - failed
- generalize this into strategy-based site adapters
- add story clustering if the product needs cross-source grouping

## Data and Schema Recommendations

Persist at least the following groups of fields.

### List metadata

- `list_page_url`
- `tracker_url`
- `grid_title`
- `grid_source`
- `grid_time_text`
- `grid_position`

### Tracker metadata

- `tracker_url`
- `tracker_article_id`
- `final_url`
- `redirect_delay_ms`
- `manual_redirect`
- `tracker_og_title`
- `tracker_og_image`

### Final article metadata

- `final_url`
- `canonical_url`
- `title`
- `author`
- `published_at`
- `updated_at`
- `source_site`
- `top_image_url`
- `main_content`

### Dedup or clustering metadata

- `normalized_title`
- `content_fingerprint`
- `duplicate_status`
- `duplicate_of`
- `story_cluster_id`
- `similarity_score`

## System Recommendations

### Weaknesses in the current approach

- strong coupling to UI structure
- no clean separation between discovery and capture
- no explicit tracker resolution stage
- extraction relies too heavily on full DOM plus AI
- retry boundaries are unclear
- stop logic is too naive

### Required improvements

- separate list ingestion from article capture
- track stage-specific success and failure
- make extraction quality observable
- preserve enough metadata to debug cross-domain failures

## Logging and Metrics

Log enough data so that extraction and dedup failures can be explained later.

Recommended structured fields:

- `tracker_url`
- `final_url`
- `final_domain`
- `expected_title`
- `candidate_count`
- `selected_candidate_score`
- `title_similarity`
- `content_length`
- `paragraph_count`
- `validation_passed`
- `duplicate_status`

Recommended metrics:

- discovered links per batch
- resolved final URL rate
- capture success rate
- extraction validation pass rate
- timeout rate
- hard dedup rate
- semantic duplicate rate
- new articles per run
- articles captured per minute
- false-stop incidents
- tracker resolution failure rate
- AI fallback rate

## Process Recommendations

### Immediate quick wins

- define a site-specific crawl strategy before implementation
- define extraction success criteria before coding
- document tracker resolution assumptions
- document pagination assumptions
- document stop-condition assumptions

### Short-term process

Create an onboarding checklist for aggregator sites:

- list selector
- backend pagination mechanism
- tracker mechanism
- final URL resolution method
- extraction anchor
- stop condition
- dedup key
- semantic clustering policy

### Medium-term process

Create crawler strategy types:

- direct-link site
- tracker-link site
- backend-pagination site
- multi-domain publisher site

### Long-term process

Refactor crawler into strategy modules:

- `DiscoveryStrategy`
- `PaginationStrategy`
- `LinkResolutionStrategy`
- `ContentExtractionStrategy`
- `DedupStrategy`

## Risks and Trade-Offs

Future developers must understand these before simplifying or refactoring the implementation.

### Risk 1. Reverting to UI-only pagination

What goes wrong:

- lower stability
- lower throughput
- higher DOM coupling
- more false failures when the button changes

Why the current recommended design avoids it:

- backend pagination matches the site's true article feed behavior

### Risk 2. Relying on redirect waiting instead of tracker parsing

What goes wrong:

- redirect timing is flaky
- browser timing differences create nondeterministic failures
- debugging becomes harder

Why tracker parsing is preferred:

- the final URL is explicitly embedded in tracker HTML

### Risk 3. Extracting from full page HTML

What goes wrong:

- unrelated content is mixed into article text
- LLM is more likely to pick the wrong block
- cost and latency increase

Why candidate isolation is required:

- publisher pages are noisy and structurally inconsistent

### Risk 4. Using exact title matching

What goes wrong:

- NewsNow titles may be truncated
- publisher titles may be rewritten or expanded
- good articles may be incorrectly rejected

Why fuzzy title matching is required:

- title anchor is still the strongest signal, but it is not exact

### Risk 5. Deduplicating all semantically similar articles

What goes wrong:

- valid multi-source reporting is lost
- the system collapses different articles into one record incorrectly

Why duplicate and story cluster must be separate concepts:

- same story is not always the same article

### Risk 6. Stopping on the first known URL

What goes wrong:

- the crawler may miss many new items in the same batch

Why batch stop logic is required:

- NewsNow discovery is batch-based

### Risk 7. Over-relying on LLM output without validation

What goes wrong:

- noisy content is persisted as success
- debugging becomes expensive
- bad data quietly accumulates

Why validation gates are required:

- extraction quality must be checked before persistence

### Risk 8. Overfitting to one publisher domain

What goes wrong:

- code works for one sampled site but breaks on others
- maintenance grows with each publisher-specific workaround

Why a generic heuristic-first design is preferred:

- final domains are heterogeneous

## Why the Code Must Be Written This Way

This design is not accidental.

It exists because NewsNow combines all of the following:

- backend discovery
- tracker indirection
- multi-domain final capture
- inconsistent publisher HTML
- high content noise on final pages
- potential semantic overlap across sources

A simpler crawler can appear to work in small tests, but it will fail in production for coverage, correctness, or maintainability reasons.

If a future developer wants to simplify the implementation, they must first prove that the simplification preserves:

- correct discovery
- stable final URL resolution
- correct main-content extraction
- low-noise persistence
- proper duplicate handling

## Final Recommendation

For NewsNow, the crawler should implement this flow:

1. call `POST /h/app/v1/articles`
2. collect tracker links and list metadata
3. resolve each tracker by parsing `clickthroughConfig.url`
4. fetch the resolved `final_url`
5. pass the NewsNow title through as `expected_title`
6. discover and score candidate article containers
7. clean the best candidate
8. extract title and main content from candidate HTML
9. validate the extraction result
10. deduplicate using hard keys first and semantic logic second
11. stop only by batch-aware rules

This is the most defensible balance of:

- correctness
- robustness
- extraction quality
- maintainability
- extensibility
