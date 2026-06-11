"""Database module - handles SQLite operations for article storage."""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Tuple


#Database file location: news_hub/data/news_hub.db
DATABASE_PATH = Path(__file__).parent.parent/ "data" /"news_hub.db"


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
    

def get_articles_by_priority(priority: int, status: str = None, limit: int = None) -> List[Tuple]:
        """Retrieve articles filtered by priority and optional status.
        
        Args:
            priority: Priority level (1, 2, or 3)
            status: Optional status filter ('pending', 'summarized', 'read')
            limit: Maximum number of articles to return
            
        Returns:
            List of article tuples from database
        """

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        if status:
            cursor.execute("""
                SELECT * FROM articles
                WHERE priority = ? AND status = ?
                ORDER BY published_date DESC
                LIMIT ?
            """, (priority, status, limit or 9999))
        else:
            cursor.execute("""
                SELECT * FROM articles
                WHERE priority = ?
                ORDER BY published_date DESC
                LIMIT ?
            """, (priority, limit or 9999))

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