"""Installable app support: web manifest, service worker and the offline page."""
from __future__ import annotations

import json
import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from ..csp import strict_html_response
from ..site_chrome import message_page

router = APIRouter(tags=["pwa"])
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
ICON_VERSION = "20261003-pwa-1"

MANIFEST = {
    "id": "/",
    "name": "OmniTrackr",
    "short_name": "OmniTrackr",
    "description": "Track movies, TV, anime, games, music and books in one private library.",
    "start_url": "/?utm_source=app",
    "scope": "/",
    "display": "standalone",
    "background_color": "#0b0a18",
    "theme_color": "#0b0a18",
    "categories": ["entertainment", "lifestyle"],
    "icons": [
        {"src": f"/static/icons/icon-192.png?v={ICON_VERSION}", "sizes": "192x192", "type": "image/png", "purpose": "any"},
        {"src": f"/static/icons/icon-512.png?v={ICON_VERSION}", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        {"src": f"/static/icons/maskable-512.png?v={ICON_VERSION}", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
    ],
    "shortcuts": [
        {"name": "Release Radar", "url": "/release-radar?utm_source=app", "description": "What's coming out soon"},
        {"name": "Popular titles", "url": "/titles?utm_source=app", "description": "Most-tracked titles on OmniTrackr"},
    ],
}


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return Response(content=json.dumps(MANIFEST, separators=(",", ":")), media_type="application/manifest+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    # Always revalidated so a new worker version is picked up on the next visit.
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


@router.get("/offline", include_in_schema=False)
def offline_page():
    page = message_page(
        "Offline", "You're offline",
        "OmniTrackr needs a connection to load your library. Check your connection and try again. "
        "Nothing you saved is lost.",
        eyebrow="No connection", actions=(("Try again", "/"),),
    )
    response = strict_html_response(page)
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["X-Robots-Tag"] = "noindex"
    return response
