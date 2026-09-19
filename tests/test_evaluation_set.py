from src.core.evaluation_set import EvaluationCase, build_evaluation_cases_from_events, summarize_evaluation_cases


def test_build_evaluation_cases_from_events_joins_saved_resolution_and_extraction_events():
    events = [
        {
            "stage": "tracker_resolution",
            "event": "tracker_html_parsed",
            "tracker_url": "https://c.newsnow.co.uk/A/100",
            "final_url": "https://publisher.example.com/story-100",
        },
        {
            "stage": "capture",
            "event": "article_saved",
            "tracker_url": "https://c.newsnow.co.uk/A/100",
            "final_url": "https://publisher.example.com/story-100",
            "canonical_url": "https://publisher.example.com/story-100-canonical",
            "duplicate_status": "unique",
        },
        {
            "stage": "extraction",
            "event": "candidate_accepted",
            "tracker_url": "https://c.newsnow.co.uk/A/100",
            "expected_title": "Observed title",
            "source_site": "Publisher Example",
        },
    ]

    cases = build_evaluation_cases_from_events(events)

    assert len(cases) == 1
    case = cases[0]
    assert case.case_id == "observed-1"
    assert case.tracker_url == "https://c.newsnow.co.uk/A/100"
    assert case.final_url == "https://publisher.example.com/story-100"
    assert case.canonical_url == "https://publisher.example.com/story-100-canonical"
    assert case.expected_title == "Observed title"
    assert case.publisher == "Publisher Example"
    assert case.duplicate_status == "unique"


def test_build_evaluation_cases_from_events_ignores_incomplete_cases_without_final_url():
    events = [
        {
            "stage": "extraction",
            "event": "candidate_accepted",
            "tracker_url": "https://c.newsnow.co.uk/A/200",
            "expected_title": "Incomplete title",
        }
    ]

    cases = build_evaluation_cases_from_events(events)

    assert cases == []


def test_summarize_evaluation_cases_counts_sources_publishers_and_duplicate_labels():
    cases = [
        EvaluationCase(
            case_id="local-1",
            source="local_fixture",
            publisher="Publisher A",
            tracker_url="https://c.newsnow.co.uk/A/1",
            final_url="https://publisher-a.example/story-1",
            canonical_url="https://publisher-a.example/story-1-canonical",
            expected_title="Story 1",
            duplicate_status="unique",
        ),
        EvaluationCase(
            case_id="observed-1",
            source="observed_log",
            publisher="Publisher B",
            tracker_url="https://c.newsnow.co.uk/A/2",
            final_url="https://publisher-b.example/story-2",
            duplicate_status="same_story",
        ),
        EvaluationCase(
            case_id="observed-2",
            source="observed_log",
            publisher="Publisher B",
            tracker_url="https://c.newsnow.co.uk/A/3",
            final_url="https://publisher-b.example/story-3",
            duplicate_status="near_duplicate",
        ),
    ]

    summary = summarize_evaluation_cases(cases)

    assert summary.total_cases == 3
    assert summary.observed_cases == 2
    assert summary.local_fixture_cases == 1
    assert summary.unique_publishers == 2
    assert summary.cases_with_canonical_url == 1
    assert summary.cases_with_expected_title == 1
    assert summary.cases_marked_unique == 1
    assert summary.cases_marked_same_story == 1
    assert summary.cases_marked_near_duplicate == 1
