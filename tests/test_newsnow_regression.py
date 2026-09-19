import json
from pathlib import Path

from bs4 import BeautifulSoup

from src.core.article_candidates import (
    compute_text_similarity,
    find_article_candidates,
    score_article_candidate,
    select_best_candidate,
)
from src.core.newsnow import parse_tracker_html
from src.core.processing import _extract_rule_based_content, _validate_extraction_result


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "newsnow"


def _read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


def test_evaluation_set_contains_multiple_cases():
    evaluation_set = json.loads(_read_fixture("evaluation_set.json"))

    assert len(evaluation_set) >= 3
    assert {item["case_id"] for item in evaluation_set} >= {
        "tracker-resolution-basic",
        "truncated-title-article",
        "rewritten-title-article",
    }


def test_tracker_resolution_fixture_matches_expected_output():
    tracker_html = """
    <!DOCTYPE html>
    <html>
      <head>
        <meta property="og:title" content="Sample Tracker Title" />
        <meta property="og:image" content="https://example.com/image.jpg" />
        <script>
          var clickthroughConfig = {
            url: 'https://www.example.com/story?id=123#fragment',
            delay: 1000,
            manualRedirect: false
          };
        </script>
      </head>
    </html>
    """
    result = parse_tracker_html("https://c.newsnow.co.uk/A/1313187102?-833:12", tracker_html)

    assert result.final_url == "https://www.example.com/story?id=123"
    assert result.redirect_delay_ms == 1000
    assert result.manual_redirect is False


def test_candidate_scoring_prefers_expected_article_fixture():
    html = _read_fixture("truncated_title_case.html")
    expected_title = "Real Madrid vs. Real Oviedo: Preview, Predictions and Lineups"

    candidates = find_article_candidates(html)
    best = select_best_candidate(candidates, expected_title)

    assert best is not None
    assert best.name in {"article", "main", "section", "div"}
    assert "Real Madrid vs. Real Oviedo" in best.get_text(" ", strip=True)

    scored = [(score_article_candidate(candidate, expected_title), candidate) for candidate in candidates]
    scored.sort(key=lambda item: item[0], reverse=True)
    assert scored[0][0] >= scored[-1][0]


def test_truncated_title_fixture_passes_similarity_and_validation():
    html = _read_fixture("truncated_title_case.html")
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    expected_title = "Real Madrid vs. Real Oviedo: Preview, Predictions and Lineups"

    extracted = _extract_rule_based_content(str(article), expected_title)

    assert extracted is not None
    similarity = compute_text_similarity(
        "Real Madrid vs. Real Oviedo: Preview, Predictions and Lineups...",
        extracted.title,
    )
    assert similarity > 0.6
    _validate_extraction_result(extracted, expected_title)


def test_rewritten_title_fixture_passes_validation():
    html = _read_fixture("rewritten_title_case.html")
    soup = BeautifulSoup(html, "html.parser")
    article = soup.find("article")
    expected_title = "Liverpool transfer plan changes after injury concern before weekend match"

    extracted = _extract_rule_based_content(str(article), expected_title)

    assert extracted is not None
    _validate_extraction_result(extracted, expected_title)


def test_validation_fixture_is_rejected_for_noise_and_topic_mismatch():
    html = _read_fixture("validation_failure_case.html")
    expected_title = "Real Madrid vs. Real Oviedo: Preview, Predictions and Lineups"
    extracted = _extract_rule_based_content(html, expected_title)

    assert extracted is not None
    try:
        _validate_extraction_result(extracted, expected_title)
    except ValueError as exc:
        message = str(exc).lower()
        assert "noisy pattern" in message or "does not match expected title" in message
    else:
        raise AssertionError("Expected validation to reject noisy unrelated content.")
