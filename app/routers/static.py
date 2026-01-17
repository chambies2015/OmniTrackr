"""
Static file serving endpoints for the OmniTrackr API.
"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

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
            "Expires": "0"
        }
    )


@router.get("/auth.js")
async def get_auth():
    auth_file = os.path.join(os.path.dirname(__file__), "..", "static", "auth.js")
    if os.path.exists(auth_file):
        return FileResponse(auth_file)
    raise HTTPException(status_code=404, detail="auth.js not found")


@router.get("/app.js")
async def get_app():
    app_file = os.path.join(os.path.dirname(__file__), "..", "static", "app.js")
    if os.path.exists(app_file):
        return FileResponse(app_file)
    raise HTTPException(status_code=404, detail="app.js not found")


@router.get("/styles.css")
async def get_styles():
    styles_file = os.path.join(os.path.dirname(__file__), "..", "static", "styles.css")
    if os.path.exists(styles_file):
        return FileResponse(styles_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")


@router.get("/omnitrackr_vortex.png")
@router.head("/omnitrackr_vortex.png")
async def get_omnitrackr_vortex():
    bg_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_vortex.png")
    if os.path.exists(bg_file):
        return FileResponse(bg_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="omnitrackr_vortex.png not found")


@router.get("/film_background.jpg")
@router.head("/film_background.jpg")
async def get_film_bg():
    bg_file = os.path.join(os.path.dirname(__file__), "..", "static", "film_background.jpg")
    if os.path.exists(bg_file):
        return FileResponse(bg_file)
    raise HTTPException(status_code=404, detail="film_background.jpg not found")


@router.get("/vortex.gif")
@router.head("/vortex.gif")
async def get_vortex_gif():
    bg_file = os.path.join(os.path.dirname(__file__), "..", "static", "vortex.gif")
    if os.path.exists(bg_file):
        return FileResponse(bg_file, media_type="image/gif")
    raise HTTPException(status_code=404, detail="vortex.gif not found")


@router.get("/favicon.ico")
@router.head("/favicon.ico")
async def get_favicon():
    favicon_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.ico not found")


@router.get("/omnitrackr_favicon.ico")
@router.head("/omnitrackr_favicon.ico")
async def get_omnitrackr_favicon():
    """Serve the OmniTrackr favicon directly."""
    favicon_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="omnitrackr_favicon.ico not found")


@router.get("/favicon.png")
@router.head("/favicon.png")
async def get_favicon_png():
    """Serve favicon as PNG (redirects to .ico version)."""
    favicon_file = os.path.join(os.path.dirname(__file__), "..", "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.png not found")



