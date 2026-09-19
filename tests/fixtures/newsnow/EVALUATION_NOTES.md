# NewsNow Evaluation Notes

This fixture set is a local regression harness for the NewsNow pipeline.

Current scope:

- tracker resolution parsing
- truncated-title matching
- rewritten-title matching
- candidate scoring and selection
- extraction validation failure cases
- hard dedup priority checks

Important limitation:

- these are representative local fixtures, not live-captured production samples
- they are designed to lock in parser and pipeline behavior in CI-friendly tests
- a future upgrade should replace or supplement them with real multi-domain captured pages and resolved tracker links

Suggested future expansion:

1. add captured tracker HTML from multiple publishers
2. add final-page HTML from at least 5-10 distinct publisher DOM styles
3. record expected extraction summaries and validation outcomes
4. compare extraction quality over time using stable evaluation notes
