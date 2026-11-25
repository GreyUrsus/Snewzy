"""Summarizer module - generates article summaries using local Ollama."""

import os
import re
from datetime import date
from typing import List, Tuple, Dict, Optional

import requests

from .database import get_articles_by_priority, update_article_summary
from .config_loader import AppConfig


def get_pending_articles(priority: int, limit: int) -> List[Tuple]:
    """Retrieve articles that need summarizing."""
    return get_articles_by_priority(priority, status="pending")[:limit]


def create_summary_prompt(title: str, content: str, priority: int) -> str:
    """Create the prompt for the LLM."""
    priority_descriptions = {
        1: "critical importance - be thorough",
        2: "moderate importance - standard summary",
        3: "general interest - brief overview"
    }
    
    importance = priority_descriptions.get(priority, "standard")
    
    # Small local models don't know today's date. Without it they sometimes
    # call a recent article "from the future" or "hypothetical" in the summary,
    # which then shows up on the public website. Give them the date and tell
    # them to stick to what the article says.
    today = date.today().strftime("%B %d, %Y")

    prompt = f"""Today is {today}. Summarize this news article.
Only describe what the article says. Do not comment on its date, whether it
is real, or whether it seems to be in the future.

Priority: {priority} ({importance})

Title: {title}

Content: {content[:3000]}

Provide:
1. A summary (2-4 sentences)
2. 1-3 bullet points of key facts

Format:
SUMMARY: [summary]

BULLET POINTS:
- [point 1]
- [point 2]
"""
    return prompt


# Used only when neither OLLAMA_HOST nor config.json's api.endpoint is set.
DEFAULT_OLLAMA_ENDPOINT = "http://192.168.1.183:11434"


def resolve_endpoint(config_endpoint: Optional[str] = None) -> str:
    """Pick the Ollama address: OLLAMA_HOST env var > config.json > default."""
    endpoint = os.environ.get("OLLAMA_HOST") or config_endpoint or DEFAULT_OLLAMA_ENDPOINT
    if not endpoint.startswith("http"):
        # OLLAMA_HOST is often written as "host:port" without a scheme
        endpoint = "http://" + endpoint
    return endpoint.rstrip("/")


def strip_thinking(text: str) -> str:
    """Remove any <think>...</think> block a reasoning model left in its reply."""
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def call_ollama(prompt: str, model: str = "qwen3:4b",
                endpoint: Optional[str] = None) -> str:
    """Send prompt to local Ollama instance."""
    try:
        response = requests.post(
            f"{resolve_endpoint(endpoint)}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                # qwen3 is a "thinking" model. Its hidden reasoning used to eat
                # the token budget, cutting summaries off mid-sentence. Turn
                # thinking off; a news summary doesn't need it.
                "think": False,
                "options": {
                    "temperature": 0.3,
                    # A little more room so the summary + bullets always finish
                    "num_predict": 800
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return strip_thinking(response.json()["response"])
    
    except requests.exceptions.ConnectionError:
        print("    Error: Cannot connect to Ollama. Is it running?")
        return None
    except Exception as e:
        print(f"    Ollama error: {e}")
        return None


def trim_to_sentence(text: str, max_chars: int = 400) -> str:
    """Shorten text to at most max_chars, ending on a full sentence.

    Used so the website never shows a summary that stops mid-word
    ("...surgical procedures. This").
    """
    text = " ".join(text.split())  # collapse newlines / double spaces
    if len(text) <= max_chars and text.endswith((".", "!", "?")):
        return text
    cut = text[:max_chars]
    last_end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if cut.endswith((".", "!", "?")):
        return cut
    if last_end > 0:
        return cut[:last_end + 1]
    # No sentence end at all: cut at a word boundary and mark it as shortened
    return cut.rsplit(" ", 1)[0] + "…"


def parse_response(response: str) -> Tuple[str, str]:
    """Parse response into summary and bullets."""
    if not response:
        return "Summary unavailable.", "Key points unavailable."
    
    lines = response.split("\n")
    summary_lines: List[str] = []
    bullets = []
    in_summary = False
    in_bullets = False
    
    for line in lines:
        line = line.strip()
        
        if line.upper().startswith("SUMMARY:"):
            # The summary can start on this line and continue on the next ones
            in_summary = True
            first = line[len("SUMMARY:"):].strip()
            if first:
                summary_lines.append(first)
        elif "BULLET" in line.upper():
            in_summary = False
            in_bullets = True
        elif in_bullets and line.startswith("-"):
            bullets.append(line[1:].strip())
        elif in_summary and line:
            summary_lines.append(line)
    
    summary = " ".join(summary_lines)
    if not summary:
        # Model ignored the format: use its text, cut at a sentence end
        summary = response
    summary = trim_to_sentence(summary)
    
    bullet_text = "\n".join(f"- {b}" for b in bullets) if bullets else "See summary."
    
    return summary, bullet_text


def summarize_article(article: Tuple, model: str, endpoint: Optional[str] = None) -> bool:
    """Summarize a single article."""
    article_id = article[0]
    title = article[1]
    content = article[5] or article[4] or title
    priority = article[8]
    
    print(f"    Summarizing: {title[:50]}...")
    
    prompt = create_summary_prompt(title, content, priority)
    response = call_ollama(prompt, model, endpoint)
    
    if not response:
        return False
    
    summary, bullets = parse_response(response)
    update_article_summary(article_id, summary, bullets)
    return True


def run_summarizer(config: AppConfig, max_per_priority: int = 5) -> Dict[str, int]:
    """Main entry point."""
    stats = {"attempted": 0, "succeeded": 0, "failed": 0}
    
    model = getattr(config.api, "local_model", "llama3.2:3b")
    endpoint = getattr(config.api, "endpoint", None)
    
    print(f"Using local model: {model}")
    print("Make sure Ollama is running: ollama serve")
    
    for priority in [1, 2]:
        print(f"\nProcessing Priority {priority}...")
        articles = get_pending_articles(priority, max_per_priority)
        
        if not articles:
            print(f"  No pending articles")
            continue
        
        print(f"  Found {len(articles)} articles")
        
        for article in articles:
            stats["attempted"] += 1
            if summarize_article(article, model, endpoint):
                stats["succeeded"] += 1
            else:
                stats["failed"] += 1
    
    return stats


if __name__ == "__main__":
    from .config_loader import load_config
    
    config = load_config()
    results = run_summarizer(config, max_per_priority=2)
    print(f"\nDone! Attempted: {results['attempted']}, Succeeded: {results['succeeded']}")