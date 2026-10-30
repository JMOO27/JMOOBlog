import argparse
import re
import sqlite3
from pathlib import Path

from .services import database


def positive_id(value: str) -> int:
    try:
        identifier = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("ID must be a positive integer") from None
    if identifier <= 0:
        raise argparse.ArgumentTypeError("ID must be a positive integer")
    return identifier


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage topics and Markdown posts, or start the website with no command."
    )
    commands = parser.add_subparsers(dest="command")

    create = commands.add_parser("create", aliases=["c"], help="Create an entry from a .md file.")
    create.add_argument("filepath", type=Path, help="Path to a UTF-8 Markdown file.")
    create.add_argument("--topic-id", type=positive_id, required=True,
                        help="ID of the topic this post belongs to.")
    create.add_argument("--description", help="Optional post description.")
    create.set_defaults(operation="create")

    modify = commands.add_parser("modify", aliases=["m"], help="Replace an entry from a .md file.")
    modify.add_argument("blog_post_id", type=positive_id, help="ID of the post to replace.")
    modify.add_argument("filepath", type=Path, help="Path to the replacement UTF-8 Markdown file.")
    modify.add_argument("--topic-id", type=positive_id, help="Reassign the post to this topic.")
    modify.add_argument("--description", help="Replace the post description (otherwise keep it).")
    modify.set_defaults(operation="modify")

    delete = commands.add_parser("delete", aliases=["d"], help="Delete an entry by ID.")
    delete.add_argument("blog_post_id", type=positive_id, help="ID of the post to delete.")
    delete.set_defaults(operation="delete")

    topic_create = commands.add_parser("topic-create", help="Create a topic.")
    topic_create.add_argument("title", help="A unique, nonempty topic title.")
    topic_create.add_argument("--description", help="Optional topic description.")
    topic_create.set_defaults(operation="topic-create")

    topic_modify = commands.add_parser("topic-modify", help="Rename or describe a topic.")
    topic_modify.add_argument("topic_id", type=positive_id)
    topic_modify.add_argument("title", help="The new unique, nonempty title.")
    topic_modify.add_argument("--description", help="Replace the description (otherwise keep it).")
    topic_modify.set_defaults(operation="topic-modify")

    topic_delete = commands.add_parser("topic-delete", help="Delete a topic and all its posts.")
    topic_delete.add_argument("topic_id", type=positive_id)
    topic_delete.set_defaults(operation="topic-delete")

    topics = commands.add_parser("topics", help="List topic IDs and titles.")
    topics.set_defaults(operation="topics")
    return parser


def read_markdown(filepath: Path) -> tuple[str, str]:
    filepath = filepath.expanduser()
    if filepath.suffix.lower() != ".md":
        raise ValueError("The input file must have a .md extension.")
    if not filepath.is_file():
        raise ValueError(f"Markdown file not found or not a regular file: {filepath}")

    content = filepath.read_text(encoding="utf-8-sig").strip()
    if not content:
        raise ValueError("The Markdown file is empty.")

    lines = content.splitlines()
    heading = re.fullmatch(r" {0,3}#[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*", lines[0])
    title = filepath.stem.replace("-", " ").replace("_", " ").strip()
    if heading:
        title = heading.group(1).strip()
        content = "\n".join(lines[1:]).strip()
    if not title or not content:
        raise ValueError("The Markdown file must have a nonempty title and body.")
    return title, content


def run_command(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    try:
        # Validate the whole file before creating or modifying any database data.
        if args.operation in {"create", "modify"}:
            title, content = read_markdown(args.filepath)

        database.create_db()
        if args.operation == "create":
            blog_post_id = database.create_blog_post(
                args.topic_id, title, content, args.description
            )
            print(f"Created post {blog_post_id}: {title}")
        elif args.operation == "modify":
            existing = database.read_blog_post(args.blog_post_id)
            if existing is None or not database.update_blog_post(
                args.blog_post_id,
                args.topic_id if args.topic_id is not None else existing.topic_id,
                title, content,
                args.description if args.description is not None else existing.description,
            ):
                raise ValueError(f"Post {args.blog_post_id} not found.")
            print(f"Modified post {args.blog_post_id}: {title}")
        elif args.operation == "delete":
            if not database.delete_blog_post(args.blog_post_id):
                raise ValueError(f"Post {args.blog_post_id} not found.")
            print(f"Deleted post {args.blog_post_id}.")
        elif args.operation == "topic-create":
            topic_id = database.create_topic(args.title, args.description)
            print(f"Created topic {topic_id}: {args.title}")
        elif args.operation == "topic-modify":
            existing = database.read_topic(args.topic_id)
            if existing is None or not database.update_topic(
                args.topic_id, args.title,
                args.description if args.description is not None else existing.description,
            ):
                raise ValueError(f"Topic {args.topic_id} not found.")
            print(f"Modified topic {args.topic_id}: {args.title}")
        elif args.operation == "topic-delete":
            if not database.delete_topic(args.topic_id):
                raise ValueError(f"Topic {args.topic_id} not found.")
            print(f"Deleted topic {args.topic_id} and its posts.")
        elif args.operation == "topics":
            for topic in database.read_topics():
                print(f"{topic.id}: {topic.title}")
    except (OSError, UnicodeError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"error: {error}\n")
