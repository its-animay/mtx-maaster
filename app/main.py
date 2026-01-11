from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.api import api_router
from app.api.v1.endpoints.security import seed_demo_key_from_env
from app.core.config import get_settings
from app.db.session import init_db
from app.web import ui_router, web_router

settings = get_settings()
app = FastAPI(title=settings.project_name)
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
static_dir = Path(__file__).resolve().parent.parent / "static"

# CORS for frontend apps; configure origins via MQDB_CORS_ORIGINS / CORS_ORIGINS env (comma-separated)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()
    seed_demo_key_from_env()


app.include_router(api_router, prefix=settings.api_prefix)
app.include_router(web_router)
app.include_router(ui_router)

# Serve static assets for legacy/admin templates.
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Serve the lightweight subject creation UI at /frontend when the bundle exists.
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=frontend_dir, html=True), name="frontend")
