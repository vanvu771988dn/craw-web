import datetime
from pathlib import Path

from src.database.models import ScrapedData
from src.database.persistence import Database
from src.utils.content_utils import compute_content_fingerprint, normalize_text_for_storage


def test_database_persists_tracker_and_final_urls(tmp_path: Path):
    db_path = tmp_path / "crawler.db"
    database = Database(str(db_path))
    database.init_database()

    database.save_scraped_data(
        ScrapedData(
            title="Test Title",
            url="https://www.example.com/final-story",
            tracker_url="https://c.newsnow.co.uk/A/123",
            tracker_article_id="123",
            final_url="https://www.example.com/final-story",
            normalized_title=normalize_text_for_storage("Test Title"),
            content_fingerprint=compute_content_fingerprint(
                "Test Title",
                "This is a sufficiently long article body.\n\nIt has more than one paragraph.",
            ),
            main_content="This is a sufficiently long article body.\n\nIt has more than one paragraph.",
            crawled_at=datetime.datetime.now(),
        )
    )

    assert database.url_exists("https://www.example.com/final-story") is True
    assert database.url_exists("https://c.newsnow.co.uk/A/123") is True
    assert database.article_exists(
        tracker_url="https://c.newsnow.co.uk/A/123",
        final_url="https://www.example.com/final-story",
        tracker_article_id="123",
    ) is True


def test_database_exact_duplicate_priority_prefers_canonical_url(tmp_path: Path):
    db_path = tmp_path / "crawler.db"
    database = Database(str(db_path))
    database.init_database()

    database.save_scraped_data(
        ScrapedData(
            canonical_url="https://www.example.com/story/canonical",
            title="Canonical Story",
            url="https://www.example.com/story?ref=home",
            tracker_url="https://c.newsnow.co.uk/A/999",
            tracker_article_id="999",
            final_url="https://www.example.com/story?ref=home",
            normalized_title=normalize_text_for_storage("Canonical Story"),
            content_fingerprint=compute_content_fingerprint(
                "Canonical Story",
                "Paragraph one.\n\nParagraph two.",
            ),
            main_content="Paragraph one.\n\nParagraph two.",
            crawled_at=datetime.datetime.now(),
        )
    )

    duplicate_of, duplicate_reason = database.find_existing_article(
        ScrapedData(
            canonical_url="https://www.example.com/story/canonical",
            final_url="https://www.example.com/story?ref=other",
            tracker_url="https://c.newsnow.co.uk/A/1000",
            tracker_article_id="1000",
            title="Canonical Story",
            main_content="Paragraph one.\n\nParagraph two.",
        )
    )

    assert duplicate_of == 1
    assert duplicate_reason == "canonical_url"


def test_database_exact_duplicate_priority_checks_unique_url_column(tmp_path: Path):
    db_path = tmp_path / "crawler.db"
    database = Database(str(db_path))
    database.init_database()

    database.save_scraped_data(
        ScrapedData(
            title="Saved Story",
            url="https://www.example.com/story?ref=home",
            final_url="https://www.example.com/story?ref=alt",
            tracker_url="https://c.newsnow.co.uk/A/2000",
            tracker_article_id="2000",
            main_content="Paragraph one.\n\nParagraph two.",
            crawled_at=datetime.datetime.now(),
        )
    )

    duplicate_of, duplicate_reason = database.find_existing_article(
        ScrapedData(
            url="https://www.example.com/story?ref=home",
            final_url="https://www.example.com/story?ref=other",
            tracker_url="https://c.newsnow.co.uk/A/2001",
            tracker_article_id="2001",
            title="Another title",
            main_content="Different content.",
        )
    )

    assert duplicate_of == 1
    assert duplicate_reason == "url"
