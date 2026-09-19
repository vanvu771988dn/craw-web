# Memory

This file logs the work done, challenges, and solutions for the project.

## 2024-08-01

-   **Work Done:**
    -   Refactored the web crawler to correctly handle three complex redirect scenarios: delayed, direct, and interactive.
    -   Significantly improved the AI content extraction prompt to focus exclusively on article titles and main content, while aggressively filtering out noise like ads, banners, and related articles.
    -   Simplified the `ScrapedData` model to align with the new, more precise extraction strategy, removing unnecessary fields.
    -   Removed dead code related to the old content simplification logic, cleaning up the codebase.
-   **Challenges:**
    -   The crawler was not waiting for client-side redirects, leading to the extraction of content from intermediate pages instead of the final destination.
    -   The initial AI extraction prompt was too general, resulting in noisy output that included ads, cookie banners, and other irrelevant content.
-   **Solutions:**
    -   Modified the crawler's navigation logic to wait for `networkidle`, ensuring that all client-side rendering and redirects complete before content extraction begins.
    -   Implemented logic to detect and click interactive redirect buttons, using a selector from the configuration file.
    -   Crafted a highly explicit and detailed extraction prompt that instructs the AI to ignore common noise elements and preserve the original formatting of the article content.
