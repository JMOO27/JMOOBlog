import sqlite3

from contextlib import contextmanager

from .config import get_settings
from ..schemas.entry import BlogEntry

settings = get_settings()

def create_db() -> None:
    with transaction() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS entries (
            BLOG_ID INTEGER PRIMARY KEY AUTOINCREMENT,
            BLOG_TYPE TEXT NOT NULL,
            TITLE TEXT NOT NULL,
            CONTENT TEXT NOT NULL,
            TIMESTAMP DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        
        """)

def create_entry(type: str, title: str, content: str) -> int:
    with transaction() as conn:
        cursor = conn.execute("""
            INSERT INTO entries (BLOG_TYPE, TITLE, CONTENT) VALUES (?, ?, ?)
        """, (type, title, content))
        assert cursor.lastrowid is not None
        return cursor.lastrowid

def read_entries(type: str, *, newest_first: bool = False) -> list[BlogEntry]:
    order = "TIMESTAMP DESC, BLOG_ID DESC" if newest_first else "BLOG_ID"
    with transaction() as conn:
        cursor = conn.execute(f"""
            SELECT BLOG_ID AS blog_id, BLOG_TYPE AS blog_type,
                   TITLE AS title, CONTENT AS content, TIMESTAMP AS timestamp
            FROM entries
            WHERE BLOG_TYPE = ?
            ORDER BY {order}
        
        """, (type,))

        return [BlogEntry.model_validate(dict(row)) for row in cursor.fetchall()]

def read_entry(blog_id: int) -> BlogEntry | None:
    with transaction() as conn:
        row = conn.execute("""
            SELECT BLOG_ID AS blog_id, BLOG_TYPE AS blog_type,
                   TITLE AS title, CONTENT AS content, TIMESTAMP AS timestamp
            FROM entries
            WHERE BLOG_ID = ?
        """, (blog_id,)).fetchone()
        return BlogEntry.model_validate(dict(row)) if row is not None else None


def update_entries(blog_id: int, type: str, title: str, content: str) -> bool:
    with transaction() as conn:
        cursor = conn.execute("""
            UPDATE entries
            SET BLOG_TYPE = ?, TITLE = ?, CONTENT = ?
            WHERE BLOG_ID = ?
        """, (type, title, content, blog_id))
        return cursor.rowcount > 0


def delete_entries(blog_id: int) -> bool:
    with transaction() as conn:
        cursor = conn.execute("DELETE FROM entries WHERE BLOG_ID = ?", (blog_id,))
        return cursor.rowcount > 0

def open_db():
    conn = sqlite3.connect(
        settings.DATABASE_PATH,
        timeout=10)

    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        conn.close()
        raise

    return conn

@contextmanager
def transaction():
    conn = open_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
