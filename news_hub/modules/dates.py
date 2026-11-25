"""Date helpers - turn the many date formats RSS/Atom feeds use into one.

Why this exists:
    Feeds send dates as plain text in different styles, for example
    "Wed, 25 Mar 2026 10:00:00 +0000" (RSS) or "2026-04-29T08:15:00Z" (Atom).
    Snewzy used to store that raw text and then sort it with
    ORDER BY published_date DESC. SQLite sorts text alphabetically, so
    "Wed, 25 Mar" landed above "Wed, 24 Jun" and old stories showed first.

    Storing every date as ISO 8601 in UTC ("2026-04-29T08:15:00+00:00")
    makes alphabetical order the same as time order, so the existing
    ORDER BY works without any other change.
"""

import calendar
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional


def struct_time_to_iso(parsed) -> Optional[str]:
    """Convert feedparser's *_parsed value (a UTC time.struct_time) to ISO text.

    feedparser already normalises every date it understands to UTC and puts it
    in entry.published_parsed / entry.updated_parsed, so this is the most
    reliable source when it is present.
    """
    if not parsed:
        return None
    try:
        # calendar.timegm treats the struct as UTC (time.mktime would use local time)
        seconds = calendar.timegm(parsed)
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def text_to_iso(raw: Optional[str]) -> Optional[str]:
    """Best-effort conversion of a raw feed date string to ISO 8601 UTC text.

    Handles RFC 822 style ("Wed, 25 Mar 2026 10:00:00 +0000") and ISO style
    ("2026-04-29T08:15:00Z"). Returns None when the text can't be understood,
    so the caller can decide on a fallback.
    """
    if not raw:
        return None
    raw = raw.strip()

    # 1) ISO 8601 (Atom feeds). Python 3.11+ accepts a trailing "Z".
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except ValueError:
        pass

    # 2) RFC 822 / RFC 2822 (classic RSS feeds)
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, IndexError):
        return None


def entry_published_iso(entry) -> str:
    """Pick the best publish date for a feed entry, always returning ISO text.

    Order of preference:
      1. published_parsed (feedparser's normalised publish date)
      2. updated_parsed   (some feeds only send an "updated" date)
      3. the raw "published"/"updated" text, parsed ourselves
      4. right now, so the article still sorts sensibly instead of vanishing
    """
    for key in ("published_parsed", "updated_parsed"):
        iso = struct_time_to_iso(entry.get(key))
        if iso:
            return iso

    for key in ("published", "updated"):
        iso = text_to_iso(entry.get(key))
        if iso:
            return iso

    return datetime.now(timezone.utc).isoformat()


def is_iso(text: Optional[str]) -> bool:
    """True when text already looks like the ISO format this module writes."""
    return bool(text) and len(text) >= 10 and text[:4].isdigit() and text[4] == "-"
