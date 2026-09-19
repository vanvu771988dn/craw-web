from difflib import SequenceMatcher
import re
from bs4 import BeautifulSoup, Tag

NOISE_PATTERN = re.compile(
    r"(related|recommended|newsletter|subscribe|comment|cookie|consent|share|social|advert|promo|sidebar)",
    re.I,
)
STRUCTURAL_SELECTORS = (
    "article",
    "main",
    "[role='main']",
    ".article-body",
    ".article-content",
    ".entry-content",
    ".post-content",
    ".story-body",
    ".story-content",
    ".content__article-body",
)


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return " ".join(value.split()).strip().lower()


def compute_text_similarity(left: str | None, right: str | None) -> float:
    normalized_left = normalize_text(left)
    normalized_right = normalize_text(right)
    if not normalized_left or not normalized_right:
        return 0.0

    if normalized_left in normalized_right or normalized_right in normalized_left:
        return 1.0

    return SequenceMatcher(None, normalized_left, normalized_right).ratio()


def _collect_heading_text(node: Tag) -> str | None:
    heading = node.find(["h1", "h2", "h3"])
    if not heading:
        return None
    return " ".join(heading.get_text(" ", strip=True).split())


def _score_candidate(node: Tag, expected_title: str | None) -> float:
    text = " ".join(node.get_text(" ", strip=True).split())
    text_length = len(text)
    if text_length == 0:
        return float("-inf")

    paragraph_count = len(node.find_all("p"))
    heading_text = _collect_heading_text(node)
    title_similarity = compute_text_similarity(expected_title, heading_text)
    link_text_length = sum(len(" ".join(anchor.get_text(" ", strip=True).split())) for anchor in node.find_all("a"))
    link_density = link_text_length / max(text_length, 1)
    noise_hits = len(NOISE_PATTERN.findall(text))

    score = 0.0
    score += title_similarity * 80
    score += min(paragraph_count, 20) * 2
    score += min(text_length / 800, 15)
    score -= link_density * 30
    score -= noise_hits * 2

    if node.name == "article":
        score += 6
    if node.name == "main":
        score += 3

    return score


def find_article_candidates(html: str) -> list[Tag]:
    """Finds candidate article containers from a final publisher page."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[Tag] = []
    seen_ids: set[int] = set()

    for selector in STRUCTURAL_SELECTORS:
        for node in soup.select(selector):
            if isinstance(node, Tag) and id(node) not in seen_ids:
                candidates.append(node)
                seen_ids.add(id(node))

    generic_pattern = re.compile(r"(article|content|story|post|entry|body|main)", re.I)
    for node in soup.find_all(["div", "section"]):
        attributes = " ".join(
            str(value)
            for key, value in node.attrs.items()
            if key in {"class", "id"}
        )
        if generic_pattern.search(attributes) and id(node) not in seen_ids:
            candidates.append(node)
            seen_ids.add(id(node))

    return candidates


def score_article_candidate(node: Tag, expected_title: str | None) -> float:
    """Public scoring wrapper for unit tests and pipeline integration."""
    return _score_candidate(node, expected_title)


def clean_article_candidate(node: Tag) -> str:
    """Removes obvious noisy descendants from a selected candidate while preserving structure."""
    candidate_soup = BeautifulSoup(str(node), "html.parser")
    for noisy_selector in (
        "[class*='related']",
        "[class*='recommended']",
        "[class*='newsletter']",
        "[class*='subscribe']",
        "[class*='comment']",
        "[class*='cookie']",
        "[class*='consent']",
        "[class*='share']",
        "[class*='social']",
        "[class*='advert']",
        "[id*='related']",
        "[id*='recommended']",
        "[id*='comment']",
    ):
        for match in candidate_soup.select(noisy_selector):
            match.decompose()

    return str(candidate_soup)


def select_best_candidate(candidates: list[Tag], expected_title: str | None) -> Tag | None:
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: _score_candidate(candidate, expected_title))


def rank_article_candidates(candidates: list[Tag], expected_title: str | None) -> list[Tag]:
    """Returns candidates ordered by descending score."""
    return sorted(candidates, key=lambda candidate: _score_candidate(candidate, expected_title), reverse=True)


def select_article_candidate_html(html: str, expected_title: str | None = None) -> str:
    """Returns the best candidate HTML block to use for extraction."""
    candidates = find_article_candidates(html)
    if not candidates:
        return html

    best_candidate = select_best_candidate(candidates, expected_title)
    if not best_candidate:
        return html

    return clean_article_candidate(best_candidate)
