"""Exporter module - writes summarized articles to a static JSON file for website consumption.

This module is the final step in the fetch/summarize pipeline. It reads the
top breaking-news and general-news articles that have already been
summarized and dumps them, in a stable flat schema, to a fixed output path
so a downstream static site (or any other consumer) can read the latest
news without touching the SQLite database directly.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .database import get_articles_by_priority

# Fixed output location: the Grey Ursus Consulting website's data folder,
# so the static site (website/js/news-panels.js) reads the same file this
# module writes. The Snewzy project and the website are sibling directories
# under grey_ursus_consulting/, e.g.:
#   grey_ursus_consulting/Snewzy/news_hub/modules/exporter.py  (this file)
#   grey_ursus_consulting/website/data/latest_news.json        (export target)
# A local fallback under <project_root>/output/ is also written so the
# pipeline still produces output if the website directory isn't present
# (e.g. in a dev/test checkout of Snewzy alone).
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_WEBSITE_DATA_DIR = _PROJECT_ROOT.parent / "website" / "data"
_LOCAL_FALLBACK_DIR = _PROJECT_ROOT / "output"

OUTPUT_PATH = (
    _WEBSITE_DATA_DIR / "latest_news.json"
    if _WEBSITE_DATA_DIR.parent.exists()
    else _LOCAL_FALLBACK_DIR / "latest_news.json"
)

# How many days back the export reaches when no config is passed in.
DEFAULT_MAX_AGE_DAYS = 7


def resolve_output_path(website_dir: str = "") -> Path:
    """Work out where latest_news.json should be written.

    If config.json sets settings.website_dir, write into <website_dir>/data/
    (the same folder main.py deploys). Otherwise keep the original
    behaviour stored in OUTPUT_PATH.
    """
    if website_dir:
        return Path(website_dir).expanduser() / "data" / "latest_news.json"
    return OUTPUT_PATH

# Row indices for the `articles` table as returned by get_articles_by_priority:
# (id, title, source, url, published_date, content, summary, bullet_points, priority, status, created_at)
_IDX_TITLE = 1
_IDX_SOURCE = 2
_IDX_URL = 3
_IDX_PUBLISHED_DATE = 4
_IDX_SUMMARY = 6


def _article_row_to_dict(row: Tuple, tier: str) -> Dict[str, Any]:
    """Convert a raw articles-table row into the flat export schema.

    Args:
        row: A single article row as returned by get_articles_by_priority,
            in column order (id, title, source, url, published_date,
            content, summary, bullet_points, priority, status, created_at).
        tier: The export tier label for this article, either "breaking"
            or "general".

    Returns:
        A dict with the fixed export fields: title, source, url,
        published_date, summary, tier.
    """
    return {
        "title": row[_IDX_TITLE],
        "source": row[_IDX_SOURCE],
        "url": row[_IDX_URL],
        "published_date": row[_IDX_PUBLISHED_DATE],
        "summary": row[_IDX_SUMMARY],
        "tier": tier,
    }


def export_for_website(config: Optional[Any] = None) -> Dict[str, int]:
    """Export the latest summarized breaking and general news to a JSON file.

    Queries priority-1 ("breaking") articles with status "summarized"
    (limit 3) and priority-2 ("general") articles with status
    "summarized" (limit 5), maps each to a flat dict of
    {title, source, url, published_date, summary, tier}, and writes the
    combined list to OUTPUT_PATH, fully overwriting any previous content.

    Only articles published in the last `export_max_age_days` days are
    included, so the website never shows months-old "Breaking News".

    Alongside latest_news.json it writes latest_news_meta.json with the time
    of this export, so the website can show a "Last updated" line. (The main
    file keeps its existing list format, so the site's current script keeps
    working unchanged.)

    Args:
        config: Optional AppConfig. Used for settings.export_max_age_days and
            settings.website_dir; defaults apply when it's missing.

    Returns:
        A dict summarizing the export, e.g. {"breaking": 3, "general": 5},
        with counts of articles actually written per tier.
    """
    settings = getattr(config, "settings", None)
    max_age_days = getattr(settings, "export_max_age_days", DEFAULT_MAX_AGE_DAYS)
    website_dir = getattr(settings, "website_dir", "")
    output_path = resolve_output_path(website_dir)

    # Cut-off as ISO 8601 UTC text, comparable with the stored published_date.
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=max_age_days)).isoformat()

    breaking_rows = get_articles_by_priority(
        1, status="summarized", limit=3, published_after=cutoff
    )
    general_rows = get_articles_by_priority(
        2, status="summarized", limit=5, published_after=cutoff
    )

    articles: List[Dict[str, Any]] = []
    articles.extend(_article_row_to_dict(row, "breaking") for row in breaking_rows)
    articles.extend(_article_row_to_dict(row, "general") for row in general_rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Overwrite completely on every run - "w" mode truncates any existing file.
    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(articles, output_file, indent=2, ensure_ascii=False)

    # Small companion file: when this export ran and how far back it looked.
    meta_path = output_path.with_name("latest_news_meta.json")
    with open(meta_path, "w", encoding="utf-8") as meta_file:
        json.dump(
            {
                "updated_at": now.isoformat(),
                "max_age_days": max_age_days,
                "breaking": len(breaking_rows),
                "general": len(general_rows),
            },
            meta_file,
            indent=2,
        )

    return {"breaking": len(breaking_rows), "general": len(general_rows)}
