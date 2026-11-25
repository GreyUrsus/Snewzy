"""Database module - handles SQLite operations for article storage."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple

from .dates import is_iso, text_to_iso


#Database file location: news_hub/data/news_hub.db
DATABASE_PATH = Path.home() / "snewzy_data" / "news_hub.db"


def init_database() -> None:
    """Initialize the database, creating tables if they don't exist."""
    #Ensure data directory exists
    db_dir = DATABASE_PATH.parent
    db_dir.mkdir(parents=True, exist_ok=True)

    #Connect to database (creates file if doesn't exist
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    #Create articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT NOT NULL UNIQUE,
            published_date TEXT,
            content TEXT,
            summary TEXT,
            bullet_points TEXT,
            priority INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    #CREATE INDEX IF NOT EXISTS idx_url ON articles(url)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_url ON articles(url)
    """)

    #Create index on priority and status for faster queries
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_priority_status
        ON articles(priority, status)
    """)

    # One-time migration to reclassify any existing priority 3 articles as priority 2
    cursor.execute("UPDATE articles SET priority = 2 WHERE priority = 3")

    # One-time migration: older rows stored the feed's raw date text
    # (e.g. "Wed, 25 Mar 2026 ..."), which sorts alphabetically, not by time.
    # Rewrite those rows to ISO 8601 UTC. Rows already in ISO form are skipped,
    # so this is cheap to run on every start-up. Rows whose date can't be read
    # fall back to when Snewzy first saved them (created_at).
    cursor.execute("SELECT id, published_date, created_at FROM articles")
    for article_id, published_date, created_at in cursor.fetchall():
        if is_iso(published_date):
            continue
        fixed = text_to_iso(published_date) or text_to_iso(created_at)
        if fixed:
            cursor.execute(
                "UPDATE articles SET published_date = ? WHERE id = ?",
                (fixed, article_id),
            )

    conn.commit()
    conn.close( )


def article_exists(url: str) -> bool:
        """Check if an article with this URL already exists."""
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT 1 from articles WHERE url = ?", (url,))
        result = cursor.fetchone()

        conn.close()
        return result is not None
    
def insert_article(title: str, source: str, url: str,
                       published_date: str, content: str,
                       priority: int) -> bool:
        """Insert a new article. Returnd True if inserted, False if duplicate"""
        #Don't insert if already exis
        if article_exists(url):
            return False
        
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO articles
            (title, source, url, published_date, content, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, source, url, published_date, content, priority, "pending"))

        conn.commit()
        conn.close()
        return True

def make_article_as_read(article_id: int) -> None:
      """Mark an article as read (archived)."""
      conn = sqlite3.connect(DATABASE_PATH)
      cursor = conn.cursor()

      cursor.execute("""
                     UPDATE articles
                     SET status = ?
                     WHERE id = ?
    """, ("read", article_id))
      
      conn.commit()
      conn.close()
    

def get_articles_by_priority(priority: int, status: str = None, limit: int = None,
                             published_after: Optional[str] = None) -> List[Tuple]:
        """Retrieve articles filtered by priority and optional status.
        
        Args:
            priority: Priority level (1, 2, or 3)
            status: Optional status filter ('pending', 'summarized', 'read')
            limit: Maximum number of articles to return
            published_after: Optional ISO 8601 date/time text. When given,
                only articles published at or after it are returned (used
                by the website export to leave out stale stories).
            
        Returns:
            List of article tuples from database
        """

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Build the WHERE clause from whichever filters were passed.
        # published_date is stored as ISO 8601 text (see dates.py), so a plain
        # text comparison (>=) and ORDER BY both follow real time order.
        conditions = ["priority = ?"]
        params: list = [priority]
        if status:
            conditions.append("status = ?")
            params.append(status)
        if published_after:
            conditions.append("published_date >= ?")
            params.append(published_after)
        params.append(limit or 9999)

        cursor.execute(f"""
            SELECT * FROM articles
            WHERE {" AND ".join(conditions)}
            ORDER BY published_date DESC
            LIMIT ?
        """, params)

        results = cursor.fetchall()
        conn.close()
        return results

def update_article_summary(article_id: int, summary: str,
                               bullet_points: str) -> None:
    """Update an article with its summary and mark as summarized."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    cursor.execute("""
            UPDATE articles
            SET summary = ?, bullet_points = ?, status = ?
            WHERE id = ?
        """, (summary, bullet_points, "summarized", article_id))

    conn.commit()
    conn.close()


        #Test code
if __name__ == "__main__":
            init_database()
            print(f"Database initialized at: {DATABASE_PATH}")

            #Test insert
            test_insert = insert_article(
                title="Test Article",
                source="Test Source",
                url="https://example.com/test",
                published_date="2024-01-01",
                content="This is test content",
                priority=1
            )
            print(f"Test insert successful: {test_insert}")

            #Test duplicate
            test_duplicate = insert_article(
                title="Test Article Duplicate",
                source="Test Source",
                url="https://example.com/test",
                published_date="2024-01-01",
                content="Different content",
                priority=2
            )
            print(f"Duplicate blocked correctly: {not test_duplicate}")
