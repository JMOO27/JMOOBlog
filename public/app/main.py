from contextlib import asynccontextmanager
from pathlib import Path
from typing import NoReturn

import uvicorn
from fastapi import FastAPI, HTTPException, Path as PathParameter, Query
from fastapi.staticfiles import StaticFiles
from pydantic import computed_field

from .schemas.entry import BlogPost
from .services.database import create_db, read_blog_posts, read_blog_post
from .cli import create_parser, run_command


class _EntryResponse(BlogPost):
    """Expose the post fields plus the ID name the existing frontend reads."""

    @computed_field
    @property
    def blog_id(self) -> int:
        return self.id


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/api/entries", response_model=list[_EntryResponse])
    def get_entries(
        topic_id: int | None = Query(default=None, gt=0),
    ) -> list[_EntryResponse]:
        return [
            _EntryResponse.model_validate(post.model_dump())
            for post in read_blog_posts(topic_id=topic_id, newest_first=True)
        ]

    @app.get("/api/entries/{blog_post_id}", response_model=_EntryResponse)
    def get_entry(blog_post_id: int = PathParameter(gt=0)) -> _EntryResponse:
        entry = read_blog_post(blog_post_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Entry not found")
        return _EntryResponse.model_validate(entry.model_dump())
    
    @app.get("/api/{path:path}", include_in_schema=False, response_model=None)
    def missing_api_route(path: str) -> NoReturn:
        raise HTTPException(status_code=404, detail="API endpoint not found")

    static_dir = Path(__file__).resolve().parent.parent / "static"
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
