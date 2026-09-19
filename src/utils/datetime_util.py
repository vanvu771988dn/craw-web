# src/utils/datetime_util.py

from datetime import datetime

COMMON_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S%z",
)

def parse_date(date_string: str) -> datetime | None:
    """
    Parses a date string from the page into a datetime object.
    Handles multiple common formats.
    """
    if not date_string:
        return None

    normalized = date_string.strip()
    if not normalized:
        return None

    iso_candidate = normalized.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate)
    except ValueError:
        pass

    for fmt in COMMON_DATE_FORMATS:
        try:
            return datetime.strptime(normalized, fmt)
        except ValueError:
            continue

    return None
