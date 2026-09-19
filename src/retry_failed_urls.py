"""
retry_failed_urls.py - Retry tracker URLs that failed during url_capture.

Luồng hoạt động:
  1. Đọc data/crawl_events.jsonl – mỗi dòng là một tracker URL chưa resolve được.
  2. Với mỗi dòng: resolve tracker_url → final_url.
     - Thành công  → append final_url vào output file của league → XÓA dòng khỏi file.
     - Thất bại    → giữ nguyên dòng (sẽ retry ở lần chạy tiếp theo).
  3. Ghi lại crawl_events.jsonl chỉ với những dòng vẫn còn thất bại.
"""

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from src.core.newsnow import normalize_url, resolve_newsnow_tracker_url
from src.utils.config_loader import load_config

EVENTS_LOG = Path("data/crawl_events.jsonl")
RETRY_TIMEOUT_MS = 30_000
RETRY_ATTEMPTS = 3


# ---------------------------------------------------------------------------
# Đọc / ghi crawl_events.jsonl
# ---------------------------------------------------------------------------


def load_pending_trackers(log_path: Path) -> list[dict]:
    """Đọc toàn bộ crawl_events.jsonl, trả về list các dict còn chờ retry.

    Mỗi dict có dạng: {"tracker_url": "...", "league": "...", "timestamp": "..."}
    Dòng nào parse lỗi hoặc thiếu tracker_url sẽ bị bỏ qua.
    """
    if not log_path.exists():
        return []

    pending = []
    with open(log_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("tracker_url"):
                pending.append(entry)
    return pending


def save_pending_trackers(log_path: Path, pending: list[dict]) -> None:
    """Ghi lại danh sách tracker URLs chưa resolve thành công vào file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as fh:
        for entry in pending:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Output file helpers
# ---------------------------------------------------------------------------


def find_latest_output_file(output_dir: Path, league: str) -> Path | None:
    safe_name = league.replace(" ", "_").replace("/", "-")
    candidates = sorted(output_dir.glob(f"{safe_name}_*.txt"))
    return candidates[-1] if candidates else None


def load_urls_from_file(file_path: Path) -> set:
    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
        return {line.strip() for line in lines[1:] if line.strip()}
    except Exception:
        return set()


def append_url_to_file(file_path: Path, url: str) -> None:
    with open(file_path, "a", encoding="utf-8") as fh:
        fh.write(url + "\n")


def ensure_other_file(output_dir: Path, dry_run: bool) -> Path:
    """Return path to the 'other' output file for the current hour.
    Creates the file with a header line if it does not exist yet."""
    now_str = datetime.now().strftime("%Y%m%d%H")
    other_file = output_dir / f"other_{now_str}.txt"
    if not dry_run and not other_file.exists():
        output_dir.mkdir(parents=True, exist_ok=True)
        other_file.write_text("other\n", encoding="utf-8")
        print(f"  [other] Created {other_file.name}")
    return other_file


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


async def retry_single(
    entry: dict,
    output_dir: Path,
    dry_run: bool,
) -> str:
    """Retry một tracker URL.

    Returns:
        "resolved"       - resolve thành công và đã ghi vào output file
        "already_exists" - URL đã có trong output file
        "no_output_file" - không tìm thấy output file cho league
        "failed"         - vẫn không resolve được
    """
    tracker_url: str = entry["tracker_url"]
    league: str = entry.get("league", "other")

    print(f"  [RETRY] [{league}] {tracker_url}")

    try:
        resolution = await resolve_newsnow_tracker_url(
            tracker_url, timeout_ms=RETRY_TIMEOUT_MS, retries=RETRY_ATTEMPTS
        )
        final_url = normalize_url(resolution.final_url) if resolution else None
    except Exception as exc:
        print(f"    [x] Still failing: {exc}")
        return "failed"

    if not final_url:
        print("    [x] Resolved but no final_url extracted.")
        return "failed"

    # Tìm output file phù hợp
    out_file = find_latest_output_file(output_dir, league)
    if out_file is None:
        if league == "other":
            out_file = ensure_other_file(output_dir, dry_run)
        else:
            print(f"    [?] No output file found for league {league!r} -- writing to 'other'.")
            out_file = ensure_other_file(output_dir, dry_run)

    existing = load_urls_from_file(out_file)
    if final_url in existing:
        print(f"    [=] Already in {out_file.name} -- skipping.")
        return "already_exists"

    print(f"    [OK] {final_url}")
    print(f"    [->] Append to {out_file.name}")
    if not dry_run:
        append_url_to_file(out_file, final_url)
    return "resolved"


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_retry(dry_run: bool, output_dir: Path, log_path: Path) -> None:
    print("=" * 60)
    print("  RETRY FAILED TRACKER URLs")
    if dry_run:
        print("  *** DRY-RUN MODE -- no files will be modified ***")
    print("=" * 60)

    print("\n[1/3] Loading pending tracker URLs from log ...")
    pending = load_pending_trackers(log_path)
    if not pending:
        print("      No pending tracker URLs found. Nothing to retry.")
        return
    print(f"      {len(pending)} tracker URL(s) to retry.")

    # Đảm bảo file 'other' tồn tại nếu có league không rõ
    unknown_leagues = [e for e in pending if not e.get("league")]
    if unknown_leagues and not dry_run:
        ensure_other_file(output_dir, dry_run)

    print(f"\n[2/3] Retrying {len(pending)} URL(s) ...\n")
    stats = {"resolved": 0, "already_exists": 0, "no_output_file": 0, "failed": 0}
    still_pending: list[dict] = []

    for entry in pending:
        outcome = await retry_single(entry, output_dir, dry_run)
        stats[outcome] = stats.get(outcome, 0) + 1

        # Giữ lại những entry vẫn thất bại
        if outcome == "failed":
            still_pending.append(entry)
        # "no_output_file" → viết vào 'other' nên cũng coi là resolved (không giữ lại)

    print(f"\n[3/3] Writing back {len(still_pending)} still-pending URL(s) to log ...")
    if not dry_run:
        save_pending_trackers(log_path, still_pending)
        print(f"      Done. {len(pending) - len(still_pending)} line(s) removed from log.")
    else:
        print("      (Dry-run: log not modified)")

    print("\n" + "=" * 60)
    print("  RETRY SUMMARY")
    print("=" * 60)
    print(f"  [OK] Resolved & appended  : {stats['resolved']}")
    print(f"  [=]  Already in output    : {stats['already_exists']}")
    print(f"  [x]  Still failing        : {stats['failed']}")
    if dry_run:
        print("\n  (Dry-run: no changes were written)")
    print("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Retry tracker URLs that failed during url_capture."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate only -- do not write to any files.",
    )
    args = parser.parse_args()

    config = load_config()
    output_dir = Path(config.get("url_capture", {}).get("output_dir", "output"))
    asyncio.run(run_retry(dry_run=args.dry_run, output_dir=output_dir, log_path=EVENTS_LOG))


if __name__ == "__main__":
    main()
