from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.engine import Engine

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_STATIC_DIR = Path(__file__).parent / "static"

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def create_app(engine: Engine) -> FastAPI:
    app = FastAPI(title="Ice Gateway")
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

    from .routes import create_router

    app.include_router(create_router(engine, templates))

    return app
