from src.core.evaluation_set import export_observed_evaluation_set


def main():
    cases = export_observed_evaluation_set(
        "data/crawl_events.jsonl",
        "tests/fixtures/newsnow/evaluation_set.observed.json",
        merge_with_existing=False,
    )
    print(f"Exported {len(cases)} observed evaluation cases.")


if __name__ == "__main__":
    main()
