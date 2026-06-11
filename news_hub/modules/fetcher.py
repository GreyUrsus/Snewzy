"""Fetcher module - downloads and processes RSS feeds."""

import feedparser
from typing import List, Tuple, Dict
from datetime import datetime
from .database import insert_article, article_exists
from .config_loader import AppConfig, SiteConfig, KeywordsConfig



def fetch_feed(url: str) -> List[dict]:
    """Download and parse an RSS feed.

    Args:
        url: The RSS feed URL to fetch

    Returns:
        List of article dictionaries from the feed
    """
    try:
        parsed = feedparser.parse(url)
        return parsed.entries
    except Exception as e:
        print(f"Error fetching feed {url}: {e}")
    return []

def calculate_priority(title: str, content: str, keywords) -> int:
    """Determine article priority based on keyword matches."""
    text = (title + " " + content).lower()

    for keyword in keywords.priority_1:
        if keyword.lower() in text:
            return 1
    
    for keyword in keywords.priority_2:
        if keyword.lower() in text:
            return 2
    
    for keyword in keywords.priority_3:
        if keyword.lower() in text:
            return 3
    
    return 3

def process_site(site: SiteConfig, keywords, max_articles: int) -> Tuple[int, int]:
    """Process a single news site.

    Args:
        site: SiteConfig with RSS URL and metadata
        keywords: KeywordsConfig for priority calculation
        max_articles: Maximum articles to process from this site

    Returns:
        Tuple of (articles_added, articles_skipped)
    """
    print(f"  Fetching from {site.name}...")
    entries = fetch_feed(site.rss_url)

    added = 0
    skipped = 0

    for entry in entries[:max_articles]:
        title = entry.get("title", "No Title")
        url = entry.get("link", "")
        published = entry.get("published", "")
        content = entry.get("summary", "") or entry.get("description", "")
        
        if not url:
            continue
        if article_exists(url):
            skipped += 1
            continue
        if site.priority_boost:
            priority = 1
        else:
            priority = calculate_priority(title, content, keywords)

        inserted = insert_article(
            title=title,
            source=site.name,
            url=url,
            published_date=published,
            content=content,
            priority=priority
        )

        if inserted:
            added += 1
    return added, skipped

def run_fetcher(config: AppConfig)-> dict:
    """Main entry point - fetchs from all configured sites.

    Args:
        config: AppConfig with sites, keywords, and settings

    Returns:
        dict with statistics: total sites, articles added, articles skipped
    """
    stats = {"sites": 0, "added": 0, "skipped": 0}

    for site in config.whitelist_sites:
        stats["sites"] += 1
        added, skipped, = process_site(
            site,
            config.keywords,
            config.settings.max_articles_per_scan
        )
        stats["added"] += added
        stats["skipped"] += skipped
    return stats


#Test code
if __name__ == "__main__":
    from .config_loader import load_config

    config = load_config()
    results = run_fetcher(config)
    print(f"\nFetch complete!")
    print(f"Sites processed: {results['sites']}")
    print(f"Articles added: {results['added']}")
    print(f"Articles skipped: {results['skipped']}")