"""
Entry point for the OmniTrackr API.
Provides CRUD endpoints for managing movies and TV shows.
"""
import os
import re
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy.orm import Session

from . import crud, schemas, models
from .database import Base, SessionLocal, engine
from .migrations import run_migrations
from .middleware import SecurityHeadersMiddleware, BotFilterMiddleware
from .dependencies import get_db
from .routers import (
    auth,
    account,
    friends,
    notifications,
    movies,
    tv_shows,
    anime,
    video_games,
    statistics,
    export_import,
    proxy,
    seo,
    static,
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Run migrations
run_migrations()

# Initialize FastAPI
app = FastAPI(title="OmniTrackr API", description="Manage your movies and TV shows", version="0.1.0")

# Initialize rate limiter
if os.getenv("TESTING", "").lower() == "true":
    limiter = Limiter(key_func=lambda: "test", enabled=False)
else:
    limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup_event():
    """Run tasks on application startup."""
    try:
        db = SessionLocal()
        expired_count = crud.expire_friend_requests(db)
        if expired_count > 0:
            print(f"Expired {expired_count} old friend requests on startup")
        db.close()
    except Exception as e:
        print(f"Error expiring friend requests on startup: {e}")


# Add middleware
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BotFilterMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Profile pictures are now stored in the database for persistence across deployments
# Serve profile pictures from database
# Using /profile-pictures/ path to avoid conflict with /static/ mount
@app.get("/profile-pictures/{user_id}")
async def serve_profile_picture(user_id: int, db: Session = Depends(get_db)):
    """Serve profile pictures from database."""
    # Get user from database
    user = crud.get_user_by_id(db, user_id)
    if not user or not user.profile_picture_data:
        raise HTTPException(status_code=404, detail="Profile picture not found")
    
    # Return image data with appropriate MIME type
    mime_type = user.profile_picture_mime_type or "image/jpeg"
    return Response(content=user.profile_picture_data, media_type=mime_type)


# Backward compatibility: support old filename-based URLs (for migration period)
# This must be registered BEFORE the static mount to take precedence
@app.get("/static/profile_pictures/{filename}")
async def serve_profile_picture_old(filename: str):
    """Backward compatibility endpoint for old profile picture URLs."""
    # Try to extract user_id from filename (format: {user_id}_{uuid}.{ext})
    match = re.match(r'^(\d+)_', filename)
    if match:
        user_id = int(match.group(1))
        # Redirect to new endpoint
        return RedirectResponse(url=f"/profile-pictures/{user_id}", status_code=301)
    raise HTTPException(status_code=404, detail="Profile picture not found")


# Mount static files for the UI
# This must be AFTER the backward compatibility route to allow it to take precedence
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Include routers
app.include_router(auth.router)

# Include account router and apply rate limiting to profile picture upload
from .routers.account import upload_profile_picture
rate_limited_profile_picture = limiter.limit("10/minute")(upload_profile_picture)
for route in account.router.routes:
    if hasattr(route, 'path') and route.path == "/account/profile-picture" and hasattr(route, 'methods') and 'POST' in route.methods:
        route.endpoint = rate_limited_profile_picture

app.include_router(account.router)
app.include_router(friends.router)
app.include_router(notifications.router)
app.include_router(movies.router)
app.include_router(tv_shows.router)
app.include_router(anime.router)
app.include_router(video_games.router)
app.include_router(statistics.router)
app.include_router(export_import.router)

# Include proxy router and apply rate limiting
# We need to wrap the endpoints with rate limiting decorators
from .routers.proxy import proxy_omdb_api, proxy_rawg_api

# Create rate-limited versions
rate_limited_omdb = limiter.limit("60/minute")(proxy_omdb_api)
rate_limited_rawg = limiter.limit("60/minute")(proxy_rawg_api)

# Replace the endpoints in the router before including it
for route in proxy.router.routes:
    if hasattr(route, 'path') and route.path == "/api/proxy/omdb":
        route.endpoint = rate_limited_omdb
    elif hasattr(route, 'path') and route.path == "/api/proxy/rawg":
        route.endpoint = rate_limited_rawg

app.include_router(proxy.router)

app.include_router(seo.router)
app.include_router(static.router)


# Root endpoint
@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def read_root():
    # Serve the HTML UI file
    html_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return {"message": "OmniTrackr API is running 🚀"}


# Public endpoint for user count
@app.get("/api/user-count", response_model=schemas.UserCount, tags=["public"])
@limiter.limit("30/minute")  # Rate limit: 30 requests per minute per IP
async def get_user_count(request: Request, db: Session = Depends(get_db)):
    """Get total number of active user accounts. Public endpoint for landing page."""
    try:
        count = db.query(models.User).filter(models.User.is_active == True).count()
        return schemas.UserCount(count=count)
    except Exception:
        # Graceful degradation: return 0 on error rather than exposing errors
        return schemas.UserCount(count=0)


# Auto-browser opening functionality
def open_browser():
    """Open the default web browser to the OmniTrackr UI"""
    import webbrowser
    import time
    import threading

    def delayed_open():
        time.sleep(2)  # Wait 2 seconds for server to start
        webbrowser.open("http://127.0.0.1:8000")

    # Start browser opening in a separate thread
    browser_thread = threading.Thread(target=delayed_open, daemon=True)
    browser_thread.start()


if __name__ == "__main__":
    import uvicorn

    open_browser()
    uvicorn.run(app, host="127.0.0.1", port=8000)
