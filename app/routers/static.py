"""
Static file serving endpoints for the OmniTrackr API.
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from .. import dashboard_assets

router = APIRouter()


@router.get("/credentials.js")
async def get_credentials():
    """Return empty credentials.js - API keys are now proxied through backend."""
    js_content = "// API Keys are now proxied through backend endpoints\n// Do not use these variables - use /api/proxy/omdb and /api/proxy/rawg instead\nconst OMDB_API_KEY = '';\nconst RAWG_API_KEY = '';\n"
    return Response(
        content=js_content, 
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Robots-Tag": "noindex, nofollow",
        }
    )


CACHE_JS_CSS = {"Cache-Control": "public, max-age=86400"}
CACHE_IMAGES = {"Cache-Control": "public, max-age=2592000"}
CACHE_VERSIONED = {"Cache-Control": "public, max-age=31536000, immutable"}


@router.get("/auth.js")
async def get_auth():
    auth_file = os.path.join(os.path.dirname(__file__), "..", "static", "auth.js")
    if os.path.exists(auth_file):
        return FileResponse(auth_file, headers=CACHE_JS_CSS)
    raise HTTPException(status_code=404, detail="auth.js not found")


@router.get("/preauth.js")
async def get_preauth():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "preauth.js"),
                        media_type="application/javascript", headers=CACHE_JS_CSS)


@router.get("/analytics.js")
async def get_analytics():
    return FileResponse(os.path.join(os.path.dirname(__file__), "..", "static", "analytics.js"),
                        media_type="application/javascript", headers=CACHE_JS_CSS)


@router.get("/app.js")
async def get_app(v: str | None = None):
    """The dashboard bundle (see app/dashboard_assets.py)."""
    script, version = dashboard_assets.bundle()
    # The page links this with a content hash, so a matching ?v= never changes.
    cache = CACHE_VERSIONED if v == version else CACHE_JS_CSS
    return Response(content=script, media_type="application/javascript", headers=cache)


@router.get("/styles.css")
async def get_styles():
    styles_file = os.path.join(os.path.dirname(__file__), "..", "static", "styles.css")
    if os.path.exists(styles_file):
        return FileResponse(styles_file, media_type="text/css", headers=CACHE_JS_CSS)
    raise HTTPException(status_code=404, detail="styles.css not found")


@router.get("/omnitrackr_vortex.png")
@router.head("/omnitrackr_vortex.png")
async def get_omnitrackr_vortex():
    bg_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_vortex.png")
    if os.path.exists(bg_file):
        return FileResponse(bg_file, media_type="image/png", headers=CACHE_IMAGES)
    raise HTTPException(status_code=404, detail="omnitrackr_vortex.png not found")


@router.get("/film_background.jpg")
@router.head("/film_background.jpg")
async def get_film_bg():
    bg_file = os.path.join(os.path.dirname(__file__), "..", "static", "film_background.jpg")
    if os.path.exists(bg_file):
        return FileResponse(bg_file, headers=CACHE_IMAGES)
    raise HTTPException(status_code=404, detail="film_background.jpg not found")


@router.get("/vortex.gif")
@router.head("/vortex.gif")
async def get_vortex_gif():
    bg_file = os.path.join(os.path.dirname(__file__), "..", "static", "vortex.gif")
    if os.path.exists(bg_file):
        return FileResponse(bg_file, media_type="image/gif", headers=CACHE_IMAGES)
    raise HTTPException(status_code=404, detail="vortex.gif not found")


# Optimized WebP renditions of the vortex artwork. The original PNG/GIF stay
# available for social previews, old caches, and browsers without WebP support.
WEBP_ASSETS = {
    "/vortex.webp": "vortex.webp",
    "/vortex-still.webp": "vortex-still.webp",
    "/omnitrackr_vortex.webp": "omnitrackr_vortex.webp",
}


def _webp_endpoint(filename: str):
    async def serve_webp():
        path = os.path.join(os.path.dirname(__file__), "..", "static", filename)
        if os.path.exists(path):
            return FileResponse(path, media_type="image/webp", headers=CACHE_IMAGES)
        raise HTTPException(status_code=404, detail=f"{filename} not found")

    serve_webp.__name__ = "get_" + filename.replace("-", "_").replace(".", "_")
    return serve_webp


for _route, _filename in WEBP_ASSETS.items():
    router.add_api_route(_route, _webp_endpoint(_filename), methods=["GET", "HEAD"], include_in_schema=False)


@router.get("/favicon.ico")
@router.head("/favicon.ico")
async def get_favicon():
    favicon_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon", headers=CACHE_IMAGES)
    raise HTTPException(status_code=404, detail="favicon.ico not found")


@router.get("/omnitrackr_favicon.ico")
@router.head("/omnitrackr_favicon.ico")
async def get_omnitrackr_favicon():
    favicon_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon", headers=CACHE_IMAGES)
    raise HTTPException(status_code=404, detail="omnitrackr_favicon.ico not found")


@router.get("/favicon.png")
@router.head("/favicon.png")
async def get_favicon_png():
    favicon_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon", headers=CACHE_IMAGES)
    raise HTTPException(status_code=404, detail="favicon.png not found")


