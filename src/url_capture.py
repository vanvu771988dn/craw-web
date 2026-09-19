"""
url_capture.py – Multi-source URL capture using Playwright Stealth.

For each configured NewsNow source:
  1. Playwright-fetch the initial page HTML (bypasses Cloudflare/anti-bot).
  2. Parse the initial article batch + build the backend API context.
  3. Paginate via the NewsNow backend API (pure HTTP POST).
  4. Stop when an article's timestamp is outside the configured time window
     OR when a previously-saved cursor timestamp is reached.
  5. Resolve each tracker URL -> final destination URL via Playwright.
  6. Write all captured final URLs to output/football_urls_<YYYYMMDD_HHMMSS>.txt.
  7. Persist the newest article metadata per source to output/cursor.json
     so the next run only collects articles newer than the last run.

Usage:
    python -m src.url_capture
"""

import asyncio
import json
import time
import re
import random
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlencode, parse_qsl, urlunparse

from src.core.newsnow import normalize_url, resolve_newsnow_tracker_url, IPBlockedError
from src.core.newsnow_discovery import (
    DiscoveredArticle,
    build_newsnow_page_context,
    ensure_latest_newsnow_url,
    fetch_newsnow_articles_batch,
)
from src.core.playwright_browser import async_fetch_html, init_browser, close_browser
from src.utils.config_loader import load_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIMEOUT_S = 30


# ---------------------------------------------------------------------------
# Timestamp utilities
# ---------------------------------------------------------------------------


def _parse_timestamp_to_epoch(ts: str | None) -> float | None:
    if not ts:
        return None
    try:
        return float(ts)
    except (ValueError, TypeError):
        pass
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            continue
    return None


def _is_within_window(ts_str: str | None, hours: float) -> bool | None:
    epoch = _parse_timestamp_to_epoch(ts_str)
    if epoch is None:
        return None
    cutoff = time.time() - hours * 3600
    return epoch >= cutoff


def _is_newer_than_cursor(ts_str: str | None, cursor_ts: str | None) -> bool:
    if not cursor_ts:
        return True
    article_epoch = _parse_timestamp_to_epoch(ts_str)
    cursor_epoch = _parse_timestamp_to_epoch(cursor_ts)
    if article_epoch is None or cursor_epoch is None:
        return True
    return article_epoch >= cursor_epoch


# ---------------------------------------------------------------------------
# Cursor persistence
# ---------------------------------------------------------------------------


def load_cursor(cursor_path: Path) -> dict:
    if cursor_path.exists():
        try:
            return json.loads(cursor_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"[cursor] Warning: could not read cursor file ({exc}); starting fresh.")
    return {}


def save_cursor(cursor_path: Path, cursor: dict) -> None:
    cursor_path.parent.mkdir(parents=True, exist_ok=True)
    cursor_path.write_text(
        json.dumps(cursor, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"[cursor] Cursor saved -> {cursor_path}")


# ---------------------------------------------------------------------------
# Top-tab helpers
# ---------------------------------------------------------------------------


def load_existing_urls_for_league(output_dir: Path, league: str) -> set[str]:
    """Return the set of URLs already written across ALL files of the most
    recent batch for *league*.  Returns an empty set if no file is found.

    File naming convention:
      Part 1 : {safe_league_name}_{YYYYMMDDhh}.txt
      Part 2+: {safe_league_name}_{YYYYMMDDhh}_2.txt, _3.txt, ...

    Strategy:
      1. Collect every matching file.
      2. Extract the timestamp prefix (the YYYYMMDDhh part, ignoring _2, _3 …).
      3. Find the latest timestamp prefix (lexicographic max = chronological max).
      4. Read ALL files that share that prefix so we don't miss any part files.
    """
    import re as _re

    safe_name = league.replace(" ", "_").replace("/", "-")
    pattern = f"{safe_name}_*.txt"
    candidates = list(output_dir.glob(pattern))
    if not candidates:
        return set()

    # Extract the timestamp prefix for each file.
    # Filename format: {safe_name}_{ts}[_{part}].txt  where ts = YYYYMMDDhh (10 digits)
    ts_re = _re.compile(
        r"^" + _re.escape(safe_name) + r"_(\d{10})(?:_\d+)?\.txt$"
    )
    prefix_map: dict[str, list[Path]] = {}
    for f in candidates:
        m = ts_re.match(f.name)
        if m:
            ts_prefix = m.group(1)
            prefix_map.setdefault(ts_prefix, []).append(f)

    if not prefix_map:
        return set()

    latest_prefix = max(prefix_map.keys())  # lexicographic max = newest hour
    latest_files = sorted(prefix_map[latest_prefix])  # part 1, 2, 3 …

    existing: set[str] = set()
    for f in latest_files:
        try:
            lines = f.read_text(encoding="utf-8").splitlines()
            for line in lines[1:]:  # skip first line (league label)
                stripped = line.strip()
                if stripped:
                    existing.add(stripped)
        except Exception as exc:
            print(f"[top-dedup] Warning: could not read {f}: {exc}")

    print(
        f"[top-dedup] [{league}] Loaded {len(existing)} existing URLs "
        f"from {len(latest_files)} file(s) with prefix '{safe_name}_{latest_prefix}'"
    )
    return existing


def derive_top_url(latest_url: str) -> str:
    """Convert a Latest-tab URL to the Top-tab URL by removing the 'type'
    query parameter entirely (Top tab has no type param on NewsNow).
    """
    parsed = urlparse(latest_url)
    params = [(k, v) for k, v in parse_qsl(parsed.query) if k != "type"]
    new_query = urlencode(params)
    return urlunparse(parsed._replace(query=new_query))


# ---------------------------------------------------------------------------
# Per-source capture
# ---------------------------------------------------------------------------


def extract_initial_articles(html: str, start_url: str) -> list[DiscoveredArticle]:
    """Parse Playwright-rendered NewsNow Vue.js DOM to extract article metadata."""
    text = html

    # In the rendered DOM, tracker URLs appear inside href attributes
    url_matches = list(re.finditer(
        r'href="(https://c\.newsnow\.co\.uk/A/(\d+)\?[^"\s]+)"',
        text
    ))
    print(f"[DEBUG] Found {len(url_matches)} tracker URLs in initial HTML")
    seen = set()
    articles = []

    for m in url_matches:
        tracker_url = m.group(1)
        article_id = m.group(2)
        if tracker_url in seen:
            continue
        seen.add(tracker_url)

        # Wider search window - timestamp is up to 1500 chars after the URL
        s = max(0, m.start() - 300)
        e = min(len(text), m.end() + 1500)
        window = text[s:e]

        # Vue.js renders timestamp as data-timestamp="<unix_epoch>"
        ts_match = (
            re.search(r'data-timestamp="(\d+)"', window)
            or re.search(r'data-time="([^"]+)"', window)
            or re.search(r'"timestamp":"([^"]+)"', window)
        )

        # Title inside <span class="article-title ...">
        title_match = re.search(
            r'class="article-title[^"]*"[^>]*>([^<]+)</span>',
            window
        )

        ts = ts_match.group(1) if ts_match else None
        title = title_match.group(1).strip() if title_match else None

        if not ts:
            continue

        articles.append(DiscoveredArticle(
            list_page_url=start_url,
            tracker_url=tracker_url,
            grid_title=title,
            grid_source=None,
            grid_time_text=ts,
            grid_position=len(articles) + 1,
            tracker_article_id=article_id,
            timestamp=ts,
        ))

    print(f"[DEBUG] Final parsed articles: {len(articles)}")
    return articles


async def capture_source(
    source_url: str,
    league: str,
    time_window_hours: float,
    cursor: dict,
) -> tuple[list[dict], dict | None]:

    url = ensure_latest_newsnow_url(source_url)
    source_cursor = cursor.get(league, {})
    cursor_ts: str | None = source_cursor.get("timestamp")

    print(f"\n{'='*60}")
    print(f"[{league}] Source : {url}")
    if cursor_ts:
        print(f"[{league}] Cursor : articles newer than timestamp={cursor_ts}")
    else:
        print(f"[{league}] Cursor : no cursor found -- collecting all within {time_window_hours}h")

    try:
        html = await async_fetch_html(url, timeout_ms=TIMEOUT_S * 1000)
        print(f"[{league}] [browser] fetched {len(html)} chars from {url}")
    except Exception as exc:
        print(f"[{league}] [!] Initial page fetch failed: {exc}")
        return [], None

    try:
        page_context = build_newsnow_page_context(url, html)
    except Exception as exc:
        print(f"[{league}] [!] Page context parse failed: {exc}")
        return [], None

    initial_batch = extract_initial_articles(html, url)
    if not initial_batch:
        print(f"[{league}] No articles found in initial page HTML.")
        return [], None

    print(f"[{league}] Initial batch: {len(initial_batch)} articles")

    records: list[dict] = []
    newest_article = None
    # Flag: True khi IP bị block trong phiên này
    # → các URL tiếp theo sẽ chỉ log, không resolve nữa
    ip_blocked_in_session: bool = False

    async def process_batch(batch):
        nonlocal newest_article, ip_blocked_in_session
        stop = False

        for article in batch:
            within = _is_within_window(article.timestamp, time_window_hours)
            if within is False:
                print(
                    f"[{league}] [STOP] Article beyond {time_window_hours}h window "
                    f"(ts={article.timestamp}) -- stopping source."
                )
                return True

            if not _is_newer_than_cursor(article.timestamp, cursor_ts):
                print(
                    f"[{league}] [STOP] Reached cursor boundary "
                    f"(ts={article.timestamp} <= cursor={cursor_ts}) -- stopping source."
                )
                return True

            if not article.tracker_url:
                continue

            # Nếu IP đã bị block trong phiên này → bỏ qua, chỉ log để retry sau
            if ip_blocked_in_session:
                print(f"[{league}] [BLOCK] IP still blocked → skipped (logged for retry): {article.tracker_url}")
                from src.utils.file_logger import log_pending_tracker as _log_pending
                _log_pending(article.tracker_url, league, article.timestamp or "")
                continue

            try:
                resolution = await resolve_newsnow_tracker_url(
                    article.tracker_url, timeout_ms=TIMEOUT_S * 1000, retries=1
                )
                final_url = normalize_url(resolution.final_url) if resolution else None
            except IPBlockedError as blocked:
                # IP bị block → đặt flag, log URL để retry sau
                ip_blocked_in_session = True
                from src.utils.file_logger import log_pending_tracker as _log_pending
                _log_pending(blocked.tracker_url, league, article.timestamp or "")
                print(f"[{league}] [BLOCK] IP blocked → logged for retry: {blocked.tracker_url}")
                print(f"[{league}] [BLOCK] All subsequent URLs will be skipped (IP blocked in session).")
                final_url = None
            except Exception as exc:
                print(f"[{league}] [!] Resolve failed ({article.tracker_url}): {exc}")
                from src.utils.file_logger import log_pending_tracker as _log_pending
                _log_pending(article.tracker_url, league, article.timestamp or "")
                final_url = None

            if not final_url:
                print(f"[{league}] [-] Could not resolve -> {article.tracker_url}")
                continue

            # Chỉ advance cursor khi có ít nhất 1 URL được resolve thành công.
            # Điều này đảm bảo nếu toàn phiên bị IP block, cursor KHÔNG được cập nhật
            # → lần chạy tiếp theo sẽ tự crawl lại những articles bị thiếu từ vị trí cũ.
            if newest_article is None:
                newest_article = article

            records.append({
                "league": league,
                "final_url": final_url,
                "tracker_url": article.tracker_url,
                "title": article.grid_title,
                "source_site": article.grid_source,
                "timestamp": article.timestamp,
            })
            print(f"[{league}] [+] {final_url}")

        return stop

    should_stop = await process_batch(initial_batch)

    if not should_stop:
        current_batch = initial_batch
        position_offset = len(initial_batch)
        batch_num = 1

        while True:
            last = current_batch[-1]
            if not last.tracker_article_id or not last.timestamp:
                print(f"[{league}] No backend cursor available -- ending pagination.")
                break

            print(f"[{league}] Fetching backend batch #{batch_num + 1} ...")
            BATCH_OUTER_RETRIES = 2
            BATCH_RETRY_DELAY_S = 5
            next_batch = None
            batch_ok = False
            for outer_attempt in range(1, BATCH_OUTER_RETRIES + 2):  # 1, 2, 3
                try:
                    next_batch = await fetch_newsnow_articles_batch(
                        page_context,
                        cursor_article_id=last.tracker_article_id,
                        cursor_ts=last.timestamp,
                        timeout_ms=TIMEOUT_S * 1000,
                        position_offset=position_offset,
                        retries=2,
                    )
                    batch_ok = True
                    break
                except Exception as exc:
                    if outer_attempt <= BATCH_OUTER_RETRIES:
                        print(
                            f"[{league}] [!] Backend batch failed (attempt {outer_attempt}/{BATCH_OUTER_RETRIES + 1}): {exc}"
                            f" -- retrying in {BATCH_RETRY_DELAY_S}s ..."
                        )
                        await asyncio.sleep(BATCH_RETRY_DELAY_S)
                    else:
                        print(
                            f"[{league}] [!] Backend batch failed after {BATCH_OUTER_RETRIES + 1} attempts: {exc}"
                            f" -- giving up on this source."
                        )
            if not batch_ok:
                break

            if not next_batch:
                print(f"[{league}] Empty backend batch -- ending pagination.")
                break

            should_stop = await process_batch(next_batch)
            if should_stop:
                break

            position_offset += len(next_batch)
            current_batch = next_batch
            batch_num += 1

    newest_meta = None
    if newest_article:
        from datetime import datetime, timezone
        newest_meta = {
            "timestamp": newest_article.timestamp,
            "article_id": newest_article.tracker_article_id,
            "tracker_url": newest_article.tracker_url,
            "title": newest_article.grid_title,
            "crawled_at": datetime.now(timezone.utc).isoformat(),
        }

    print(f"[{league}] Done -- {len(records)} final URLs captured.")
    return records, newest_meta


async def capture_source_top(
    source_url: str,
    league: str,
    top_window_hours: float,
    existing_urls: set[str],
) -> list[dict]:
    """Capture Top-tab articles for a single source.

    * URL is derived by stripping the 'type' query param (Top has no type).
    * No cursor is used – only the time window applies.
    * Any URL already present in *existing_urls* is skipped (dedup).
    """
    top_url = derive_top_url(source_url)
    print(f"\n[{league}] [TOP] Fetching Top tab: {top_url}")

    # Pass an empty cursor so _is_newer_than_cursor always returns True
    # (only the time window stops pagination).
    records, _newest_meta = await capture_source(
        source_url=top_url,
        league=league,
        time_window_hours=top_window_hours,
        cursor={},
    )

    new_records: list[dict] = []
    skipped = 0
    for rec in records:
        url = rec.get("final_url", "")
        if url and url in existing_urls:
            skipped += 1
            continue
        new_records.append(rec)
        existing_urls.add(url)  # prevent intra-batch dupes

    print(
        f"[{league}] [TOP] {len(new_records)} new URLs added, "
        f"{skipped} duplicates skipped."
    )
    return new_records


MAX_URLS_PER_FILE = 30


def write_output_per_league(
    output_dir: Path,
    records: list[dict],
    league: str,
    now_str: str,
) -> Path | None:
    """Write output file(s) for one league, max MAX_URLS_PER_FILE URLs per file.

    File naming:
      - Part 1  : {league}_{YYYYMMDDhh}.txt
      - Part 2+ : {league}_{YYYYMMDDhh}_2.txt, _3.txt, ...

    Each file starts with the league name on the first line,
    followed by one final URL per line.
    """
    valid = [r for r in records if r.get("final_url")]
    if not valid:
        print(f"[{league}] No valid URLs to write -- skipping file.")
        return None

    safe_name = league.replace(" ", "_").replace("/", "-")
    first_file: Path | None = None

    # Split into chunks of MAX_URLS_PER_FILE
    chunks = [
        valid[i : i + MAX_URLS_PER_FILE]
        for i in range(0, len(valid), MAX_URLS_PER_FILE)
    ]

    for part_idx, chunk in enumerate(chunks, start=1):
        if part_idx == 1:
            filename = f"{safe_name}_{now_str}.txt"
        else:
            filename = f"{safe_name}_{now_str}_{part_idx}.txt"

        out_file = output_dir / filename

        with open(out_file, "w", encoding="utf-8") as fh:
            fh.write(league + "\n")   # first line = league label
            for rec in chunk:
                fh.write(rec["final_url"] + "\n")

        print(
            f"[SUCCESS] [{league}] Part {part_idx}/{len(chunks)} written -> "
            f"{out_file}  ({len(chunk)} URLs)"
        )

        if first_file is None:
            first_file = out_file

    total = len(valid)
    if len(chunks) > 1:
        print(
            f"[SUCCESS] [{league}] Total {total} URLs split across "
            f"{len(chunks)} files (max {MAX_URLS_PER_FILE} each)."
        )

    return first_file


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------


async def run_capture(config: dict) -> None:
    capture_cfg = config.get("url_capture", {})
    sources: list[dict] = capture_cfg.get("sources", [])
    time_window_hours: float = float(capture_cfg.get("time_window_hours", 24))
    output_dir = Path(capture_cfg.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    if not sources:
        print("[!] No sources configured under url_capture.sources -- nothing to do.")
        return

    # ------------------------------------------------------------------
    # Startup: xoá sạch log cũ – run mới ghi lại từ đầu
    # ------------------------------------------------------------------
    from src.utils.file_logger import clear_crawl_events
    clear_crawl_events()

    # ------------------------------------------------------------------
    # Cleanup: remove output .txt files older than 24 hours
    # ------------------------------------------------------------------
    cutoff = time.time() - 24 * 3600
    removed = 0
    for txt_file in output_dir.glob("*.txt"):
        try:
            if txt_file.stat().st_mtime < cutoff:
                txt_file.unlink()
                print(f"[cleanup] Deleted old file: {txt_file.name}")
                removed += 1
        except Exception as exc:
            print(f"[cleanup] Warning: could not delete {txt_file.name}: {exc}")
    if removed:
        print(f"[cleanup] {removed} file(s) deleted (older than 24h).")
    else:
        print("[cleanup] No files older than 24h found.")

    # Start the shared Playwright browser (one instance for whole run)
    await init_browser()

    cursor_path = output_dir / "cursor.json"
    cursor = load_cursor(cursor_path)

    all_records: list[dict] = []
    updated_cursor = dict(cursor)

    async def process_single_source(source: dict):
        url = source.get("url", "")
        league = source.get("league", url)
        source_type = source.get("type", "league")
        if not url:
            print(f"[!] Skipping source with no URL: {source}")
            return [], None, league

        if "newsnow.co.uk" in url and "type=ln" not in url:
            sep = "&" if "?" in url else "?"
            url += f"{sep}type=ln"

        try:
            records, newest_meta = await capture_source(
                source_url=url,
                league=league,
                time_window_hours=time_window_hours,
                cursor=cursor,
            )
            for r in records:
                r["type"] = source_type
        except Exception as exc:
            print(f"[{league}] [!] capture_source failed: {exc}")
            records, newest_meta = [], None

        # Dedup Latest-tab results against previous run's output files.
        # This is a safety net: even if the cursor is missing/reset, URLs
        # that already exist in the last batch of output files are dropped.
        if records:
            prev_urls = load_existing_urls_for_league(output_dir, league)
            if prev_urls:
                before = len(records)
                records = [r for r in records if r.get("final_url") not in prev_urls]
                dropped = before - len(records)
                if dropped:
                    print(
                        f"[{league}] [latest-dedup] Dropped {dropped} URL(s) "
                        f"already present in previous output files."
                    )

        return records, newest_meta, league

    try:
        club_sources = [s for s in sources if s.get("type") == "club"]
        league_sources = [s for s in sources if s.get("type", "league") == "league"]
        transfer_sources = [s for s in sources if s.get("type") == "transfer"]

        print(f"\n[*] PHASE 1: Capture {len(club_sources)} BIG CLUBS first...")
        club_tasks = [process_single_source(source) for source in club_sources]
        club_results = await asyncio.gather(*club_tasks)

        for records, newest_meta, league in club_results:
            all_records.extend(records)
            if newest_meta:
                updated_cursor[league] = newest_meta

        print(f"\n[*] PHASE 1.5: Capture {len(transfer_sources)} TRANSFER NEWS source(s)...")
        transfer_tasks = [process_single_source(source) for source in transfer_sources]
        transfer_results = await asyncio.gather(*transfer_tasks)

        transfer_records: list[dict] = []
        for records, newest_meta, league in transfer_results:
            transfer_records.extend(records)
            if newest_meta:
                updated_cursor[league] = newest_meta

        print(f"\n[*] PHASE 2: Capture {len(league_sources)} LEAGUES...")
        league_tasks = [process_single_source(source) for source in league_sources]
        league_results = await asyncio.gather(*league_tasks)

        for records, newest_meta, league in league_results:
            all_records.extend(records)
            if newest_meta:
                updated_cursor[league] = newest_meta

        # Gather URLs belonging to "club" sources to filter them out of "league" sources
        club_urls = set()
        for rec in all_records:
            if rec.get("type") == "club" and rec.get("final_url"):
                club_urls.add(rec["final_url"])

        # Filter out records (transfer records are intentionally NOT filtered)
        filtered_records = []
        for rec in all_records:
            if rec.get("type") == "league":
                if rec.get("final_url") in club_urls:
                    print(f"[{rec.get('league')}] [FILTER] Dropping {rec.get('final_url')} (already covered by a club)")
                    continue
            filtered_records.append(rec)

        # ------------------------------------------------------------------
        # PHASE 3: Top-tab capture for every source
        # ------------------------------------------------------------------
        top_time_window_hours: float = float(
            capture_cfg.get("top_time_window_hours", 20)
        )
        print(
            f"\n[*] PHASE 3: Capture Top tab for {len(sources)} sources "
            f"(window={top_time_window_hours}h) ..."
        )

        # Build per-league URL sets from this run's Latest results so Top
        # doesn't duplicate what Latest already found.
        from collections import defaultdict
        current_run_urls_by_league: dict[str, set[str]] = defaultdict(set)
        for rec in filtered_records:
            fu = rec.get("final_url")
            if fu:
                current_run_urls_by_league[rec["league"]].add(fu)

        async def process_single_source_top(source: dict):
            url = source.get("url", "")
            league_name = source.get("league", url)
            source_type = source.get("type", "league")
            if not url:
                return [], league_name, source_type

            # Existing URLs = most recent file on disk + already captured
            file_existing = load_existing_urls_for_league(output_dir, league_name)
            existing_urls = file_existing | current_run_urls_by_league.get(
                league_name, set()
            )

            try:
                top_recs = await capture_source_top(
                    source_url=url,
                    league=league_name,
                    top_window_hours=top_time_window_hours,
                    existing_urls=existing_urls,
                )
            except Exception as exc:
                print(f"[{league_name}] [TOP] [!] Top capture failed: {exc}")
                top_recs = []

            for r in top_recs:
                r["type"] = source_type
            return top_recs, league_name, source_type

        top_tasks = [process_single_source_top(s) for s in sources]
        top_results = await asyncio.gather(*top_tasks)

        for top_recs, _league_name, _source_type in top_results:
            filtered_records.extend(top_recs)

        # ------------------------------------------------------------------
        # Write output files (Latest + Top combined, one file per league)
        # ------------------------------------------------------------------

        # Timestamp for filenames: YYYYMMDDhh  (hour-granularity)
        now_str = datetime.now().strftime("%Y%m%d%H")

        # Group records by league and write one file per league
        records_by_league: dict[str, list[dict]] = defaultdict(list)
        for rec in filtered_records:
            records_by_league[rec["league"]].append(rec)

        out_files = []
        for league_name, league_records in records_by_league.items():
            out_file = write_output_per_league(
                output_dir, league_records, league_name, now_str
            )
            if out_file:
                out_files.append(out_file)

        # ------------------------------------------------------------------
        # Write Transfer News to dedicated file: transfer_news_{YYYYMMDDhh}.txt
        # ------------------------------------------------------------------
        if transfer_records:
            transfer_out = write_output_per_league(
                output_dir, transfer_records, "transfer_news", now_str
            )
            if transfer_out:
                out_files.append(transfer_out)
                print(f"[TRANSFER] Written -> {transfer_out}  ({len(transfer_records)} URLs)")
        else:
            print("[TRANSFER] No transfer news URLs captured this run.")

        save_cursor(cursor_path, updated_cursor)

        print(f"\n{'='*60}")
        print(f"Capture complete.  {len(all_records) + len(transfer_records)} total URLs from {len(sources)} sources.")
        print(f"Files written : {len(out_files)}")
        for f in out_files:
            print(f"  -> {f}")
        print(f"Cursor  : {cursor_path}")
        print(f"{'='*60}\n")
    finally:
        await close_browser()


def main() -> None:
    config = load_config()
    asyncio.run(run_capture(config))


if __name__ == "__main__":
    main()
