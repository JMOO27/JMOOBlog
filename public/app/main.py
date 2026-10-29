from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal, NoReturn

import uvicorn
from fastapi import FastAPI, HTTPException, Path as PathParameter
from fastapi.staticfiles import StaticFiles

from .schemas.entry import BlogEntry
from .services.database import create_db, read_entries, read_entry
from .cli import create_parser, run_command

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)

    @app.get("/api/entries", response_model=list[BlogEntry])
    def get_entries(type: Literal["blog", "project"]) -> list[BlogEntry]:
        return read_entries(type, newest_first=True)

    @app.get("/api/entries/{blog_id}", response_model=BlogEntry)
    def get_entry(blog_id: int = PathParameter(gt=0)) -> BlogEntry:
        entry = read_entry(blog_id)
        if entry is None:
            raise HTTPException(status_code=404, detail="Entry not found")
        return entry
    
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
