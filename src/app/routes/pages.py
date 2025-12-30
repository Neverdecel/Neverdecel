"""Page routes for rendering HTML templates."""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def index(request: Request):
    """Render the main landing page."""
    templates = request.app.state.templates
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "title": "NEVERDECEL // DevOps & AI",
        },
    )
