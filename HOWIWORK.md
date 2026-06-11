Here is the fresh **HOWIWORK.md**:

---

# Snewzy - How It Works

Technical documentation for the Snewzy personal news hub.

## Overview

Snewzy is an agent-based news aggregator that:
1. Fetches RSS feeds from whitelisted sources
2. Categorizes articles by keyword priority (1-3)
3. Summarizes articles using local AI (Ollama)
4. Presents articles in a priority-based GUI
5. Allows marking articles as read/archived

## Architecture

```
┌─────────────────────────────────────────┐
│           ORCHESTRATOR (main.py)        │
│    Coordinates: CLI mode vs GUI mode   │
└─────────────────┬───────────────────────┘
                  │
    ┌─────────────┼─────────────┐
    ▼             ▼             ▼
┌───────┐    ┌───────┐    ┌───────────┐
│FETCH  │    │ANALYZE│    │  CURATE   │
│AGENT  │───▶│AGENT  │───▶│   AGENT   │
└───────┘    └───────┘    └─────┬─────┘
   ▲                              │
   │                              ▼
   │                         ┌───────────┐
   │                         │  DISPLAY  │
   │                         │   (GUI)   │
   │                         └───────────┘
   │                              │
   └──────────────────────────────┘
         (Mark as Read feedback)
```

## Data Flow

### 1. Configuration Phase
**File:** `config.json` → `config_loader.py`

| Component | Input | Output |
|-----------|-------|--------|
| `config.json` | User-defined JSON | Raw configuration |
| `config_loader.py` | JSON path | Validated `AppConfig` object |
| `Pydantic models` | Dict data | Type-validated objects |

**Key Models:**
- `SiteConfig`: RSS source with URL and priority_boost flag
- `KeywordsConfig`: Three priority levels of keywords
- `APIConfig`: Ollama/OpenAI configuration
- `SettingsConfig`: App behavior (scan interval, max articles)

### 2. Fetch Phase
**File:** `fetcher.py`

```
RSS Feed URL
    ↓
feedparser.parse()
    ↓
List of entries (title, link, published, summary)
    ↓
For each entry:
    - Check if exists in DB (article_exists)
    - Calculate priority (calculate_priority)
    - Insert new article (insert_article)
```

**Priority Calculation:**
1. Combine `title + " " + content` → lowercase
2. Check P1 keywords → if match, return 1
3. Check P2 keywords → if match, return 2
4. Check P3 keywords → if match, return 3
5. No matches → default to 3

**Note:** `priority_boost: true` in site config bypasses keyword matching and forces P1.

### 3. Summarize Phase
**File:** `summarizer.py`

```
Pending articles by priority (P1 first, then P2, P3)
    ↓
For each article:
    - Create prompt with title, content, priority level
    - Call Ollama API (localhost:11434)
    - Parse response for SUMMARY and BULLET POINTS
    - Update article in DB (update_article_summary)
    - Mark status as "summarized"
```

**Ollama Prompt Structure:**
```
Summarize this news article.
Priority: {1/2/3} ({importance_description})

Title: {title}
Content: {content}

Provide:
1. A summary (2-4 sentences)
2. 1-3 bullet points of key facts

Format:
SUMMARY: [summary]

BULLET POINTS:
- [point 1]
- [point 2]
```

### 4. Display Phase
**File:** `display.py`

```
Initialize database
    ↓
Fetch articles by priority (max 5 per priority, status="summarized")
    ↓
For each priority section (P1, P2, P3):
    - Create cards with title, source, summary, bullets
    - Color-code by priority (red/orange/green)
    - Add "Open Article" button (links to URL)
    - Add "Mark as Read" button (updates status)
    ↓
Render GUI with scrollable columns
```

**Card Components:**
- Priority badge (P1/P2/P3)
- Source name and date
- Title (bold)
- Summary text
- Bullet points (if available)
- Action buttons

### 5. User Interaction Flow

| Action | Handler | Result |
|--------|---------|--------|
| Click "Mark as Read" | `mark_article_as_read()` | Status → "read", card removed |
| Click "Open Article" | URL launcher | Opens browser to article |
| Click "Settings" | `create_settings_dialog()` | Overlay with config editor |
| Click "Refresh News" | `subprocess.run(--update)` | Re-fetches and reloads GUI |
| Close app | Standard close | Database persists |

## Database Schema

**Table:** `articles`

| Column | Type | Purpose |
|--------|------|---------|
| id | INTEGER PRIMARY KEY AUTOINCREMENT | Unique ID |
| title | TEXT NOT NULL | Article title |
| source | TEXT NOT NULL | Site name |
| url | TEXT NOT NULL UNIQUE | Article link (deduplication) |
| published_date | TEXT | Original publish date |
| content | TEXT | Full article text/summary |
| summary | TEXT | AI-generated summary |
| bullet_points | TEXT | AI-generated bullet points |
| priority | INTEGER NOT NULL | 1/2/3 classification |
| status | TEXT DEFAULT 'pending' | pending/summarized/read |
| created_at | TIMESTAMP | When fetched |

**Indexes:**
- `idx_url` on url (fast duplicate checking)
- `idx_priority_status` on (priority, status) (fast GUI queries)

## File Structure

```
snewzy/                           # Project root
├── config.json                   # User configuration
├── launch.sh                     # Desktop launcher script
├── requirements.txt              # Python dependencies
├── README.md                     # User documentation
├── HOWIWORK.md                   # This file
├── news_hub/                     # Python package
│   ├── __init__.py
│   ├── main.py                   # Entry point
│   ├── data/                     # SQLite database
│   │   └── news_hub.db
│   └── modules/                  # Core modules
│       ├── __init__.py
│       ├── config_loader.py      # Config validation
│       ├── database.py           # SQLite operations
│       ├── fetcher.py            # RSS fetching
│       ├── summarizer.py         # AI summarization
│       ├── display.py            # GUI rendering
│       └── settings_dialog.py    # Settings overlay
└── venv/                         # Virtual environment
    └── ...
```

## Configuration Details

### Keywords Strategy

**Priority 1 (Critical):** Security, breaches, urgent news
- Examples: `data breach`, `security flaw`, `zero-day`, `ransomware`

**Priority 2 (Important):** Business, funding, major announcements
- Examples: `funding round`, `acquired`, `IPO`, `investment`

**Priority 3 (General):** Reviews, updates, minor news
- Examples: `product launch`, `review`, `new feature`

**Tip:** Use multi-word phrases for precision. Single words like "security" match too broadly.

### RSS Feed Sources

**Good sources for tech news:**
- TechCrunch (techcrunch.com/feed/)
- Wired (wired.com/feed/)
- 404 Media (404media.co/feed/)
- Tom's Hardware (tomshardware.com/rss/news)

**priority_boost:** Only use for emergency-only feeds (e.g., government alerts).

## Launch Methods

### Method 1: Desktop Icon (Recommended)
Double-click `Snewzy.desktop` icon on desktop.

**Requirements:**
- `launch.sh` must be executable
- `.desktop` file must have `metadata::trusted true`
- Virtual environment at correct path

### Method 2: Terminal
```bash
cd /path/to/snewzy
source venv/bin/activate
python -m news_hub.main
```

### Method 3: Command Line (Update Mode)
```bash
python -m news_hub.main --update
```

## Troubleshooting

### Issue: No articles appearing in GUI
**Check:**
- Database exists: `ls news_hub/data/news_hub.db`
- Articles have status="summarized": `sqlite3 news_hub/data/news_hub.db "SELECT status, COUNT(*) FROM articles GROUP BY status;"`
- Ollama is running: `ollama ps`

### Issue: All articles Priority 1
**Cause:** `priority_boost: true` on all sites, or keywords too broad.
**Fix:** Set `priority_boost: false` in config.json, use more specific keywords.

### Issue: Desktop icon won't launch
**Check:**
- `launch.sh` has correct paths (absolute, not relative)
- `.desktop` file is executable: `chmod +x Snewzy.desktop`
- File is trusted: `gio set Snewzy.desktop metadata::trusted true`
- Virtual environment path matches `launch.sh` content

### Issue: Summarizer timeout
**Cause:** Ollama too slow on CPU.
**Fix:** Increase timeout in `summarizer.py`, or use smaller model (llama3.2:3b), or add GPU.

### Issue: Keywords not matching
**Debug:** Add print to `calculate_priority()`:
```python
print(f"Checking: {title}")
print(f"P1 keywords: {keywords.priority_1}")
print(f"Text: {text[:100]}")
```

## Security Notes

- **API Keys:** Store in environment variables or `.env`, never in code
- **Database:** SQLite file is local, no network exposure
- **Ollama:** Runs locally, no data leaves machine
- **RSS Feeds:** HTTPS recommended, verify feed URLs

## Performance Optimization

| Bottleneck | Solution |
|------------|----------|
| Slow summarization | Use GPU, smaller model, or reduce `max_articles_per_scan` |
| Large database | Add `LIMIT` to queries, archive old articles |
| GUI lag | Reduce card count, use lazy loading |
| Fetch delays | Reduce `max_articles_per_scan`, use fewer feeds |

## Extension Points

**Easy additions:**
- Add more RSS feeds to `config.json`
- Adjust keywords for different news domains
- Change Ollama model in `config.json`

**Medium additions:**
- Add search/filter to GUI
- Export articles to Markdown/PDF
- Add notification alerts for P1 articles

**Hard additions:**
- Web-based interface (replace Flet)
- Multi-user support
- Cloud sync

---

*Snewzy v1.0 - Personal AI News Hub*


