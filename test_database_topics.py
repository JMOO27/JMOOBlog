r"""Database relationship and CRUD regression tests.

Run from the repository root:
    .\env\Scripts\python.exe -m unittest -v test_database_topics

Every test uses a temporary database. The application's blog.db is never touched.
"""

import asyncio
import contextlib
import io
import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from pydantic import ValidationError

from public.app.main import create_app, main
from public.app.schemas.entry import BlogPost, Topic
from public.app.services import database


class TemporaryDatabaseTestCase(unittest.TestCase):
    def setUp(self):
        # Patch the configured path before initializing: no real data is changed.
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        settings_patch = patch.object(
            database.settings, "DATABASE_PATH", str(self.directory / "test.db")
        )
        settings_patch.start()
        self.addCleanup(settings_patch.stop)
        database.create_db()
        self.topic_id = database.create_topic("Python")


class TopicRelationshipTests(TemporaryDatabaseTestCase):
    def test_topic_can_start_empty_then_have_one_or_many_posts(self):
        """A parent may be created first, and then accept multiple children."""
        self.assertEqual(database.read_blog_posts(topic_id=self.topic_id), [])
        first_id = database.create_blog_post(self.topic_id, "First", "Body")
        self.assertEqual(len(database.read_blog_posts(topic_id=self.topic_id)), 1)
        second_id = database.create_blog_post(self.topic_id, "Second", "Body")
        posts = database.read_blog_posts(topic_id=self.topic_id)
        self.assertEqual([post.id for post in posts], [first_id, second_id])
        self.assertTrue(all(post.topic_id == self.topic_id for post in posts))
        self.assertTrue(all(isinstance(post, BlogPost) for post in posts))

    def test_post_requires_one_existing_topic(self):
        """NOT NULL rejects no topic; the foreign key rejects nonexistent IDs."""
        for topic_id in (None, 999, 0, -1):
            with self.subTest(topic_id=topic_id):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.create_blog_post(topic_id, "Invalid", "Body")
        self.assertEqual(database.read_blog_posts(), [])

    def test_sql_cannot_omit_topic_or_assign_multiple_topics(self):
        """Enforce the relationship even when a caller bypasses the helpers."""
        with self.assertRaises(sqlite3.IntegrityError):
            with database.transaction() as conn:
                conn.execute("""
                    INSERT INTO blog_posts (title, content)
                    VALUES ('Orphan', 'Body')
                """)
        other_id = database.create_topic("Other")
        with self.assertRaises(sqlite3.IntegrityError):
            database.create_blog_post(f"{self.topic_id},{other_id}", "Invalid", "Body")

    def test_deleting_topic_cascades_to_all_its_posts_only(self):
        """Removing one parent must leave unrelated topics and posts intact."""
        first = database.create_blog_post(self.topic_id, "First", "Body")
        second = database.create_blog_post(self.topic_id, "Second", "Body")
        other_id = database.create_topic("Other")
        kept = database.create_blog_post(other_id, "Keep", "Body")
        self.assertTrue(database.delete_topic(self.topic_id))
        self.assertIsNone(database.read_topic(self.topic_id))
        self.assertIsNone(database.read_blog_post(first))
        self.assertIsNone(database.read_blog_post(second))
        self.assertEqual(database.read_blog_post(kept).topic_id, other_id)
        self.assertIsNotNone(database.read_topic(other_id))

    def test_direct_sql_topic_delete_also_cascades(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        with database.transaction() as conn:
            conn.execute("DELETE FROM topics WHERE id = ?", (self.topic_id,))
        self.assertIsNone(database.read_blog_post(post_id))

    def test_renaming_topic_keeps_id_and_all_post_relationships(self):
        original = database.read_topic(self.topic_id)
        post_ids = [database.create_blog_post(self.topic_id, title, "Body")
                    for title in ("First", "Second")]
        self.assertTrue(database.update_topic(self.topic_id, "Renamed", "New description"))
        renamed = database.read_topic(self.topic_id)
        self.assertEqual(renamed.id, original.id)
        self.assertEqual(renamed.timestamp, original.timestamp)
        self.assertEqual((renamed.title, renamed.description), ("Renamed", "New description"))
        self.assertEqual([post.id for post in database.read_blog_posts(topic_id=renamed.id)], post_ids)
        self.assertTrue(all(database.read_blog_post(post_id).topic_id == original.id
                            for post_id in post_ids))

    def test_post_can_be_reassigned_to_exactly_one_other_topic(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        original = database.read_blog_post(post_id)
        other_id = database.create_topic("Other")
        self.assertTrue(database.update_blog_post(post_id, other_id, "Post", "Body"))
        moved = database.read_blog_post(post_id)
        self.assertEqual((moved.id, moved.timestamp), (original.id, original.timestamp))
        self.assertEqual(moved.topic_id, other_id)
        self.assertEqual(database.read_blog_posts(topic_id=self.topic_id), [])
        self.assertEqual([post.id for post in database.read_blog_posts(topic_id=other_id)], [post_id])
        # Cascades now follow the new parent, not the old one.
        database.delete_topic(self.topic_id)
        self.assertIsNotNone(database.read_blog_post(post_id))
        database.delete_topic(other_id)
        self.assertIsNone(database.read_blog_post(post_id))

    def test_invalid_reassignment_leaves_entire_post_unchanged(self):
        post_id = database.create_blog_post(self.topic_id, "Original", "Body")
        original = database.read_blog_post(post_id)
        for topic_id in (None, 999):
            with self.subTest(topic_id=topic_id):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.update_blog_post(post_id, topic_id, "Edited", "New")
                self.assertEqual(database.read_blog_post(post_id), original)

    def test_topic_titles_are_unique_on_create_and_rename(self):
        with self.assertRaises(sqlite3.IntegrityError):
            database.create_topic("Python")
        other_id = database.create_topic("Other")
        with self.assertRaises(sqlite3.IntegrityError):
            database.update_topic(other_id, "Python", "Must roll back")
        self.assertEqual(database.read_topic(other_id).title, "Other")
        self.assertIsNone(database.read_topic(other_id).description)
        self.assertTrue(database.update_topic(self.topic_id, "Python"))

    def test_topic_titles_cannot_be_null_empty_or_whitespace(self):
        """Reject blank titles on both insertion and updates, including Unicode."""
        for title in (None, "", " ", "\t\r\n", "\u00a0\u2003"):
            with self.subTest(title=title):
                with self.assertRaises(sqlite3.IntegrityError):
                    database.create_topic(title)
                with self.assertRaises(sqlite3.IntegrityError):
                    database.update_topic(self.topic_id, title)
                self.assertEqual(database.read_topic(self.topic_id).title, "Python")

    def test_descriptions_default_to_sql_null_for_both_models(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        self.assertIsNone(database.read_topic(self.topic_id).description)
        self.assertIsNone(database.read_blog_post(post_id).description)
        with database.transaction() as conn:
            self.assertEqual(conn.execute("SELECT description IS NULL FROM topics").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT description IS NULL FROM blog_posts").fetchone()[0], 1)

    def test_descriptions_can_be_set_then_cleared_to_null(self):
        database.update_topic(self.topic_id, "Python", "Topic description")
        post_id = database.create_blog_post(self.topic_id, "Post", "Body", description="Post description")
        self.assertEqual(database.read_topic(self.topic_id).description, "Topic description")
        self.assertEqual(database.read_blog_post(post_id).description, "Post description")
        database.update_topic(self.topic_id, "Python", None)
        database.update_blog_post(post_id, self.topic_id, "Post", "Body", None)
        self.assertIsNone(database.read_topic(self.topic_id).description)
        self.assertIsNone(database.read_blog_post(post_id).description)

    def test_deleting_post_keeps_topic_and_sibling_posts(self):
        first = database.create_blog_post(self.topic_id, "First", "Body")
        second = database.create_blog_post(self.topic_id, "Second", "Body")
        self.assertTrue(database.delete_blog_post(first))
        self.assertFalse(database.delete_blog_post(first))
        self.assertIsNotNone(database.read_topic(self.topic_id))
        self.assertIsNotNone(database.read_blog_post(second))
        database.delete_blog_post(second)
        self.assertIsNotNone(database.read_topic(self.topic_id))

    def test_topic_filter_and_newest_first_order(self):
        other_id = database.create_topic("Other")
        first = database.create_blog_post(self.topic_id, "First", "Body")
        another = database.create_blog_post(self.topic_id, "Another", "Body")
        second = database.create_blog_post(other_id, "Second", "Body")
        third = database.create_blog_post(self.topic_id, "Third", "Body")
        with database.transaction() as conn:
            conn.execute("UPDATE blog_posts SET timestamp = '2020-01-01 00:00:00'")
            conn.execute("UPDATE blog_posts SET timestamp = '2021-01-01 00:00:00' WHERE id = ?", (first,))
        self.assertEqual([post.id for post in database.read_blog_posts(newest_first=True)],
                         [first, third, second, another])
        self.assertEqual([post.id for post in database.read_blog_posts(topic_id=self.topic_id)],
                         [first, another, third])
        self.assertEqual(database.read_blog_posts(topic_id=999), [])

    def test_post_update_preserves_identity_and_timestamp(self):
        post_id = database.create_blog_post(self.topic_id, "Original", "Body")
        original = database.read_blog_post(post_id)
        self.assertTrue(database.update_blog_post(post_id, self.topic_id, "Edited", "New body",
                                                 "Description"))
        updated = database.read_blog_post(post_id)
        self.assertEqual((updated.id, updated.timestamp), (original.id, original.timestamp))
        self.assertEqual((updated.title, updated.content, updated.description),
                         ("Edited", "New body", "Description"))

    def test_missing_crud_targets_report_none_or_false(self):
        self.assertIsNone(database.read_topic(999))
        self.assertIsNone(database.read_blog_post(999))
        self.assertFalse(database.update_topic(999, "Missing"))
        self.assertFalse(database.delete_topic(999))
        self.assertFalse(database.update_blog_post(999, self.topic_id, "Missing", "Body"))
        self.assertFalse(database.delete_blog_post(999))

    def test_schema_initialization_is_idempotent(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        database.create_db()
        self.assertEqual([topic.id for topic in database.read_topics()], [self.topic_id])
        self.assertEqual([post.id for post in database.read_blog_posts()], [post_id])

    def test_failed_transaction_restores_cascaded_deletions(self):
        """Parent deletion and cascades must roll back together on failure."""
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        with self.assertRaises(sqlite3.IntegrityError):
            with database.transaction() as conn:
                conn.execute("DELETE FROM topics WHERE id = ?", (self.topic_id,))
                conn.execute("INSERT INTO topics (title) VALUES (NULL)")
        self.assertIsNotNone(database.read_topic(self.topic_id))
        self.assertIsNotNone(database.read_blog_post(post_id))

    def test_sql_like_text_is_stored_as_data(self):
        title = "quote'; DROP TABLE topics; --"
        topic_id = database.create_topic(title, title)
        post_id = database.create_blog_post(topic_id, title, title, title)
        self.assertEqual(database.read_topic(topic_id).title, title)
        self.assertEqual(database.read_blog_post(post_id).content, title)
        self.assertEqual([post.id for post in database.read_blog_posts(topic_id=topic_id)], [post_id])
        self.assertEqual(database.read_blog_posts(topic_id="' OR 1=1 --"), [])

    def test_each_connection_enforces_foreign_keys_and_closes(self):
        for _ in range(2):
            with database.transaction() as conn:
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with self.assertRaises(sqlite3.ProgrammingError):
                conn.execute("SELECT 1")
        with self.assertRaises(RuntimeError):
            with database.transaction() as failed_conn:
                raise RuntimeError("Abort")
        with self.assertRaises(sqlite3.ProgrammingError):
            failed_conn.execute("SELECT 1")

    def test_models_use_new_names_nullable_descriptions_and_utc(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        topic = database.read_topic(self.topic_id)
        post = database.read_blog_post(post_id)
        self.assertIsInstance(topic, Topic)
        for record in (topic, post):
            self.assertIsInstance(record.timestamp, datetime)
            self.assertEqual(record.timestamp.tzinfo, timezone.utc)
            self.assertIn("description", record.model_dump())
        self.assertIn("topic_id", post.model_dump())
        self.assertNotIn("blog_entry_type", post.model_dump())
        with database.transaction() as conn:
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(blog_posts)")}
        self.assertNotIn("blog_entry_type", columns)
        # Pydantic rejects invalid model input as well as SQLite rejecting writes.
        for title in (None, "", " \t", "\u2003"):
            with self.subTest(title=title), self.assertRaises(ValidationError):
                Topic.model_validate({**topic.model_dump(), "title": title})
        for topic_id in (None, 0):
            with self.subTest(topic_id=topic_id), self.assertRaises(ValidationError):
                BlogPost.model_validate({**post.model_dump(), "topic_id": topic_id})
        values = post.model_dump()
        values.pop("topic_id")
        with self.assertRaises(ValidationError):
            BlogPost.model_validate(values)


class DatabaseCLITests(TemporaryDatabaseTestCase):
    """Check that the CLI uses the new CRUD names and preserves topic metadata."""

    def invoke(self, *args, expected_status=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        status = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                main(list(args))
            except SystemExit as error:
                status = error.code
        self.assertEqual(status, expected_status, stderr.getvalue())
        return stdout.getvalue(), stderr.getvalue()

    def markdown(self):
        path = self.directory / "post.md"
        path.write_text("# Post title\n\nMarkdown body.", encoding="utf-8")
        return str(path)

    def test_post_create_modify_reassign_delete(self):
        path = self.markdown()
        self.invoke("create", path, "--topic-id", str(self.topic_id),
                    "--description", "Keep description")
        original = database.read_blog_posts()[0]
        self.invoke("modify", str(original.id), path)
        self.assertEqual(database.read_blog_post(original.id), original)
        other_id = database.create_topic("Other")
        self.invoke("modify", str(original.id), path, "--topic-id", str(other_id))
        moved = database.read_blog_post(original.id)
        self.assertEqual(moved.topic_id, other_id)
        self.assertEqual(moved.description, "Keep description")
        self.invoke("delete", str(original.id))
        self.assertIsNone(database.read_blog_post(original.id))

    def test_create_requires_topic_and_rejects_nonexistent_topic(self):
        path = self.markdown()
        self.invoke("create", path, expected_status=2)
        self.invoke("create", path, "--topic-id", "999", expected_status=1)
        self.assertEqual(database.read_blog_posts(), [])

    def test_removed_type_option_is_rejected(self):
        self.invoke("create", self.markdown(), "--topic-id", str(self.topic_id),
                    "--type", "blog", expected_status=2)
        self.assertEqual(database.read_blog_posts(), [])

    def test_invalid_reassignment_reports_error_without_modifying_post(self):
        post_id = database.create_blog_post(self.topic_id, "Original", "Keep body")
        original = database.read_blog_post(post_id)
        _, error = self.invoke("modify", str(post_id), self.markdown(),
                               "--topic-id", "999", expected_status=1)
        self.assertIn("FOREIGN KEY", error)
        self.assertEqual(database.read_blog_post(post_id), original)

    def test_topic_commands_rename_and_cascade(self):
        self.invoke("topic-create", "Other", "--description", "Keep description")
        other = database.read_topics()[-1]
        post_id = database.create_blog_post(other.id, "Post", "Body")
        self.invoke("topic-modify", str(other.id), "Renamed")
        self.assertEqual(database.read_topic(other.id).description, "Keep description")
        self.assertEqual(database.read_blog_post(post_id).topic_id, other.id)
        output, _ = self.invoke("topics")
        self.assertIn(f"{other.id}: Renamed", output)
        self.invoke("topic-delete", str(other.id))
        self.assertIsNone(database.read_blog_post(post_id))

    def test_duplicate_and_empty_topic_titles_report_errors(self):
        self.invoke("topic-create", "Python", expected_status=1)
        self.invoke("topic-create", "", expected_status=1)
        self.invoke("topic-modify", str(self.topic_id), " \t", expected_status=1)
        self.assertEqual(database.read_topic(self.topic_id).title, "Python")


class DatabaseAPITests(TemporaryDatabaseTestCase):
    """Exercise the database-backed API without adding an HTTP client dependency."""

    def setUp(self):
        super().setUp()
        self.app = create_app()

    def get_json(self, url, expected_status=200):
        parsed = urlsplit(url)
        messages = []

        async def request():
            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(message):
                messages.append(message)

            await self.app({
                "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
                "method": "GET", "scheme": "http", "path": parsed.path,
                "raw_path": parsed.path.encode(), "query_string": parsed.query.encode(),
                "root_path": "", "headers": [], "server": ("test", 80),
                "client": ("test", 1234),
            }, receive, send)

        asyncio.run(request())
        start = next(message for message in messages if message["type"] == "http.response.start")
        body = b"".join(message.get("body", b"") for message in messages
                        if message["type"] == "http.response.body")
        self.assertEqual(start["status"], expected_status, body.decode())
        return json.loads(body)

    def test_api_returns_post_fields_without_type(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        post = self.get_json(f"/api/entries/{post_id}")
        self.assertEqual(post["id"], post_id)
        self.assertEqual(post["topic_id"], self.topic_id)
        self.assertNotIn("blog_entry_type", post)
        self.assertNotIn("blog_type", post)
        self.assertIsNone(post["description"])
        self.assertEqual(post["blog_id"], post["id"])
        self.assertEqual(self.get_json("/api/entries"), [post])

    def test_api_observes_topic_rename_reassignment_and_cascade(self):
        post_id = database.create_blog_post(self.topic_id, "Post", "Body")
        other_id = database.create_topic("Other")
        database.update_topic(self.topic_id, "Renamed")
        self.assertEqual(self.get_json(f"/api/entries?topic_id={self.topic_id}")[0]["id"], post_id)
        database.update_blog_post(post_id, other_id, "Post", "Body")
        self.assertEqual(self.get_json(f"/api/entries?topic_id={self.topic_id}"), [])
        self.assertEqual(self.get_json(f"/api/entries?topic_id={other_id}")[0]["id"], post_id)
        database.delete_topic(other_id)
        self.assertEqual(self.get_json("/api/entries"), [])
        self.get_json(f"/api/entries/{post_id}", expected_status=404)

    def test_api_rejects_invalid_topic_filters_and_post_ids(self):
        for url in ("/api/entries?topic_id=0", "/api/entries?topic_id=abc",
                    "/api/entries/0", "/api/entries/abc"):
            with self.subTest(url=url):
                self.get_json(url, expected_status=422)


if __name__ == "__main__":
    unittest.main()
