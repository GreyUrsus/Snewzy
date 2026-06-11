"""Summarizer module - generates article summaries using local Ollama."""

import requests
from typing import List, Tuple, Dict

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
    
    prompt = f"""Summarize this news article.

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


def call_ollama(prompt: str, model: str = "llama3.2:3b") -> str:
    """Send prompt to local Ollama instance."""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "num_predict": 500
                }
            },
            timeout=120
        )
        response.raise_for_status()
        return response.json()["response"]
    
    except requests.exceptions.ConnectionError:
        print("    Error: Cannot connect to Ollama. Is it running?")
        return None
    except Exception as e:
        print(f"    Ollama error: {e}")
        return None


def parse_response(response: str) -> Tuple[str, str]:
    """Parse response into summary and bullets."""
    if not response:
        return "Summary unavailable.", "Key points unavailable."
    
    lines = response.split("\n")
    summary = ""
    bullets = []
    in_bullets = False
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("SUMMARY:"):
            summary = line.replace("SUMMARY:", "").strip()
        elif "BULLET" in line.upper():
            in_bullets = True
        elif in_bullets and line.startswith("-"):
            bullets.append(line[1:].strip())
        elif in_bullets and line and not summary:
            summary = line
    
    if not summary:
        summary = response[:200] + "..."
    
    bullet_text = "\n".join(f"- {b}" for b in bullets) if bullets else "See summary."
    
    return summary, bullet_text


def summarize_article(article: Tuple, model: str) -> bool:
    """Summarize a single article."""
    article_id = article[0]
    title = article[1]
    content = article[5] or article[4] or title
    priority = article[8]
    
    print(f"    Summarizing: {title[:50]}...")
    
    prompt = create_summary_prompt(title, content, priority)
    response = call_ollama(prompt, model)
    
    if not response:
        return False
    
    summary, bullets = parse_response(response)
    update_article_summary(article_id, summary, bullets)
    return True


def run_summarizer(config: AppConfig, max_per_priority: int = 5) -> Dict[str, int]:
    """Main entry point."""
    stats = {"attempted": 0, "succeeded": 0, "failed": 0}
    
    model = getattr(config.api, "local_model", "llama3.2:3b")
    
    print(f"Using local model: {model}")
    print("Make sure Ollama is running: ollama serve")
    
    for priority in [1, 2, 3]:
        print(f"\nProcessing Priority {priority}...")
        articles = get_pending_articles(priority, max_per_priority)
        
        if not articles:
            print(f"  No pending articles")
            continue
        
        print(f"  Found {len(articles)} articles")
        
        for article in articles:
            stats["attempted"] += 1
            if summarize_article(article, model):
                stats["succeeded"] += 1
            else:
                stats["failed"] += 1
    
    return stats


if __name__ == "__main__":
    from .config_loader import load_config
    
    config = load_config()
    results = run_summarizer(config, max_per_priority=2)
    print(f"\nDone! Attempted: {results['attempted']}, Succeeded: {results['succeeded']}")