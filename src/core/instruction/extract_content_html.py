# src/core/instruction/extract_content_html.py

EXTRACTION_INSTRUCTION = """Your goal is to act as a highly accurate content extractor for news articles.
From the provided HTML, you must extract ONLY the following two elements:
1.  The main title of the article.
2.  The full, main content of the article text.

**Crucial Instructions:**
-   **Focus exclusively on the main article.** Ignore everything else.
-   **ABSOLUTELY EXCLUDE:**
    -   Advertisements, banners, and promotional content.
    -   Navigation bars, headers, footers, and sidebars.
    -   "Related articles," "more from this site," or "you may also like" sections.
    -   Author bios, comment sections, and social media sharing buttons.
    -   Cookie consent banners or subscription pop-ups.
    -   Any script, style, or interactive elements.
-   **Heuristics for Identifying Main Content:**
    -   The main content is typically the **longest continuous block of text** on the page.
    -   Analyze the text density. The main article body will have a high concentration of text within `<p>` tags.
    -   Avoid sections with numerous images (`<img>`), short text fragments, or a high density of links (`<a>`).
-   **Preserve Original Formatting:**
    -   Maintain all original paragraph breaks, headings (like H1, H2), and other text formatting from the main content.
    -   Do not summarize, rewrite, or alter the text in any way.
-   **Output:**
    -   Return the extracted text exactly as it appears on the page, with original line breaks and structure.

If the HTML does not contain a discernible article, return an empty response.
"""

EXTRACTION_INSTRUCTION_WITH_TITLE = """Your primary goal is to act as a highly accurate content locator and extractor for a specific news article.
You have been given the title of an article from a list page. You must use this title to locate the correct article container within the provided HTML.

**Title to find:**
"{title}"

**Your task:**
1.  Search the HTML to find the main article container where the heading is a close match to the title provided above.
2.  From that specific container, and only that container, extract the full, main content of the article text.

**Crucial Instructions:**
-   **Focus exclusively on the article identified by the title.** Ignore everything else on the page.
-   **ABSOLUTELY EXCLUDE** all other content, including ads, navigation, sidebars, footers, related articles, author bios, and comments.
-   **Preserve Original Formatting:** Maintain all original paragraph breaks and headings. Do not summarize or rewrite the text.

If you cannot find an article with a matching title, return an empty response.
"""
