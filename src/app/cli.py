import argparse
import re
import sqlite3
from pathlib import Path

from .services import database


def positive_id(value: str) -> int:
    try:
        blog_id = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("blog_id must be a positive integer") from None
    if blog_id <= 0:
        raise argparse.ArgumentTypeError("blog_id must be a positive integer")
    return blog_id


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage Markdown entries, or start the website when no command is given."
    )
    commands = parser.add_subparsers(dest="command", metavar="{create,modify,delete}")

    create = commands.add_parser("create", aliases=["c"], help="Create an entry from a .md file.")
    create.add_argument("filepath", type=Path, help="Path to a UTF-8 Markdown file.")
    create.add_argument("--type", dest="blog_type", choices=["blog", "project"], default="blog",
                        help="Entry type (default: blog).")
    create.set_defaults(operation="create")

    modify = commands.add_parser("modify", aliases=["m"], help="Replace an entry from a .md file.")
    modify.add_argument("blog_id", type=positive_id, help="ID of the entry to replace.")
    modify.add_argument("filepath", type=Path, help="Path to the replacement UTF-8 Markdown file.")
    modify.set_defaults(operation="modify")

    delete = commands.add_parser("delete", aliases=["d"], help="Delete an entry by ID.")
    delete.add_argument("blog_id", type=positive_id, help="ID of the entry to delete.")
    delete.set_defaults(operation="delete")
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
            blog_id = database.create_entry(args.blog_type, title, content)
            print(f"Created {args.blog_type} {blog_id}: {title}")
        elif args.operation == "modify":
            existing = database.read_entry(args.blog_id)
            if existing is None or not database.update_entries(
                args.blog_id, existing.blog_type, title, content
            ):
                raise ValueError(f"Entry {args.blog_id} not found.")
            print(f"Modified entry {args.blog_id}: {title}")
        elif args.operation == "delete":
            if not database.delete_entries(args.blog_id):
                raise ValueError(f"Entry {args.blog_id} not found.")
            print(f"Deleted entry {args.blog_id}.")
    except (OSError, UnicodeError, ValueError, sqlite3.Error) as error:
        parser.exit(1, f"error: {error}\n")
