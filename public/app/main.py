from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, NoReturn

if __name__ == "__main__" and not __package__:
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    __package__ = "public.app"

import uvicorn
from fastapi import FastAPI, HTTPException, Path as PathParameter, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import computed_field

from .schemas.entry import BlogPost, Topic
from .services.database import create_db, read_blog_posts, read_blog_post, read_topic, read_topics
from .cli import create_parser, run_command


class _EntryResponse(BlogPost):
    """Expose the post fields plus the ID name the existing frontend reads."""

    @computed_field
    @property
    def blog_id(self) -> int:
        return self.id


class _ArticleResponse(_EntryResponse):
    """Include the related topic so the article can display its current title."""

    topic: Topic


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/api/entries", response_model=list[_ArticleResponse])
    def get_entries(
        topic_id: int | None = Query(default=None, gt=0),
        entry_type: Literal["blog", "project"] | None = Query(default=None, alias="type"),
    ) -> list[_ArticleResponse]:
        topics = {topic.id: topic for topic in read_topics()}
        return [
            _ArticleResponse.model_validate({**post.model_dump(), "topic": topics[post.topic_id]})
            for post in read_blog_posts(topic_id=topic_id, newest_first=True)
            if entry_type is None or (
                (topics[post.topic_id].title.strip().casefold() == "project")
                == (entry_type == "project")
            )
        ]

    @app.get("/api/entries/{blog_post_id}", response_model=_ArticleResponse)
    def get_entry(blog_post_id: int = PathParameter(gt=0)) -> _ArticleResponse:
        entry = read_blog_post(blog_post_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Entry not found")
        topic = read_topic(entry.topic_id)
        if topic is None:
            raise HTTPException(status_code=404, detail="Topic not found")
        return _ArticleResponse.model_validate({**entry.model_dump(), "topic": topic})
    
    @app.get("/api/{path:path}", include_in_schema=False, response_model=None)
    def missing_api_route(path: str) -> NoReturn:
        raise HTTPException(status_code=404, detail="API endpoint not found")

    static_dir = Path(__file__).resolve().parent.parent / "static"

    def page_response(filename: str):
        def serve_page() -> FileResponse:
            return FileResponse(static_dir / filename)
        return serve_page

    for route, filename in {
        "/home": "index.html", "/blog": "blog.html",
        "/projects": "projects.html", "/contact": "contact.html",
    }.items():
        app.add_api_route(route, page_response(filename), include_in_schema=False)

    app.mount("/", StaticFiles(directory=static_dir, html=True), name="site")
    return app


app = create_app()


def main(argv: list[str] | None = None) -> None:
    parser = create_parser()
    args = parser.parse_args(argv)
    if args.command is not None:
        run_command(args, parser)
    else:
        uvicorn.run(app, host="127.0.0.1", port=8080)


if __name__ == "__main__":
    main()
