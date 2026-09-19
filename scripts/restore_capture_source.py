"""Restore capture_source between extract_initial_articles and write_output_txt."""

CAPTURE_SOURCE = '''

async def capture_source(
    source_url: str,
    league: str,
    time_window_hours: float,
    cursor: dict,
) -> tuple[list[dict], dict | None]:

    url = ensure_latest_newsnow_url(source_url)
    source_cursor = cursor.get(league, {})
    cursor_ts: str | None = source_cursor.get("timestamp")

    print(f"\\n{\'=\'*60}")
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

    async def process_batch(batch):
        nonlocal newest_article
        stop = False

        for article in batch:
            if newest_article is None:
                newest_article = article

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
            try:
                resolution = await resolve_newsnow_tracker_url(
                    article.tracker_url, timeout_ms=TIMEOUT_S * 1000, retries=2
                )
                final_url = normalize_url(resolution.final_url) if resolution else None
            except Exception as exc:
                print(f"[{league}] [!] Resolve failed ({article.tracker_url}): {exc}")
                final_url = None

            if not final_url:
                print(f"[{league}] [-] Could not resolve -> {article.tracker_url}")
                continue

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
            try:
                next_batch = await fetch_newsnow_articles_batch(
                    page_context,
                    cursor_article_id=last.tracker_article_id,
                    cursor_ts=last.timestamp,
                    timeout_ms=TIMEOUT_S * 1000,
                    position_offset=position_offset,
                    retries=2,
                )
            except Exception as exc:
                print(f"[{league}] [!] Backend batch failed: {exc}")
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

'''

path = "src/url_capture.py"
content = open(path, encoding="utf-8").read()

# Insert capture_source before write_output_txt
insert_marker = "\ndef write_output_txt("
idx = content.find(insert_marker)
if idx == -1:
    print("ERROR: marker not found!")
else:
    new_content = content[:idx] + CAPTURE_SOURCE + content[idx:]
    open(path, "w", encoding="utf-8").write(new_content)
    print(f"Done! Inserted capture_source at index {idx}")
    print(f"New file size: {len(new_content)} chars")
