import json
from pathlib import Path

from src.core.evaluation_set import (
    build_evaluation_cases_from_log,
    load_evaluation_cases,
    summarize_evaluation_cases,
)
from src.core.metrics import summarize_crawl_events_file


def _print_json(title: str, payload: dict) -> None:
    print(title)
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def main():
    log_path = Path("data/crawl_events.jsonl")
    fixture_path = Path("tests/fixtures/newsnow/evaluation_set.json")

    metrics_summary = summarize_crawl_events_file(log_path)
    observed_cases = build_evaluation_cases_from_log(log_path)
    fixture_cases = load_evaluation_cases(fixture_path)

    _print_json("Metrics Summary", metrics_summary.to_dict())
    _print_json("Observed Evaluation Summary", summarize_evaluation_cases(observed_cases).to_dict())
    _print_json("Fixture Evaluation Summary", summarize_evaluation_cases(fixture_cases).to_dict())


if __name__ == "__main__":
    main()
