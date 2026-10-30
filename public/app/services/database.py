import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager

from .config import get_settings
from ..schemas.entry import BlogPost, Topic

settings = get_settings()


def create_db() -> None:
    """Initialize the schema without changing existing topics or posts.

    A topic can exist before its first post is written. Each post must reference
    one existing topic; deleting that topic removes its posts automatically.
    """
    with transaction() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                -- Reject the Unicode whitespace recognized by Python's str.strip().
                title TEXT NOT NULL UNIQUE
                    CHECK (length(trim(title, char(
                        9, 10, 11, 12, 13, 28, 29, 30, 31, 32, 133, 160, 5760,
                        8192, 8193, 8194, 8195, 8196, 8197, 8198, 8199, 8200,
                        8201, 8202, 8232, 8233, 8239, 8287, 12288
                    ))) > 0),
                description TEXT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS blog_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                description TEXT,
                timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Index the child key for topic filtering and cascading deletes.
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_blog_posts_topic_id ON blog_posts(topic_id)
        """)


def create_topic(title: str, description: str | None = None) -> int:
    with transaction() as conn:
        cursor = conn.execute(
            "INSERT INTO topics (title, description) VALUES (?, ?)",
            (title, description),
        )
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def read_topics() -> list[Topic]:
    with transaction() as conn:
        rows = conn.execute("SELECT * FROM topics ORDER BY id").fetchall()
        return [Topic.model_validate(dict(row)) for row in rows]


def read_topic(topic_id: int) -> Topic | None:
    with transaction() as conn:
        row = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
        return Topic.model_validate(dict(row)) if row is not None else None


def update_topic(topic_id: int, title: str, description: str | None = None) -> bool:
    """Replace topic details while preserving its ID and creation timestamp."""
    with transaction() as conn:
        cursor = conn.execute(
            "UPDATE topics SET title = ?, description = ? WHERE id = ?",
            (title, description, topic_id),
        )
        return cursor.rowcount > 0


def delete_topic(topic_id: int) -> bool:
    """Delete a topic and, through the foreign key, all posts belonging to it."""
    with transaction() as conn:
        cursor = conn.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        return cursor.rowcount > 0


def create_blog_post(
    topic_id: int,
    title: str,
    content: str,
    description: str | None = None,
) -> int:
    with transaction() as conn:
        cursor = conn.execute("""
            INSERT INTO blog_posts (topic_id, title, content, description)
            VALUES (?, ?, ?, ?)
        """, (topic_id, title, content, description))
        assert cursor.lastrowid is not None
        return cursor.lastrowid


def read_blog_posts(
    *,
    topic_id: int | None = None,
    newest_first: bool = False,
) -> list[BlogPost]:
    """List all posts, optionally filtering by topic."""
    where = " WHERE topic_id = ?" if topic_id is not None else ""
    parameters = (topic_id,) if topic_id is not None else ()
    order = "timestamp DESC, id DESC" if newest_first else "id"
    with transaction() as conn:
        rows = conn.execute(
            f"SELECT * FROM blog_posts{where} ORDER BY {order}", parameters
        ).fetchall()
        return [BlogPost.model_validate(dict(row)) for row in rows]


def read_blog_post(blog_post_id: int) -> BlogPost | None:
    with transaction() as conn:
        row = conn.execute(
            "SELECT * FROM blog_posts WHERE id = ?", (blog_post_id,)
        ).fetchone()
        return BlogPost.model_validate(dict(row)) if row is not None else None


def update_blog_post(
    blog_post_id: int,
    topic_id: int,
    title: str,
    content: str,
    description: str | None = None,
) -> bool:
    """Replace post details, including its topic, without changing its identity."""
    with transaction() as conn:
        cursor = conn.execute("""
            UPDATE blog_posts
            SET topic_id = ?, title = ?, content = ?, description = ?
            WHERE id = ?
        """, (topic_id, title, content, description, blog_post_id))
        return cursor.rowcount > 0


def delete_blog_post(blog_post_id: int) -> bool:
    with transaction() as conn:
        cursor = conn.execute("DELETE FROM blog_posts WHERE id = ?", (blog_post_id,))
        return cursor.rowcount > 0


def open_db() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.DATABASE_PATH, timeout=10)
    try:
        conn.row_factory = sqlite3.Row
        # SQLite requires this on EVERY connection for both FK checks and cascades.
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 10000")
        conn.execute("PRAGMA journal_mode = WAL")
    except Exception:
        conn.close()
        raise
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Commit successful operations, roll back failures, and always close."""
    conn = open_db()
    try:
        with conn:
            yield conn
    finally:
        conn.close()
