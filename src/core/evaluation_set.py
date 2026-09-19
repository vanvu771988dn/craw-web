import json
from dataclasses import dataclass, asdict
from pathlib import Path

from src.core.metrics import load_structured_events


@dataclass(slots=True)
class EvaluationCase:
    case_id: str
    publisher: str | None
    tracker_url: str
    final_url: str | None
    canonical_url: str | None = None
    expected_title: str | None = None
    duplicate_status: str | None = None
    source: str = "observed_log"
    notes: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class EvaluationSetSummary:
    total_cases: int = 0
    observed_cases: int = 0
    local_fixture_cases: int = 0
    unique_publishers: int = 0
    cases_with_canonical_url: int = 0
    cases_with_expected_title: int = 0
    cases_marked_unique: int = 0
    cases_marked_near_duplicate: int = 0
    cases_marked_same_story: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


def build_evaluation_cases_from_events(events: list[dict]) -> list[EvaluationCase]:
    """Builds evaluation cases from structured crawl events when enough context is available."""
    cases_by_tracker: dict[str, EvaluationCase] = {}

    for event in events:
        stage = event.get("stage")
        name = event.get("event")
        tracker_url = event.get("tracker_url")
        if not tracker_url:
            continue

        if stage == "capture" and name == "article_saved":
            case = cases_by_tracker.get(tracker_url)
            if not case:
                case = EvaluationCase(
                    case_id=f"observed-{len(cases_by_tracker) + 1}",
                    publisher=None,
                    tracker_url=tracker_url,
                    final_url=event.get("final_url"),
                )
                cases_by_tracker[tracker_url] = case

            case.final_url = event.get("final_url") or case.final_url
            case.canonical_url = event.get("canonical_url") or case.canonical_url
            case.duplicate_status = event.get("duplicate_status") or case.duplicate_status

        if stage == "tracker_resolution" and name in {"tracker_html_parsed", "browser_fallback_succeeded"}:
            case = cases_by_tracker.get(tracker_url)
            if case:
                case.final_url = event.get("final_url") or case.final_url

        if stage == "extraction" and name == "candidate_accepted":
            case = cases_by_tracker.get(tracker_url)
            if case:
                case.expected_title = event.get("expected_title") or case.expected_title
                if not case.publisher:
                    case.publisher = event.get("source_site")

    return [case for case in cases_by_tracker.values() if case.final_url]


def build_evaluation_cases_from_log(log_path: str | Path) -> list[EvaluationCase]:
    return build_evaluation_cases_from_events(load_structured_events(log_path))


def merge_evaluation_cases(
    existing_cases: list[EvaluationCase],
    new_cases: list[EvaluationCase],
) -> list[EvaluationCase]:
    merged: dict[str, EvaluationCase] = {case.case_id: case for case in existing_cases}
    for case in new_cases:
        merged[case.case_id] = case
    return list(merged.values())


def load_evaluation_cases(path: str | Path) -> list[EvaluationCase]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    payload = json.loads(file_path.read_text(encoding="utf-8"))
    return [EvaluationCase(**item) for item in payload]


def write_evaluation_cases(cases: list[EvaluationCase], output_path: str | Path) -> None:
    path = Path(output_path)
    path.write_text(
        json.dumps([case.to_dict() for case in cases], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def export_observed_evaluation_set(
    log_path: str | Path,
    output_path: str | Path,
    *,
    merge_with_existing: bool = True,
) -> list[EvaluationCase]:
    observed_cases = build_evaluation_cases_from_log(log_path)
    if merge_with_existing:
        existing_cases = load_evaluation_cases(output_path)
        observed_cases = merge_evaluation_cases(existing_cases, observed_cases)
    write_evaluation_cases(observed_cases, output_path)
    return observed_cases


def summarize_evaluation_cases(cases: list[EvaluationCase]) -> EvaluationSetSummary:
    publishers = {case.publisher for case in cases if case.publisher}
    return EvaluationSetSummary(
        total_cases=len(cases),
        observed_cases=sum(1 for case in cases if case.source == "observed_log"),
        local_fixture_cases=sum(1 for case in cases if case.source == "local_fixture"),
        unique_publishers=len(publishers),
        cases_with_canonical_url=sum(1 for case in cases if case.canonical_url),
        cases_with_expected_title=sum(1 for case in cases if case.expected_title),
        cases_marked_unique=sum(1 for case in cases if case.duplicate_status == "unique"),
        cases_marked_near_duplicate=sum(1 for case in cases if case.duplicate_status == "near_duplicate"),
        cases_marked_same_story=sum(1 for case in cases if case.duplicate_status == "same_story"),
    )
