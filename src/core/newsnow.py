import asyncio
import random
import re
import urllib.request
from dataclasses import dataclass
from html import unescape
from typing import Optional
from urllib.parse import urlparse, urlunparse
from urllib.request import Request
from src.core.errors import CrawlStageError


class IPBlockedError(Exception):
    """Raised when the remote host refuses to respond (WinError 10060 / IP blocked)."""
    def __init__(self, tracker_url: str, original: Exception):
        super().__init__(f"IP blocked for {tracker_url}: {original}")
        self.tracker_url = tracker_url
        self.original = original


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Do not follow redirects

# Static opener: does NOT follow HTTP redirects, so we read tracker HTML directly
_TRACKER_OPENER = urllib.request.build_opener(_NoRedirectHandler)

TRACKER_URL_RE = re.compile(r"url:\s*'([^']+)'", re.S)
REDIRECT_DELAY_RE = re.compile(r"delay:\s*(\d+)", re.S)
MANUAL_REDIRECT_RE = re.compile(r"manualRedirect:\s*(true|false)", re.S | re.I)
OG_TITLE_RE = re.compile(r'<meta\s+property="og:title"\s+content="([^"]*)"', re.I)
OG_IMAGE_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]*)"', re.I)
TRACKER_ARTICLE_ID_RE = re.compile(r"/A/(\d+)")


@dataclass(slots=True)
class TrackerResolutionResult:
    tracker_url: str
    final_url: Optional[str]
    tracker_article_id: Optional[str]
    redirect_delay_ms: Optional[int]
    manual_redirect: Optional[bool]
    tracker_og_title: Optional[str]
    tracker_og_image: Optional[str]
    used_browser_fallback: bool = False


def normalize_url(url: str | None) -> str | None:
    """Normalizes a URL for dedup checks without changing its meaning.
    Preserves the original http or https scheme.
    """
    if not url:
        return None

    parsed = urlparse(url.strip())
    if not parsed.scheme or not parsed.netloc:
        return url.strip()

    normalized_path = parsed.path.rstrip("/") or "/"
    normalized_netloc = parsed.netloc.lower()
    # Keep original scheme (http or https) – do not force-upgrade.
    normalized_scheme = parsed.scheme.lower()
    return urlunparse(
        (
            normalized_scheme,
            normalized_netloc,
            normalized_path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def parse_tracker_html(tracker_url: str, html: str) -> TrackerResolutionResult:
    """Parses the NewsNow tracker HTML and extracts redirect metadata."""
    final_url_match = TRACKER_URL_RE.search(html)
    redirect_delay_match = REDIRECT_DELAY_RE.search(html)
    manual_redirect_match = MANUAL_REDIRECT_RE.search(html)
    og_title_match = OG_TITLE_RE.search(html)
    og_image_match = OG_IMAGE_RE.search(html)
    tracker_article_id_match = TRACKER_ARTICLE_ID_RE.search(tracker_url)

    manual_redirect = None
    if manual_redirect_match:
        manual_redirect = manual_redirect_match.group(1).lower() == "true"

    redirect_delay_ms = None
    if redirect_delay_match:
        redirect_delay_ms = int(redirect_delay_match.group(1))

    final_url = None
    if final_url_match:
        final_url = normalize_url(unescape(final_url_match.group(1)))

    return TrackerResolutionResult(
        tracker_url=tracker_url,
        final_url=final_url,
        tracker_article_id=tracker_article_id_match.group(1) if tracker_article_id_match else None,
        redirect_delay_ms=redirect_delay_ms,
        manual_redirect=manual_redirect,
        tracker_og_title=unescape(og_title_match.group(1)) if og_title_match else None,
        tracker_og_image=unescape(og_image_match.group(1)) if og_image_match else None,
    )


def _fetch_tracker_html_sync(tracker_url: str, timeout_ms: int) -> str:
    """Fetch the NewsNow tracker page WITHOUT following HTTP redirects.

    The tracker subdomain (c.newsnow.co.uk) does not have Cloudflare protection,
    so plain urllib works reliably here. Using _NoRedirectHandler ensures we read
    the raw tracker HTML (which contains clickthroughConfig) instead of being
    redirected to the final article page.
    """
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    ]
    request = Request(
        tracker_url,
        headers={"User-Agent": random.choice(user_agents)},
    )
    with _TRACKER_OPENER.open(request, timeout=max(timeout_ms / 1000, 1)) as response:
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        charset = "utf-8"
        if "charset=" in content_type:
            charset = content_type.split("charset=")[-1].strip().split(";")[0].strip()
        return raw.decode(charset, errors="replace")


# Semaphore: allow up to 5 parallel tracker fetches (urllib is lightweight)
_TRACKER_SEMAPHORE = asyncio.Semaphore(5)

async def resolve_newsnow_tracker_url(
    tracker_url: str,
    timeout_ms: int = 15000,
    retries: int = 3,
) -> TrackerResolutionResult:
    """Resolves a NewsNow tracker URL to the final article URL using urllib."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with _TRACKER_SEMAPHORE:
                tracker_html = await asyncio.to_thread(
                    _fetch_tracker_html_sync, tracker_url, timeout_ms
                )
            resolution = parse_tracker_html(tracker_url, tracker_html)
            return resolution
        except Exception as exc:  # pragma: no cover - network error path
            # WinError 10060 = connection timeout → IP bị block, không retry
            if "WinError 10060" in str(exc) or "10060" in str(exc):
                print(f"Tracker resolution attempt {attempt}/{retries} failed for {tracker_url}: {exc}")
                raise IPBlockedError(tracker_url, exc) from exc
            last_error = exc
            print(f"Tracker resolution attempt {attempt}/{retries} failed for {tracker_url}: {exc}")
            if attempt < retries:
                # Exponential backoff: 2s, 4s, ...
                await asyncio.sleep(2 ** attempt)

    raise CrawlStageError(
        stage="tracker_resolution",
        code="TRACKER_RESOLUTION_FAILED",
        message=f"Failed to resolve tracker URL after {retries} attempts.",
        context={"tracker_url": tracker_url},
    ) from last_error
