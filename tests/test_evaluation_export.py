from pathlib import Path

from src.core.evaluation_set import EvaluationCase, export_observed_evaluation_set, write_evaluation_cases


def test_export_observed_evaluation_set_merges_existing_and_new_cases(tmp_path: Path):
    log_path = tmp_path / "crawl_events.jsonl"
    output_path = tmp_path / "evaluation_set.json"

    log_path.write_text(
        "\n".join(
            [
                '{"stage":"tracker_resolution","event":"tracker_html_parsed","tracker_url":"https://c.newsnow.co.uk/A/100","final_url":"https://publisher.example.com/story-100"}',
                '{"stage":"capture","event":"article_saved","tracker_url":"https://c.newsnow.co.uk/A/100","final_url":"https://publisher.example.com/story-100","canonical_url":"https://publisher.example.com/story-100-canonical","duplicate_status":"unique"}',
                '{"stage":"extraction","event":"candidate_accepted","tracker_url":"https://c.newsnow.co.uk/A/100","expected_title":"Observed title","source_site":"Publisher Example"}',
            ]
        ),
        encoding="utf-8",
    )

    write_evaluation_cases(
        [
            EvaluationCase(
                case_id="local-1",
                source="local_fixture",
                publisher="Local Publisher",
                tracker_url="https://c.newsnow.co.uk/A/1",
                final_url="https://local.example.com/story-1",
            )
        ],
        output_path,
    )

    cases = export_observed_evaluation_set(log_path, output_path, merge_with_existing=True)

    assert len(cases) == 2
    case_ids = {case.case_id for case in cases}
    assert "local-1" in case_ids
    assert "observed-1" in case_ids
