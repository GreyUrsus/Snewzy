"""Snewzy - Main entry point."""

import os
import re
import subprocess
import sys
from .modules.config_loader import load_config
from .modules.database import init_database
from .modules.fetcher import run_fetcher
from .modules.summarizer import run_summarizer
from .modules.display import run_display
from .modules.exporter import export_for_website


CLOUDFLARE_ENV_FILE = os.path.expanduser("~/.snewzy_env")
WEBSITE_DEPLOY_DIR = "/mnt/artifacts/grey_ursus_consulting/website"
DEPLOY_TIMEOUT_SECONDS = 120


def _read_cloudflare_token(env_path=CLOUDFLARE_ENV_FILE):
    """Read CLOUDFLARE_API_TOKEN from the env file at runtime.

    Returns the token string, or raises ValueError/OSError describing
    why it could not be read. Never hardcodes a token in source.
    """
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "CLOUDFLARE_API_TOKEN":
                token = value.strip().strip('"').strip("'")
                if token:
                    return token
                raise ValueError("CLOUDFLARE_API_TOKEN is present but empty")
    raise ValueError("CLOUDFLARE_API_TOKEN not found in " + env_path)


def _deploy_to_cloudflare():
    """Deploy the website via `wrangler deploy`.

    Returns a dict: {"success": bool, "url": str | None, "error": str | None}
    Never raises - failures are reported for the caller to log, but must
    not affect the success of the local export step.
    """
    try:
        token = _read_cloudflare_token()
    except (OSError, ValueError) as e:
        return {"success": False, "url": None, "error": f"Could not load CLOUDFLARE_API_TOKEN: {e}"}

    deploy_env = os.environ.copy()
    deploy_env["CLOUDFLARE_API_TOKEN"] = token

    try:
        result = subprocess.run(
            ["wrangler", "deploy"],
            cwd=WEBSITE_DEPLOY_DIR,
            env=deploy_env,
            capture_output=True,
            text=True,
            timeout=DEPLOY_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "url": None,
            "error": f"wrangler deploy timed out after {DEPLOY_TIMEOUT_SECONDS}s",
        }
    except FileNotFoundError as e:
        return {"success": False, "url": None, "error": f"wrangler CLI not found: {e}"}
    except Exception as e:
        return {"success": False, "url": None, "error": f"Unexpected error running wrangler: {e}"}

    if result.returncode != 0:
        return {
            "success": False,
            "url": None,
            "error": (result.stderr or result.stdout or "unknown error").strip(),
        }

    url_match = re.search(r"https?://\S+", result.stdout or "")
    return {"success": True, "url": url_match.group(0) if url_match else None, "error": None}


def fetch_and_summarize():
    """Run fetcher and summarizer (background tasks)."""
    print("=" * 50)
    print("SNEWZY - Background Update")
    print("=" * 50)
    
    # Load config
    print("\n[1/6] Loading configuration...")
    try:
        config = load_config()
        print(f"  ✓ Loaded {len(config.whitelist_sites)} sites")
    except Exception as e:
        print(f"  ✗ Config error: {e}")
        return
    
    # Init database
    print("\n[2/6] Initializing database...")
    try:
        init_database()
        print("  ✓ Database ready")
    except Exception as e:
        print(f"  ✗ Database error: {e}")
        return
    
    # Fetch articles
    print("\n[3/6] Fetching articles...")
    try:
        results = run_fetcher(config)
        print(f"  ✓ Added {results['added']} new articles")
    except Exception as e:
        print(f"  ✗ Fetch failed: {e}")
    
    # Summarize
    print("\n[4/6] Summarizing...")
    try:
        results = run_summarizer(config, max_per_priority=5)
        print(f"  ✓ Summarized {results['succeeded']} articles")
    except Exception as e:
        print(f"  ✗ Summarization failed: {e}")
    
    # Export latest summarized articles for the website
    print("\n[5/6] Exporting for website...")
    export_succeeded = False
    try:
        export_results = export_for_website()
        export_succeeded = True
        print(
            f"  ✓ Exported {export_results['breaking']} breaking, "
            f"{export_results['general']} general articles"
        )
    except Exception as e:
        print(f"  ✗ Export failed: {e}")
    
    # Deploy the updated website to Cloudflare (best-effort; never fails the cycle)
    print("\n[6/6] Deploying to Cloudflare...")
    try:
        deploy_result = _deploy_to_cloudflare()
        if deploy_result["success"]:
            if deploy_result["url"]:
                print(f"  ✓ Deploy succeeded: {deploy_result['url']}")
            else:
                print("  ✓ Deploy succeeded")
        else:
            if export_succeeded:
                print("  ⚠ Local update succeeded, remote deploy failed")
            else:
                print("  ⚠ Remote deploy failed (local export also failed)")
            print(f"  ✗ Deploy error: {deploy_result['error']}")
    except Exception as e:
        # Defensive: _deploy_to_cloudflare should not raise, but never let a
        # deploy problem crash the overall update cycle.
        if export_succeeded:
            print("  ⚠ Local update succeeded, remote deploy failed")
        else:
            print("  ⚠ Remote deploy failed (local export also failed)")
        print(f"  ✗ Deploy error: unexpected exception: {e}")
    
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