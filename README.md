# Snewzy — Local LLM News Pipeline

Automated news aggregation and summarization pipeline using local LLMs, with live website integration and automatic Cloudflare deployment.

## What It Does

1. Fetches articles from 10 RSS sources every 6 hours
2. Summarizes them using a local Ollama model (qwen3:4b on Ollama)
3. Exports curated two-tier output (Breaking News / General News) to JSON
4. Deploys the updated website to Cloudflare automatically via Wrangler
5. Live site at greyursusconsulting.com updates with no manual intervention

## Architecture

- **Fetcher:** Pulls RSS feeds, calculates priority based on keyword matching
- **Summarizer:** Calls local Ollama instance for each article
- **Exporter:** Writes curated JSON to website data directory
- **Deploy:** Wrangler CLI pushes updated site to Cloudflare Worker
- **Scheduler:** threading.Timer drives 6-hour auto-refresh cycle; manual refresh button resets the timer

## Configuration

Edit `config.json` to modify:
- RSS sources (`whitelist_sites`)
- Keyword priorities (`keywords.priority_1/2/3`)
- Ollama endpoint and model (`api.provider`, `api.model`)
- Scan interval and article limits (`settings.scan_interval_hours`, `settings.max_articles_per_scan`)

## Requirements

- Python 3.10+
- Ollama running on local network (default: 192.168.1.183:11434)
- Node.js 22+ and Wrangler 4.x (for Cloudflare auto-deploy)
- Cloudflare API token stored in `~/.snewzy_env`

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage

**Manual update:**
```bash
python3 -m news_hub.main --update
```

**GUI mode:**
```bash
python3 -m news_hub.display
```

**Automated mode:**
The GUI's 6-hour timer handles this automatically. Manual refresh button triggers an immediate update and resets the countdown.

## Run it on a schedule (no GUI needed)

The 6-hour timer inside the GUI only runs while the desktop app is open, which
is why the website's Live Demo can go stale. To keep it current on its own,
install the systemd user timer in `deploy/` on the machine that runs Snewzy:

```bash
mkdir -p ~/.config/systemd/user
cp deploy/snewzy-update.service deploy/snewzy-update.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now snewzy-update.timer
# keep user timers running after you log out:
loginctl enable-linger "$USER"
```

Check it with `systemctl --user list-timers` and see the last run's output with
`journalctl --user -u snewzy-update.service -n 50`. Stop it any time with
`systemctl --user disable --now snewzy-update.timer`.

Edit the paths in `deploy/snewzy-update.service` first if your copy of Snewzy
isn't at `~/workspace/projects/snewzy`. Ollama has to be reachable when it runs.

### Settings for the website export (optional, in `config.json`)

- `settings.export_max_age_days` (default 7): only stories newer than this go
  to the website.
- `settings.website_dir`: the website folder. When set, the export writes
  `data/latest_news.json` there and `wrangler deploy` runs in the same folder.
- `api.endpoint`: Ollama's address. The `OLLAMA_HOST` environment variable
  overrides it.

Each export also writes `data/latest_news_meta.json` with an `updated_at`
time, which the website can show as "Last updated".

## Project Structure

```
snewzy/
├── config.json              # RSS sources, keywords, API settings
├── requirements.txt         # Python dependencies
├── news_hub/
│   ├── main.py              # Entry point, orchestrates all steps
│   ├── data/                # SQLite database (gitignored)
│   └── modules/
│       ├── config_loader.py # Pydantic config validation
│       ├── database.py      # SQLite operations
│       ├── fetcher.py       # RSS feed fetching
│       ├── summarizer.py    # Ollama LLM summarization
│       ├── exporter.py      # JSON export for website
│       └── display.py       # Flet GUI with auto-refresh timer
```

## Notes

- Database lives on local disk (`~/snewzy_data/news_hub.db`), not the network share, to avoid SQLite locking issues with CIFS mounts
- Cloudflare deploy requires `wrangler.jsonc` in the website directory with the correct Worker name and account ID
- The website is a Cloudflare Worker with static assets, not a Pages project
