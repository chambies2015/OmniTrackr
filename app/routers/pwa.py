"""Installable app support: web manifest, service worker and the offline page."""
from __future__ import annotations

import json
import os
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import app_install, share_intake
from ..csp import strict_html_response
from ..dependencies import get_db, get_optional_current_user

router = APIRouter(tags=["pwa"])
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
ICON_VERSION = "20261003-pwa-1"
SCREENSHOT_VERSION = "20261018-install-card-1"
SHORTCUT_ICON_VERSION = "20261118-app-1"

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
    # Screenshots give Android and desktop Chrome their richer install sheet.
    "screenshots": [
        {"src": f"/static/screenshots/app-library-wide.webp?v={SCREENSHOT_VERSION}", "sizes": "1280x800",
         "type": "image/webp", "form_factor": "wide", "label": "Your library as a poster shelf"},
        {"src": f"/static/screenshots/app-release-radar-narrow.webp?v={SCREENSHOT_VERSION}", "sizes": "358x799",
         "type": "image/webp", "form_factor": "narrow", "label": "Release Radar for the titles you track"},
    ],
    # Android lists the installed app in the share sheet. A link or text shared from IMDb,
    # Spotify, Goodreads, YouTube and so on lands on /share, which finds the title.
    "share_target": {
        "action": "/share",
        "method": "GET",
        "params": {"title": "title", "text": "text", "url": "url"},
    },
    # Opening the app again focuses the window that is already open instead of stacking new ones.
    "launch_handler": {"client_mode": ["navigate-existing", "auto"]},
    # Long-press the app icon (Android, computers). "Add a title" opens Add anything ready to search.
    "shortcuts": [
        {"name": "Add a title", "short_name": "Add", "url": "/?find=&utm_source=app_shortcut",
         "description": "Search for a movie, show, game, book or album and add it",
         "icons": [{"src": f"/static/icons/shortcut-add.png?v={SHORTCUT_ICON_VERSION}", "sizes": "96x96", "type": "image/png"}]},
        {"name": "Release Radar", "short_name": "Radar", "url": "/release-radar?utm_source=app_shortcut",
         "description": "What's coming out soon for the titles you track",
         "icons": [{"src": f"/static/icons/shortcut-radar.png?v={SHORTCUT_ICON_VERSION}", "sizes": "96x96", "type": "image/png"}]},
        {"name": "Pick for me", "short_name": "Pick", "url": "/pick?utm_source=app_shortcut",
         "description": "Let OmniTrackr choose what to watch, play or read next",
         "icons": [{"src": f"/static/icons/shortcut-pick.png?v={SHORTCUT_ICON_VERSION}", "sizes": "96x96", "type": "image/png"}]},
        {"name": "Daily game", "short_name": "Daily", "url": "/daily?utm_source=app_shortcut",
         "description": "Guess today's title",
         "icons": [{"src": f"/static/icons/shortcut-daily.png?v={SHORTCUT_ICON_VERSION}", "sizes": "96x96", "type": "image/png"}]},
        {"name": "Popular titles", "url": "/titles?utm_source=app_shortcut", "description": "Most-tracked titles on OmniTrackr"},
    ],
    # Lets Chrome on Android tell the page the app is already installed (navigator.getInstalledRelatedApps).
    "related_applications": [{"platform": "webapp", "url": "https://omnitrackr.xyz/manifest.webmanifest"}],
    "prefer_related_applications": False,
}


@router.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return Response(content=json.dumps(MANIFEST, separators=(",", ":")), media_type="application/manifest+json",
                    headers={"Cache-Control": "public, max-age=86400"})


@router.get("/share", include_in_schema=False)
async def share_target(
    request: Request,
    title: Optional[str] = None,
    text: Optional[str] = None,
    url: Optional[str] = None,
    user=Depends(get_optional_current_user),
):
    """Where the phone's share sheet sends a link or text: works out the title, then opens Add anything."""
    shared = share_intake.read_share(title, text, url)
    app_install.count("shared_in", request)
    client = getattr(request.app.state, "external_api_client", None)
    shared = await share_intake.lookup_extras(shared, client, signed_in=user is not None)
    path = shared.dashboard_path()
    if user is None:
        # Signed out: the log-in form opens and brings the share back afterwards.
        path = "/?next=" + quote(path, safe="") + "#login"
    response = RedirectResponse(path, status_code=303)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex"
    return response


class AppEvent(BaseModel):
    event: str = Field(..., max_length=40)
    platform: str = Field("", max_length=12)
    repeat: bool = False  # a guest open that signed in later the same day: note the member, don't count twice


@router.post("/api/app/event", status_code=204, include_in_schema=False)
def record_app_event(payload: AppEvent, request: Request, user=Depends(get_optional_current_user),
                     db: Session = Depends(get_db)):
    """Install offers, presses and home-screen opens for Site stats (whitelisted names, see app/app_install.py).

    "opened" is sent at most once a day per device by the installed app; for a signed-in member it also
    notes that they use the app, so Site stats can count members rather than devices.
    """
    if payload.event in app_install.CLIENT_EVENTS:
        if not (payload.event == "opened" and payload.repeat):
            app_install.count(payload.event, request)
        if payload.event == "opened" and user is not None:
            try:
                app_install.record_open(db, user, app_install.platform_for(payload.platform))
            except Exception:
                db.rollback()  # Analytics must never fail the app.
    return Response(status_code=204)


@router.get("/api/app/status", include_in_schema=False)
def app_status(request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """Which kinds of device the signed-in member opened the installed app on (Safari can't tell on iPhone)."""
    platforms = app_install.platforms_for(db, user) if user is not None else []
    return JSONResponse({"platforms": platforms}, headers={"Cache-Control": "private, no-store"})


@router.get("/app", include_in_schema=False)
def app_page():
    """Get the app: what adding OmniTrackr to a home screen gives you, and the steps for each device."""
    response = strict_html_response(app_install.app_page_html())
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@router.get("/sw.js", include_in_schema=False)
def service_worker():
    # Always revalidated so a new worker version is picked up on the next visit.
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript",
                        headers={"Cache-Control": "no-cache", "Service-Worker-Allowed": "/"})


# Self-contained on purpose: the service worker stores this page once and shows it for any page
# that can't load, so it can't count on the site's stylesheets being stored too. It reloads the
# page by itself when the connection comes back.
OFFLINE_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <meta name="robots" content="noindex">
  <meta name="theme-color" content="#0b0a18">
  <title>Offline - OmniTrackr</title>
  <style>
    :root { color-scheme: dark; }
    body { align-items: center; background: #0b0a18; color: #f4f2ff; display: flex; font: 16px/1.55 Inter, system-ui, -apple-system, "Segoe UI", sans-serif; justify-content: center; margin: 0; min-height: 100vh; min-height: 100dvh; padding: 24px; box-sizing: border-box; text-align: center; }
    main { max-width: 420px; }
    img { border-radius: 20px; box-shadow: 0 14px 36px rgb(0 0 0 / .5); display: block; height: 80px; margin: 0 auto 20px; width: 80px; }
    p.eyebrow { color: #2dd4bf; font-size: .75rem; font-weight: 800; letter-spacing: .1em; margin: 0 0 6px; text-transform: uppercase; }
    h1 { font: 800 1.7rem/1.2 Poppins, Inter, system-ui, sans-serif; margin: 0 0 12px; }
    p { color: #d4d0ec; margin: 0 0 22px; }
    button { background: #8b5cf6; border: 0; border-radius: 999px; color: #fff; cursor: pointer; font: 700 1rem Inter, system-ui, sans-serif; min-height: 48px; padding: 0 28px; }
    button:focus-visible { outline: 3px solid #2dd4bf; outline-offset: 3px; }
    .status { color: #aaa6cb; font-size: .88rem; margin: 18px 0 0; min-height: 1.4em; }
  </style>
</head>
<body>
  <main>
    <img src="/static/icons/icon-192.png?v=20261003-pwa-1" alt="" width="80" height="80">
    <p class="eyebrow">No connection</p>
    <h1>You're offline</h1>
    <p>OmniTrackr needs a connection to load your library. This page opens it again by itself as soon as you're back online. Nothing you saved is lost.</p>
    <button type="button" id="offlineRetry">Try again</button>
    <p class="status" id="offlineStatus" role="status" aria-live="polite"></p>
  </main>
  <script>
    (function () {
      var status = document.getElementById('offlineStatus');
      function back() {
        try {
          if (navigator.sendBeacon) navigator.sendBeacon('/api/app/event', new Blob([JSON.stringify({ event: 'offline_seen' })], { type: 'application/json' }));
        } catch (error) { /* counting is optional */ }
        window.location.reload();
      }
      document.getElementById('offlineRetry').addEventListener('click', function () {
        if (navigator.onLine === false) { status.textContent = 'Still offline. This page will reload when the connection is back.'; return; }
        back();
      });
      window.addEventListener('online', function () { status.textContent = 'Back online. Opening OmniTrackr...'; back(); });
    })();
  </script>
</body>
</html>"""


@router.get("/offline", include_in_schema=False)
def offline_page():
    response = strict_html_response(OFFLINE_PAGE)
    response.headers["Cache-Control"] = "public, max-age=86400"
    response.headers["X-Robots-Tag"] = "noindex"
    return response
