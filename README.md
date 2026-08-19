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
