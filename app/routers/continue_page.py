"""GET /continue: finish signing up in a real browser (see app/continue_page.py)."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query, Request

from .. import continue_page
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response

router = APIRouter(tags=["continue"])


@router.get("/continue", include_in_schema=False)
def continue_signup(request: Request,
                    invite: Optional[str] = Query(None, max_length=40),
                    came_from: Optional[str] = Query(None, alias="from", max_length=220),
                    via: Optional[str] = Query(None, max_length=10)):
    html = continue_page.page_html(
        request.headers.get("user-agent", ""),
        invite=invite,
        came_from=came_from,
        via_app=via == "app",
        member=bool(request.cookies.get(AUTH_COOKIE_NAME)),
    )
    response = strict_html_response(html)
    # The page differs inside an app's browser, and carries nothing worth caching.
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Vary"] = "User-Agent, Cookie"
    response.headers["X-Robots-Tag"] = "noindex"
    return response
