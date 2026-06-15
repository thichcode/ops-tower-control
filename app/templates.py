from fastapi.templating import Jinja2Templates
from app.config import TEMPLATES_DIR

templates = Jinja2Templates(directory=TEMPLATES_DIR)


def TemplateResponse(name: str, context: dict, **kwargs):
    """Keep router calls stable across Starlette's TemplateResponse API change."""
    request = context.get("request")
    return templates.TemplateResponse(request=request, name=name, context=context, **kwargs)
