from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.db.session import init_db
from app.api.v1.endpoints.security import seed_demo_key_from_env
from app.web.routes import web_router
from fastapi.staticfiles import StaticFiles

settings = get_settings()
app = FastAPI(title=settings.project_name)

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

app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(web_router)
