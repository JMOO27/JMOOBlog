import asyncio
import contextlib
import io
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

with patch.dict(os.environ, {"DATABASE_PATH": ":memory:"}):
    from public.app.main import create_app, main
    from public.app.services import database


class PostTimestampTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.object(database.settings, "DATABASE_PATH", str(Path(directory) / "test.db")))
        self.server = self.enterContext(patch("public.app.main.uvicorn.run"))
        database.create_db()
        self.topic_id = database.create_topic("Blog", "Topic description")
        self.other_topic_id = database.create_topic("Other")
        self.post_id = database.create_blog_post(self.topic_id, "Title", "Body", "Description")
        self.other_post_id = database.create_blog_post(self.topic_id, "Untouched", "Other body")
        database.create_blog_post(self.other_topic_id, "Other topic", "Other topic body")

    def invoke(self, *args, expected_status=0):
        stdout, stderr = io.StringIO(), io.StringIO()
        status = 0
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                main(["post-timestamp", *map(str, args)])
            except SystemExit as error:
                status = error.code
        self.assertEqual(status, expected_status, stderr.getvalue())
        self.server.assert_not_called()
        return stdout.getvalue(), stderr.getvalue()

    def snapshot(self):
        return database.read_topics(), database.read_blog_posts()

    def test_calendar_dates_round_trip_through_sqlite_and_models(self):
        original = database.read_blog_post(self.post_id)
        topics = database.read_topics()
        other_posts = database.read_blog_posts()[1:]
        for value, expected in [
            ("11/03/2026", "2026-11-03 05:00:00"),
            ("07/04/2026", "2026-07-04 04:00:00"),
            ("02/29/2024", "2024-02-29 05:00:00"),
            ("03/08/2026", "2026-03-08 05:00:00"),
            ("11/01/2026", "2026-11-01 04:00:00"),
            ("02/29/2000", "2000-02-29 05:00:00"),
        ]:
            with self.subTest(value=value):
                output, _ = self.invoke(self.topic_id, self.post_id, value)
                self.assertIn(f"Updated timestamp for post {self.post_id}", output)
                with database.transaction() as conn:
                    stored = conn.execute(
                        "SELECT timestamp FROM blog_posts WHERE id = ?", (self.post_id,)
                    ).fetchone()[0]
                    self.assertEqual(conn.execute("SELECT datetime(?)", (stored,)).fetchone()[0], expected)
                self.assertEqual(stored, expected)
                post = database.read_blog_post(self.post_id)
                self.assertEqual(post.timestamp, datetime.fromisoformat(expected).replace(tzinfo=timezone.utc))
                self.assertEqual(post.timestamp.astimezone(ZoneInfo("America/New_York")).strftime("%m/%d/%Y"), value)
                self.assertEqual(post.model_dump(exclude={"timestamp"}), original.model_dump(exclude={"timestamp"}))
                self.assertEqual(database.read_topics(), topics)
                self.assertEqual(database.read_blog_posts()[1:], other_posts)

    def test_invalid_dates_fail_before_touching_database(self):
        before = self.snapshot()
        for value in [
            "02/29/2025", "02/29/1900", "04/31/2026", "13/01/2026", "00/01/2026",
            "11/00/2026", "11/03/0000", "2026/11/03", "2026-11-03", "31/12/2026",
            "1/03/2026", "11/3/2026", "11/03/26", " 11/03/2026", "11/03/2026 ",
            "11 / 03 / 2026", "11/03/2026 12:00:00", "", "not a date",
            "11/03/2026'; DROP TABLE blog_posts; --",
        ]:
            with self.subTest(value=value), patch.object(database, "create_db") as initialize:
                _, error = self.invoke(self.topic_id, self.post_id, value, expected_status=2)
                self.assertIn("MM/DD/YYYY", error)
                initialize.assert_not_called()
        self.assertEqual(self.snapshot(), before)

    def test_invalid_ids_and_missing_arguments_are_rejected(self):
        before = self.snapshot()
        for args in [
            (), (1,), (1, 1), (0, 1, "11/03/2026"), (-1, 1, "11/03/2026"),
            ("abc", 1, "11/03/2026"), (1, 0, "11/03/2026"),
            (1, -1, "11/03/2026"), (1, "1.5", "11/03/2026"),
        ]:
            with self.subTest(args=args):
                self.invoke(*args, expected_status=2)
        self.assertEqual(self.snapshot(), before)

    def test_missing_post_or_wrong_topic_does_not_change_data(self):
        before = self.snapshot()
        for topic_id, post_id in [(self.topic_id, 999), (999, self.post_id), (self.other_topic_id, self.post_id)]:
            with self.subTest(topic_id=topic_id, post_id=post_id):
                _, error = self.invoke(topic_id, post_id, "11/03/2026", expected_status=1)
                self.assertIn(f"Post {post_id} not found in topic {topic_id}", error)
                self.assertEqual(self.snapshot(), before)

    def test_database_errors_report_failure(self):
        import sqlite3

        with patch.object(database, "update_blog_post_timestamp", side_effect=sqlite3.OperationalError("database is locked")):
            _, error = self.invoke(self.topic_id, self.post_id, "11/03/2026", expected_status=1)
        self.assertIn("database is locked", error)

    async def get_json(self, path):
        messages = []
        completed = asyncio.Event()

        async def receive():
            await completed.wait()
            return {"type": "http.disconnect"}

        async def send(message):
            messages.append(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                completed.set()

        await create_app()({
            "type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "GET", "scheme": "http", "path": path,
            "raw_path": path.encode(), "query_string": b"", "root_path": "",
            "headers": [], "server": ("test", 80), "client": ("test", 1234),
        }, receive, send)
        start = next(message for message in messages if message["type"] == "http.response.start")
        self.assertEqual(start["status"], 200)
        return json.loads(b"".join(message.get("body", b"") for message in messages))

    async def test_api_keeps_iso_timestamps_and_chronological_order(self):
        self.invoke(self.topic_id, self.post_id, "12/31/2025")
        self.invoke(self.topic_id, self.other_post_id, "01/01/2026")
        entry = await self.get_json(f"/api/entries/{self.post_id}")
        self.assertEqual(entry["timestamp"], "2025-12-31T05:00:00Z")
        self.assertEqual(entry["topic"]["id"], self.topic_id)
        entries = await self.get_json("/api/entries")
        ids = [entry["id"] for entry in entries]
        self.assertLess(ids.index(self.other_post_id), ids.index(self.post_id))


if __name__ == "__main__":
    unittest.main()
