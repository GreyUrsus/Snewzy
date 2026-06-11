"""Snewzy - Main entry point."""

import sys
from .modules.config_loader import load_config
from .modules.database import init_database
from .modules.fetcher import run_fetcher
from .modules.summarizer import run_summarizer
from .modules.display import run_display


def fetch_and_summarize():
    """Run fetcher and summarizer (background tasks)."""
    print("=" * 50)
    print("SNEWZY - Background Update")
    print("=" * 50)
    
    # Load config
    print("\n[1/4] Loading configuration...")
    try:
        config = load_config()
        print(f"  ✓ Loaded {len(config.whitelist_sites)} sites")
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return
    
    # Init database
    print("\n[2/4] Initializing database...")
    try:
        init_database()
        print("  ✓ Database ready")
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return
    
    # Fetch articles
    print("\n[3/4] Fetching articles...")
    try:
        results = run_fetcher(config)
        print(f"  ✓ Added {results['added']} new articles")
    except Exception as e:
        print(f"  ✗ Fetch failed: {e}")
    
    # Summarize
    print("\n[4/4] Summarizing...")
    try:
        results = run_summarizer(config, max_per_priority=5)
        print(f"  ✓ Summarized {results['succeeded']} articles")
    except Exception as e:
        print(f"  ✗ Summarization failed: {e}")
    
    print("\n" + "=" * 50)
    print("Update complete!")
    print("=" * 50)


def main():
    """Main entry - supports CLI and GUI modes."""
    if len(sys.argv) > 1 and sys.argv[1] == "--update":
        # Background update mode
        fetch_and_summarize()
    else:
        # GUI mode (default)
        print("Starting Snewzy GUI...")
        print("Use --update flag to fetch/summarize from command line")
        run_display()


if __name__ == "__main__":
    main()