from src.core.article_candidates import compute_text_similarity, select_article_candidate_html
from src.core.dedup import classify_semantic_duplicate
from src.core.article_pipeline_service import filter_new_discovered_articles
from src.core.pagination_service import (
    GenericUIPaginationStrategy,
    NewsNowPaginationStrategy,
    collect_seen_tracker_urls,
)
from src.core.newsnow_discovery import (
    DiscoveredArticle,
    build_newsnow_page_context,
    ensure_latest_newsnow_url,
    parse_initial_newsnow_batch,
    parse_newsnow_articles_response,
)
from src.core.newsnow import normalize_url, parse_tracker_html
from src.core.processing import enrich_scraped_data_from_html
from src.core.site_adapters import select_site_adapter
from src.database.models import ScrapedData


TRACKER_HTML = """
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

INITIAL_PAGE_HTML = """
<html>
  <script>
    nn.data = {
      "mnid": '12',
      "nlid": '833',
      "nfp": 'Sport;Football',
      "sTim": '17787372-abc123'
    };
  </script>
  <div class="newsfeed">
    <div class="hl" data-id="1313197900">
      <div class="hl__inner">
        <a class="hll" href="https://c.newsnow.co.uk/A/1313197900?-833:12">Shakira, Madonna, and BTS to Headline World Cup Final Halftime Show</a>
        <span class="meta">
          <span class="src src-part" data-pub="ROLLINGSTONE">Rolling Stone</span>
          <span class="time" data-time="1778737134">06:38</span>
        </span>
      </div>
    </div>
  </div>
</html>
"""

BACKEND_BATCH_RESPONSE = """
{"success":1,"data":"_\\\"pubCountry\\\":\\\"US\\\"}]_\\\"type\\\":\\\"article\\\"_\\\"clickContext\\\":\\\"nn`utopic`u{tab}`ulatest\\\"_\\\"pubName\\\":\\\"Philadelphia Union `d Official Site\\\"_ Philadelphia Union 3\\\"_\\\"title\\\":\\\"Box Score | Orlando City SC 4_\\\"url\\\":\\\"https://c.newsnow.co.uk/A/1313188430?`d833:12\\\"_\\\"id\\\":\\\"1313188430\\\"_\\\"d1\\\":null}_\\\"dl\\\":null_\\\"d2\\\":null_\\\"ml\\\":null_\\\"img\\\":{\\\"d\\\":null_\\\"accessWarning\\\":\\\"\\\"_\\\"tags\\\":[]_\\\"access\\\":\\\"\\\"_{\\\"timestamp\\\":\\\"1778726901\\\"_\\\"pubCountry\\\":\\\"US\\\"}_\\\"type\\\":\\\"article\\\"_\\\"clickContext\\\":\\\"nn`utopic`u{tab}`ulatest\\\"_\\\"pubId\\\":\\\"MIAMIHERALD\\\"_\\\"pubName\\\":\\\"Miami Herald\\\"_ Miami rallies on Cincinnati blunders late\\\"_\\\"title\\\":\\\"Lionel Messi tallies twice early_\\\"url\\\":\\\"https://c.newsnow.co.uk/A/1313188447?`d833:12\\\"_\\\"dl\\\":null}_\\\"d1\\\":null_\\\"d2\\\":null_\\\"d\\\":null_\\\"img\\\":{\\\"ml\\\":null_\\\"id\\\":\\\"1313188447\\\"_\\\"accessWarning\\\":\\\"1\\\"_\\\"tags\\\":[]_\\\"access\\\":\\\"Paywall\\\"_{\\\"timestamp\\\":\\\"1778726932\\\"_\\\"ml\\\":null}}"} 
"""


def test_parse_tracker_html_extracts_redirect_metadata():
    result = parse_tracker_html("https://c.newsnow.co.uk/A/1313187102?-833:12", TRACKER_HTML)

    assert result.final_url == "https://www.example.com/story?id=123"
    assert result.tracker_article_id == "1313187102"
    assert result.redirect_delay_ms == 1000
    assert result.manual_redirect is False
    assert result.tracker_og_title == "Sample Tracker Title"
    assert result.tracker_og_image == "https://example.com/image.jpg"


def test_normalize_url_removes_fragment_and_normalizes_case():
    assert normalize_url("HTTPS://WWW.EXAMPLE.COM/path/#fragment") == "https://www.example.com/path"


def test_compute_text_similarity_handles_truncated_titles():
    similarity = compute_text_similarity(
        "Inter Miami player ratings vs FC Cincinnati: Lionel Messi can’t be stopped as Herons rally to…",
        "Inter Miami player ratings vs FC Cincinnati: Lionel Messi can’t be stopped as Herons rally to win eight-goal thriller",
    )

    assert similarity > 0.6


def test_select_article_candidate_html_prefers_article_with_matching_heading():
    html = """
    <html>
      <body>
        <div class="related-content">
          <h2>Related stories</h2>
          <p>Short unrelated content.</p>
        </div>
        <article>
          <h1>Real Madrid vs. Real Oviedo: Preview, Predictions and Lineups</h1>
          <p>Paragraph one with the main story.</p>
          <p>Paragraph two with more detail.</p>
          <p>Paragraph three with extra context.</p>
        </article>
      </body>
    </html>
    """

    selected_html = select_article_candidate_html(
        html,
        expected_title="Real Madrid vs. Real Oviedo: Preview, Predictions and Lineups",
    )

    assert "<article>" in selected_html
    assert "Related stories" not in selected_html


def test_build_newsnow_page_context_parses_initial_html():
    context = build_newsnow_page_context(
        "https://www.newsnow.co.uk/h/Sport/Football?type=ln",
        INITIAL_PAGE_HTML,
    )

    assert context.mnid == 12
    assert context.nlid == 833
    assert context.path == "Sport;Football"
    assert context.stim == "17787372-abc123"


def test_parse_initial_newsnow_batch_extracts_list_metadata():
    batch = parse_initial_newsnow_batch(
        "https://www.newsnow.co.uk/h/Sport/Football?type=ln",
        INITIAL_PAGE_HTML,
    )

    assert len(batch) == 1
    assert batch[0].tracker_url == "https://c.newsnow.co.uk/A/1313197900?-833:12"
    assert batch[0].grid_title == "Shakira, Madonna, and BTS to Headline World Cup Final Halftime Show"
    assert batch[0].grid_source == "Rolling Stone"
    assert batch[0].tracker_article_id == "1313197900"
    assert batch[0].timestamp == "1778737134"


def test_parse_newsnow_articles_response_extracts_backend_batch():
    batch = parse_newsnow_articles_response(
        "https://www.newsnow.co.uk/h/Sport/Football?type=ln",
        BACKEND_BATCH_RESPONSE,
        position_offset=40,
    )

    assert len(batch) == 2
    assert batch[0].tracker_url == "https://c.newsnow.co.uk/A/1313188430?`d833:12"
    assert batch[0].grid_title == "Box Score | Orlando City SC 4"
    assert batch[0].grid_source == "Philadelphia Union & Official Site"
    assert batch[0].tracker_article_id == "1313188430"
    assert batch[0].timestamp == "1778726901"
    assert batch[1].tracker_article_id == "1313188447"
    assert batch[1].grid_source == "Miami Herald"


def test_ensure_latest_newsnow_url_forces_latest_tab():
    url = "https://www.newsnow.co.uk/h/Sport/Football?type=ts&foo=bar"
    normalized = ensure_latest_newsnow_url(url)

    assert normalized == "https://www.newsnow.co.uk/h/Sport/Football?type=ln&foo=bar"


def test_filter_new_discovered_articles_skips_seen_tracker_urls():
    seen_tracker_urls = {"https://c.newsnow.co.uk/A/1313197900?-833:12"}
    discovered_articles = [
        DiscoveredArticle(
            list_page_url="https://www.newsnow.co.uk/h/Sport/Football?type=ln",
            tracker_url="https://c.newsnow.co.uk/A/1313197900?-833:12",
            grid_title="Existing article",
            grid_source="Rolling Stone",
            grid_time_text="06:38",
            grid_position=1,
            tracker_article_id="1313197900",
            timestamp="1778737134",
        ),
        DiscoveredArticle(
            list_page_url="https://www.newsnow.co.uk/h/Sport/Football?type=ln",
            tracker_url="https://c.newsnow.co.uk/A/1313197901?-833:12",
            grid_title="New article",
            grid_source="BBC Sport",
            grid_time_text="06:40",
            grid_position=2,
            tracker_article_id="1313197901",
            timestamp="1778737200",
        ),
    ]

    new_articles = filter_new_discovered_articles(discovered_articles, seen_tracker_urls)

    assert len(new_articles) == 1
    assert new_articles[0].tracker_url == "https://c.newsnow.co.uk/A/1313197901?-833:12"
    assert new_articles[0].grid_source == "BBC Sport"
    assert seen_tracker_urls == {
        "https://c.newsnow.co.uk/A/1313197900?-833:12",
        "https://c.newsnow.co.uk/A/1313197901?-833:12",
    }


def test_collect_seen_tracker_urls_normalizes_and_skips_empty_values():
    discovered_articles = [
        DiscoveredArticle(
            list_page_url="https://www.newsnow.co.uk/h/Sport/Football?type=ln",
            tracker_url="HTTPS://C.NEWSNOW.CO.UK/A/1313197900?-833:12#fragment",
            grid_title="Article one",
            grid_source="Rolling Stone",
            grid_time_text="06:38",
            grid_position=1,
            tracker_article_id="1313197900",
            timestamp="1778737134",
        ),
        DiscoveredArticle(
            list_page_url="https://www.newsnow.co.uk/h/Sport/Football?type=ln",
            tracker_url="",
            grid_title="Article two",
            grid_source="BBC Sport",
            grid_time_text="06:40",
            grid_position=2,
            tracker_article_id="1313197901",
            timestamp="1778737200",
        ),
    ]

    assert collect_seen_tracker_urls(discovered_articles) == {
        "https://c.newsnow.co.uk/A/1313197900?-833:12",
    }


def test_enrich_scraped_data_from_html_extracts_final_article_metadata():
    final_html = """
    <html>
      <head>
        <link rel="canonical" href="/story/canonical-version" />
        <meta property="og:title" content="Expanded Publisher Title" />
        <meta property="og:site_name" content="Example News" />
        <meta property="og:image" content="/images/top.jpg" />
        <meta name="author" content="Jane Doe" />
        <meta property="article:published_time" content="2026-05-14T10:15:00+00:00" />
        <meta property="article:modified_time" content="2026-05-14T12:00:00+00:00" />
      </head>
      <body>
        <article>
          <h1>Expanded Publisher Title</h1>
          <p>Paragraph one.</p>
          <p>Paragraph two.</p>
        </article>
      </body>
    </html>
    """

    enriched = enrich_scraped_data_from_html(
        ScrapedData(title=None, main_content="Paragraph one.\n\nParagraph two."),
        final_html,
        "https://publisher.example.com/story?id=123",
        expected_title="Expected NewsNow Title",
    )

    assert enriched.canonical_url == "https://publisher.example.com/story/canonical-version"
    assert enriched.title == "Expanded Publisher Title"
    assert enriched.author == "Jane Doe"
    assert enriched.source_site == "Example News"
    assert enriched.top_image_url == "https://publisher.example.com/images/top.jpg"
    assert enriched.published_at is not None
    assert enriched.updated_at is not None


def test_classify_semantic_duplicate_marks_same_story():
    article = ScrapedData(
        title="Liverpool transfer plan changes after late injury blow",
        main_content="Liverpool change their transfer plan after a late injury concern before the weekend fixture.",
    )
    recent_articles = [
        {
            "id": 7,
            "title": "Liverpool transfer plan changes after injury concern before weekend match",
            "main_content": "Liverpool alter the transfer strategy after an injury concern ahead of the weekend match.",
            "story_cluster_id": "story-7",
        }
    ]

    result = classify_semantic_duplicate(article, recent_articles)

    assert result.duplicate_status in {"same_story", "near_duplicate"}
    assert result.duplicate_of == 7
    assert result.story_cluster_id == "story-7"
    assert result.similarity_score is not None


def test_select_site_adapter_uses_newsnow_strategy_for_newsnow_urls():
    adapter = select_site_adapter("https://www.newsnow.co.uk/h/Sport/Football?type=ln")

    assert adapter.name == "newsnow"
    assert isinstance(adapter.pagination_strategy, NewsNowPaginationStrategy)


def test_select_site_adapter_uses_generic_ui_strategy_for_non_newsnow_urls():
    adapter = select_site_adapter("https://example.com/news")

    assert adapter.name == "generic_ui"
    assert isinstance(adapter.pagination_strategy, GenericUIPaginationStrategy)
