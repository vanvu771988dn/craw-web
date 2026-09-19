# src/core/processing.py
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler
from src.core.errors import CrawlStageError
from src.database.models import ScrapedData
from src.core.article_candidates import (
    clean_article_candidate,
    compute_text_similarity,
    find_article_candidates,
    rank_article_candidates,
)
from src.utils.ai_utils import extract_content_with_ai
from src.utils.content_utils import compute_content_fingerprint, normalize_text_for_storage
from src.utils.datetime_util import parse_date
from src.utils.html_utils import clean_html_for_extraction
from src.utils.file_logger import log_crawl_results, log_debug_artifact, log_structured_event

NOISE_TEXT_PATTERNS = (
    "related articles",
    "recommended",
    "most read",
    "sign up",
    "subscribe",
    "newsletter",
    "advertisement",
    "cookie policy",
)


def _extract_rule_based_content(candidate_html: str, expected_title: str | None) -> ScrapedData | None:
    soup = BeautifulSoup(candidate_html, "html.parser")
    heading = soup.find(["h1", "h2", "h3"])
    paragraphs = [
        " ".join(paragraph.get_text(" ", strip=True).split())
        for paragraph in soup.find_all("p")
    ]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    if not paragraphs:
        return None

    title = " ".join(heading.get_text(" ", strip=True).split()) if heading else expected_title
    main_content = "\n\n".join(paragraphs)
    return ScrapedData(title=title, main_content=main_content)


def _validate_extraction_result(scraped_data: ScrapedData, expected_title: str | None) -> None:
    main_content = (scraped_data.main_content or "").strip()
    if len(main_content) < 200:
        raise ValueError("Extracted main content is too short to be considered a valid article.")

    paragraph_count = sum(1 for line in main_content.splitlines() if line.strip())
    if paragraph_count < 2:
        raise ValueError("Extracted main content does not contain enough paragraph structure.")

    normalized_main_content = normalize_text_for_storage(main_content)
    for noise_pattern in NOISE_TEXT_PATTERNS:
        if noise_pattern in normalized_main_content:
            raise ValueError(f"Extracted main content contains a noisy pattern: '{noise_pattern}'.")

    if expected_title and scraped_data.title:
        similarity = compute_text_similarity(expected_title, scraped_data.title)
        if similarity < 0.45:
            raise ValueError(
                f"Extracted title does not match expected title closely enough (similarity={similarity:.2f})."
            )


def _extract_meta_content(soup: BeautifulSoup, *selectors: tuple[str, str]) -> str | None:
    for attr_name, attr_value in selectors:
        node = soup.find("meta", attrs={attr_name: attr_value})
        if node and node.get("content"):
            return " ".join(node["content"].split()).strip() or None
    return None


def _extract_first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            text = " ".join(node.get_text(" ", strip=True).split())
            if text:
                return text
    return None


def enrich_scraped_data_from_html(
    scraped_data: ScrapedData,
    final_html: str,
    final_url: str,
    expected_title: str | None = None,
) -> ScrapedData:
    soup = BeautifulSoup(final_html, "html.parser")

    canonical_href = None
    canonical_link = soup.find("link", rel=lambda value: value and "canonical" in str(value).lower())
    if canonical_link and canonical_link.get("href"):
        canonical_href = urljoin(final_url, canonical_link.get("href"))

    scraped_data.canonical_url = canonical_href or scraped_data.canonical_url or final_url
    scraped_data.title = (
        scraped_data.title
        or _extract_meta_content(soup, ("property", "og:title"), ("name", "twitter:title"))
        or _extract_first_text(soup, ["h1", "main h1", "article h1"])
        or expected_title
    )
    scraped_data.author = scraped_data.author or _extract_meta_content(
        soup,
        ("name", "author"),
        ("property", "article:author"),
    )
    published_raw = _extract_meta_content(
        soup,
        ("property", "article:published_time"),
        ("name", "pubdate"),
        ("name", "date"),
    )
    updated_raw = _extract_meta_content(
        soup,
        ("property", "article:modified_time"),
        ("name", "lastmod"),
        ("name", "updated_time"),
    )
    if not published_raw:
        time_node = soup.find("time")
        if time_node:
            published_raw = time_node.get("datetime") or time_node.get_text(" ", strip=True)
    if not scraped_data.published_at and published_raw:
        scraped_data.published_at = parse_date(published_raw)
    if not scraped_data.updated_at and updated_raw:
        scraped_data.updated_at = parse_date(updated_raw)
    scraped_data.source_site = scraped_data.source_site or _extract_meta_content(soup, ("property", "og:site_name"))
    if not scraped_data.source_site:
        scraped_data.source_site = urlparse(final_url).netloc.lower()
    scraped_data.top_image_url = scraped_data.top_image_url or _extract_meta_content(
        soup,
        ("property", "og:image"),
        ("name", "twitter:image"),
    )
    if scraped_data.top_image_url:
        scraped_data.top_image_url = urljoin(final_url, scraped_data.top_image_url)

    scraped_data.canonical_url = urljoin(final_url, scraped_data.canonical_url) if scraped_data.canonical_url else None
    scraped_data.normalized_title = normalize_text_for_storage(scraped_data.title)
    scraped_data.content_fingerprint = compute_content_fingerprint(
        scraped_data.title,
        scraped_data.main_content,
    )
    return scraped_data


async def process_content(
    crawler: AsyncWebCrawler, 
    final_html: str, 
    url: str, 
    config: dict,
    expected_title: str | None = None,
    tracker_url: str | None = None,
    tracker_article_id: str | None = None,
) -> ScrapedData:
    """Cleans HTML, isolates article content, and returns validated scraped data."""
    if not final_html:
        raise Exception("Failed to retrieve final HTML after navigation and wait.")

    ai_extraction_attempts = config.get("crawler", {}).get("retry_attempts", {}).get("extraction", 2)
    candidates = rank_article_candidates(find_article_candidates(final_html), expected_title)
    log_structured_event(
        "extraction",
        "candidate_ranked",
        final_url=url,
        expected_title=expected_title,
        candidate_count=len(candidates),
    )
    candidate_htmls = [clean_html_for_extraction(clean_article_candidate(candidate)) for candidate in candidates[:3]]
    if not candidate_htmls:
        candidate_htmls = [clean_html_for_extraction(final_html)]

    extraction_errors: list[str] = []
    for index, candidate_html in enumerate(candidate_htmls, start=1):
        try:
            extracted_data = _extract_rule_based_content(candidate_html, expected_title)
            if extracted_data is None:
                ai_error: Exception | None = None
                scraped_data_list = None
                for attempt in range(1, ai_extraction_attempts + 1):
                    try:
                        scraped_data_list = await extract_content_with_ai(
                            crawler,
                            candidate_html,
                            config,
                            title_to_find=expected_title,
                        )
                        if not scraped_data_list:
                            raise ValueError("AI extraction returned no data.")
                        break
                    except Exception as exc:
                        ai_error = exc
                        log_structured_event(
                            "extraction",
                            "ai_extraction_retry",
                            final_url=url,
                            tracker_url=tracker_url,
                            tracker_article_id=tracker_article_id,
                            expected_title=expected_title,
                            candidate_index=index,
                            attempt=attempt,
                            attempts=ai_extraction_attempts,
                            error=str(exc),
                        )
                if not scraped_data_list:
                    if ai_error:
                        raise ai_error
                    raise ValueError("AI extraction returned no data.")
                extracted_data = scraped_data_list[0]

            extracted_data.url = url
            extracted_data.final_url = url
            extracted_data.tracker_url = tracker_url
            extracted_data.tracker_article_id = tracker_article_id
            extracted_data = enrich_scraped_data_from_html(
                extracted_data,
                final_html,
                url,
                expected_title=expected_title,
            )

            title_similarity = compute_text_similarity(expected_title, extracted_data.title) if expected_title and extracted_data.title else None
            _validate_extraction_result(extracted_data, expected_title)
            log_structured_event(
                "extraction",
                "candidate_accepted",
                final_url=url,
                tracker_url=tracker_url,
                tracker_article_id=tracker_article_id,
                expected_title=expected_title,
                candidate_index=index,
                canonical_url=extracted_data.canonical_url,
                source_site=extracted_data.source_site,
                top_image_url=extracted_data.top_image_url,
                normalized_title=extracted_data.normalized_title,
                title_similarity=title_similarity,
                content_length=len(extracted_data.main_content or ""),
                paragraph_count=sum(1 for line in extracted_data.main_content.splitlines() if line.strip()),
            )
            print(f"Final scraped data accepted from candidate #{index}: {extracted_data}")
            log_crawl_results(final_html, extracted_data)
            return extracted_data
        except Exception as exc:
            artifact_path = log_debug_artifact(f"candidate_failure_{index}", candidate_html)
            log_structured_event(
                "extraction",
                "candidate_rejected",
                final_url=url,
                tracker_url=tracker_url,
                tracker_article_id=tracker_article_id,
                expected_title=expected_title,
                candidate_index=index,
                error=str(exc),
                artifact_path=artifact_path,
            )
            extraction_errors.append(f"candidate_{index}: {exc}")

    raise CrawlStageError(
        stage="extraction",
        code="EXTRACTION_VALIDATION_FAILED",
        message="Extraction validation failed for all candidate articles.",
        context={
            "final_url": url,
            "tracker_url": tracker_url,
            "tracker_article_id": tracker_article_id,
            "expected_title": expected_title,
            "errors": extraction_errors,
        },
    )
