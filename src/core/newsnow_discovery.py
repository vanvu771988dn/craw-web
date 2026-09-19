import asyncio
import json
import re
from dataclasses import dataclass
from html import unescape
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from src.core.errors import CrawlStageError
from src.core.newsnow import TRACKER_ARTICLE_ID_RE, normalize_url
from src.utils.file_logger import log_structured_event

MNID_RE = re.compile(r'"mnid":\s*\'(\d+)\'')
NLID_RE = re.compile(r'"nlid":\s*\'(\d+)\'')
NFP_RE = re.compile(r'"nfp":\s*\'([^\']+)\'')
STIM_RE = re.compile(r'"sTim":\s*\'([^\']+)\'')
TRACKER_URL_RE = re.compile(r'https://c\.newsnow\.co\.uk/A/\d+\?(?:`d|-)\d+:\d+')
FIELD_RE_TEMPLATE = r'"{field}":"([^"]*)"'
INVALID_TITLE_PATTERNS = (
    "https://",
    "c.newsnow.co.uk",
    'a/',
    'pubid',
    'timestamp',
    'clickcontext',
)
INVALID_SOURCE_PATTERNS = (
    "https://",
    "c.newsnow.co.uk",
    "timestamp",
    "clickcontext",
)


@dataclass(slots=True)
class NewsNowPageContext:
    start_url: str
    mnid: int
    nlid: int
    path: str
    stim: str
    quantity: int = 40
    abstractname: str = "105"
    pagetype: str = "203"


@dataclass(slots=True)
class DiscoveredArticle:
    list_page_url: str
    tracker_url: str
    grid_title: Optional[str]
    grid_source: Optional[str]
    grid_time_text: Optional[str]
    grid_position: int
    tracker_article_id: Optional[str]
    timestamp: Optional[str]
    access: Optional[str] = None


def ensure_latest_newsnow_url(start_url: str) -> str:
    """Normalizes a NewsNow URL to the Latest tab because the crawler strategy is latest-feed specific."""
    parsed = urlparse(start_url)
    if "newsnow.co.uk" not in parsed.netloc:
        return start_url

    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["type"] = "ln"
    normalized_query = urlencode(query)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, normalized_query, parsed.fragment))


def _decode_newsnow_text(value: str | None) -> str | None:
    if value is None:
        return None
    decoded = value.replace("_", " ").replace("`d", "&")
    decoded = decoded.replace("`t", " ").replace("`u{", " ").replace("`}", " ")
    decoded = " ".join(decoded.split())
    return unescape(decoded).strip() or None


def _is_reasonable_title(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    if len(normalized) < 12:
        return False
    return not any(pattern in normalized for pattern in INVALID_TITLE_PATTERNS)


def _is_reasonable_source(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    if len(normalized) < 3:
        return False
    return not any(pattern in normalized for pattern in INVALID_SOURCE_PATTERNS)


def _pick_preferred_metadata_value(local_value: str | None, indexed_value: str | None, *, kind: str) -> str | None:
    if kind == "title":
        if _is_reasonable_title(local_value):
            return local_value
        if _is_reasonable_title(indexed_value):
            return indexed_value
        return local_value or indexed_value

    if _is_reasonable_source(local_value):
        return local_value
    if _is_reasonable_source(indexed_value):
        return indexed_value
    return local_value or indexed_value


def build_newsnow_page_context(start_url: str, html: str, quantity: int = 40) -> NewsNowPageContext:
    mnid_match = MNID_RE.search(html)
    nlid_match = NLID_RE.search(html)
    path_match = NFP_RE.search(html)
    stim_match = STIM_RE.search(html)

    if not (mnid_match and nlid_match and path_match and stim_match):
        raise CrawlStageError(
            stage="discovery",
            code="NEWSNOW_CONTEXT_PARSE_FAILED",
            message="Failed to parse NewsNow page context from initial HTML.",
            context={"start_url": start_url},
        )

    return NewsNowPageContext(
        start_url=start_url,
        mnid=int(mnid_match.group(1)),
        nlid=int(nlid_match.group(1)),
        path=path_match.group(1),
        stim=stim_match.group(1),
        quantity=quantity,
    )


def parse_initial_newsnow_batch(start_url: str, html: str) -> list[DiscoveredArticle]:
    soup = BeautifulSoup(html, "html.parser")
    articles: list[DiscoveredArticle] = []

    for index, row in enumerate(soup.select("div.newsfeed div.hl"), start=1):
        link = row.select_one("a.hll[href*='https://c.newsnow.co.uk/A/']")
        if not link:
            continue

        tracker_url = normalize_url(link.get("href"))
        source = row.select_one(".meta .src")
        time_node = row.select_one(".meta .time")
        tracker_article_id_match = TRACKER_ARTICLE_ID_RE.search(tracker_url or "")

        articles.append(
            DiscoveredArticle(
                list_page_url=start_url,
                tracker_url=tracker_url or "",
                grid_title=" ".join(link.get_text(" ", strip=True).split()) or None,
                grid_source=" ".join(source.get_text(" ", strip=True).split()) if source else None,
                grid_time_text=" ".join(time_node.get_text(" ", strip=True).split()) if time_node else None,
                grid_position=index,
                tracker_article_id=tracker_article_id_match.group(1) if tracker_article_id_match else row.get("data-id"),
                timestamp=time_node.get("data-time") if time_node else None,
            )
        )

    log_structured_event(
        "discovery",
        "initial_batch_parsed",
        start_url=start_url,
        discovered=len(articles),
    )
    return articles


def _build_articles_request_payload(context: NewsNowPageContext, cursor_article_id: str, cursor_ts: str) -> dict:
    page_descriptor = json.dumps(
        [
            "NNv5::Page::News",
            {
                "_ValidPath": 1,
                "abstractname": context.abstractname,
                "extra_query": {},
                "mnid": context.mnid,
                "pageno": 0,
                "pagetype": context.pagetype,
                "path": context.path,
            },
        ],
        separators=(",", ":"),
    )
    return {
        "page": page_descriptor,
        "type": "ln",
        "article_id": cursor_article_id,
        "ts": cursor_ts,
        "tr_mnids": [],
        "tr_searches": [],
        "quantity": context.quantity,
        "stim": context.stim,
        "UseAlternativeTheme": False,
        "tt_output": "default",
        "force_clustering": False,
    }


def _post_newsnow_articles_sync(context: NewsNowPageContext, cursor_article_id: str, cursor_ts: str, timeout_ms: int) -> tuple[str, dict]:
    payload = _build_articles_request_payload(context, cursor_article_id, cursor_ts)
    encoded_form = urlencode({"data": json.dumps(payload, separators=(",", ":"))}).encode("utf-8")
    request = Request(
        "https://www.newsnow.co.uk/h/app/v1/articles",
        data=encoded_form,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": "https://www.newsnow.co.uk",
            "Referer": context.start_url,
        },
        method="POST",
    )
    with urlopen(request, timeout=max(timeout_ms / 1000, 1)) as response:
        raw = response.read().decode("utf-8", errors="replace")
    return raw, payload


def parse_newsnow_articles_response(start_url: str, encoded_response: str, position_offset: int = 0) -> list[DiscoveredArticle]:
    try:
        response_wrapper = json.loads(encoded_response)
    except json.JSONDecodeError as exc:
        raise CrawlStageError(
            stage="discovery",
            code="NEWSNOW_RESPONSE_NOT_JSON",
            message="NewsNow articles response was not valid JSON.",
            context={"start_url": start_url},
        ) from exc

    encoded_data = response_wrapper.get("data")
    if not isinstance(encoded_data, str):
        raise CrawlStageError(
            stage="discovery",
            code="NEWSNOW_RESPONSE_DATA_MISSING",
            message="NewsNow articles response did not contain an encoded data string.",
            context={"start_url": start_url},
        )

    url_matches = list(TRACKER_URL_RE.finditer(encoded_data))
    timestamp_values = re.findall(FIELD_RE_TEMPLATE.format(field="timestamp"), encoded_data)
    title_values = re.findall(FIELD_RE_TEMPLATE.format(field="title"), encoded_data)
    pub_name_values = re.findall(FIELD_RE_TEMPLATE.format(field="pubName"), encoded_data)
    access_values = re.findall(FIELD_RE_TEMPLATE.format(field="access"), encoded_data)
    articles: list[DiscoveredArticle] = []
    for index, match in enumerate(url_matches, start=1):
        tracker_url = normalize_url(match.group(0))
        window_start = max(0, match.start() - 1000)
        window_end = min(len(encoded_data), match.end() + 800)
        window = encoded_data[window_start:window_end]
        before = encoded_data[window_start:match.start()]
        after = encoded_data[match.end():window_end]

        title_matches = re.findall(FIELD_RE_TEMPLATE.format(field="title"), before)
        if not title_matches:
            title_matches = re.findall(FIELD_RE_TEMPLATE.format(field="title"), window)
        pub_name_matches = re.findall(FIELD_RE_TEMPLATE.format(field="pubName"), before)
        if not pub_name_matches:
            pub_name_matches = re.findall(FIELD_RE_TEMPLATE.format(field="pubName"), window)
        time_matches = re.findall(FIELD_RE_TEMPLATE.format(field="timestamp"), after)
        if not time_matches:
            time_matches = re.findall(FIELD_RE_TEMPLATE.format(field="timestamp"), window)
        access_matches = re.findall(FIELD_RE_TEMPLATE.format(field="access"), window)
        id_matches = re.findall(FIELD_RE_TEMPLATE.format(field="id"), after)
        if not id_matches:
            id_matches = re.findall(FIELD_RE_TEMPLATE.format(field="id"), window)

        tracker_article_id_match = TRACKER_ARTICLE_ID_RE.search(tracker_url or "")
        article_id = tracker_article_id_match.group(1) if tracker_article_id_match else (id_matches[0] if id_matches else None)
        title = _decode_newsnow_text(title_matches[-1]) if title_matches else None
        pub_name = _decode_newsnow_text(pub_name_matches[-1]) if pub_name_matches else None
        indexed_timestamp = timestamp_values[index - 1] if len(timestamp_values) >= index else None
        indexed_title = _decode_newsnow_text(title_values[index - 1]) if len(title_values) >= index else None
        indexed_pub_name = _decode_newsnow_text(pub_name_values[index - 1]) if len(pub_name_values) >= index else None
        indexed_access = _decode_newsnow_text(access_values[index - 1]) if len(access_values) >= index else None

        timestamp = indexed_timestamp or (time_matches[0] if time_matches else None)
        access = _decode_newsnow_text(access_matches[0]) if access_matches else indexed_access
        title = _pick_preferred_metadata_value(title, indexed_title, kind="title")
        pub_name = _pick_preferred_metadata_value(pub_name, indexed_pub_name, kind="source")

        articles.append(
            DiscoveredArticle(
                list_page_url=start_url,
                tracker_url=tracker_url or "",
                grid_title=title,
                grid_source=pub_name,
                grid_time_text=timestamp,
                grid_position=position_offset + index,
                tracker_article_id=article_id,
                timestamp=timestamp,
                access=access,
            )
        )

    log_structured_event(
        "discovery",
        "backend_batch_parsed",
        start_url=start_url,
        discovered=len(articles),
        position_offset=position_offset,
    )
    return articles


async def fetch_newsnow_articles_batch(
    context: NewsNowPageContext,
    cursor_article_id: str,
    cursor_ts: str,
    timeout_ms: int = 30000,
    position_offset: int = 0,
    retries: int = 2,
) -> list[DiscoveredArticle]:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            raw_response, payload = await asyncio.to_thread(
                _post_newsnow_articles_sync,
                context,
                cursor_article_id,
                cursor_ts,
                timeout_ms,
            )
            log_structured_event(
                "discovery",
                "backend_batch_requested",
                start_url=context.start_url,
                cursor_article_id=cursor_article_id,
                cursor_ts=cursor_ts,
                quantity=context.quantity,
                payload=payload,
                attempt=attempt,
                retries=retries,
            )
            return parse_newsnow_articles_response(context.start_url, raw_response, position_offset=position_offset)
        except CrawlStageError:
            raise
        except Exception as exc:
            last_error = exc
            log_structured_event(
                "discovery",
                "backend_batch_retry",
                start_url=context.start_url,
                cursor_article_id=cursor_article_id,
                cursor_ts=cursor_ts,
                attempt=attempt,
                retries=retries,
                error=str(exc),
            )

    raise CrawlStageError(
        stage="discovery",
        code="NEWSNOW_BACKEND_BATCH_FAILED",
        message="Failed to fetch or parse a NewsNow backend article batch.",
        context={
            "start_url": context.start_url,
            "cursor_article_id": cursor_article_id,
            "cursor_ts": cursor_ts,
        },
    ) from last_error
