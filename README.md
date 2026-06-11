# Snewzy - Personal AI News Hub

An agent-based news aggregator that fetches RSS feeds, prioritizes articles by keyword, summarizes them with local AI, and presents them in a clean GUI.

## Features

- **Fetcher Agent**: Automatically downloads articles from RSS feeds
- **Priority Engine**: Sorts articles by keyword importance (1-3)
- **Summarizer Agent**: Uses local LLM (Ollama) for zero-cost summarization
- **Desktop GUI**: View articles by priority with color-coded cards

## Quick Start

### Prerequisites

- Python 3.10+
- Ollama installed locally

### Installation

```bash
# Clone repository
cd snewzy

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Pull Ollama model
ollama pull llama3.2:3b

## Launch Methods

**Desktop Icon (Recommended):**
Double-click Snewzy icon on desktop

**Terminal:**
```bash
cd ~/workspace/projects/snewzy
source news_hub/venv/bin/activate
python -m news_hub.main