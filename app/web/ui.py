from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))
ui_router = APIRouter(prefix="/ui", tags=["ui"], include_in_schema=False)


@ui_router.get("/", response_class=HTMLResponse)
@ui_router.get("/console", response_class=HTMLResponse)
@ui_router.get("/subjects", response_class=HTMLResponse)
async def ui_console(request: Request):
    """Render the Jinja-based UI console that talks to the public API."""

    settings = get_settings()
    api_base_default = f"{request.base_url.scheme}://{request.base_url.netloc}{settings.api_prefix}"
    return templates.TemplateResponse(
        "console.html",
        {
            "request": request,
            "project_name": settings.project_name,
            "api_prefix": settings.api_prefix,
            "api_base_default": api_base_default,
        },
    )
