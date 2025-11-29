"""
Entry point for the OmniTrackr API.
Provides CRUD endpoints for managing movies and TV shows.

Test commit for profile picture persistence verification.
"""
import json
from datetime import datetime
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
import io

from . import crud, schemas, auth, models, email as email_utils, database
from .database import Base, SessionLocal, engine

# Create the database tables
Base.metadata.create_all(bind=engine)

# Lightweight migration: add missing columns if upgrading an existing DB
try:
    inspector = inspect(engine)

    # Check users table for new authentication columns
    if inspector.has_table("users"):
        user_columns = {col["name"] for col in inspector.get_columns("users")}
        if "is_verified" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN is_verified BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("Added is_verified column to users table")
        if "verification_token" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN verification_token VARCHAR"))
                conn.commit()
                print("Added verification_token column to users table")
        if "reset_token" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_token VARCHAR"))
                conn.commit()
                print("Added reset_token column to users table")
        if "reset_token_expires" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN reset_token_expires TIMESTAMP"))
                conn.commit()
                print("Added reset_token_expires column to users table")
        if "created_at" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"))
                conn.commit()
                print("Added created_at column to users table")
        if "deactivated_at" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN deactivated_at TIMESTAMP"))
                conn.commit()
                print("Added deactivated_at column to users table")
        if "movies_private" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN movies_private BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("Added movies_private column to users table")
        if "tv_shows_private" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN tv_shows_private BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("Added tv_shows_private column to users table")
        if "statistics_private" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN statistics_private BOOLEAN DEFAULT FALSE"))
                conn.commit()
                print("Added statistics_private column to users table")
        if "profile_picture_url" not in user_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture_url VARCHAR"))
                conn.commit()
                print("Added profile_picture_url column to users table")

    # Check movies table for review and poster_url columns
    if inspector.has_table("movies"):
        existing_columns = {col["name"] for col in inspector.get_columns("movies")}
        if "review" not in existing_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE movies ADD COLUMN review VARCHAR"))
                conn.commit()
        if "poster_url" not in existing_columns:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE movies ADD COLUMN poster_url VARCHAR"))
                conn.commit()
        
        # Check if rating column exists and ensure it's FLOAT type (for decimal ratings support)
        # This handles edge cases where rating might have been created as INTEGER
        rating_column = next((col for col in inspector.get_columns("movies") if col["name"] == "rating"), None)
        if rating_column:
            # For SQLite, we can't directly change column type, but INTEGER values work fine in FLOAT columns
            # For PostgreSQL, we can alter the column type if needed
            if database.DATABASE_URL.startswith("postgresql"):
                # Check if it's not already a float/numeric type
                col_type = str(rating_column.get("type", "")).upper()
                if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                    try:
                        with engine.connect() as conn:
                            # PostgreSQL: Convert INTEGER to FLOAT
                            conn.execute(text("ALTER TABLE movies ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                            conn.commit()
                            print("Converted movies.rating column from INTEGER to FLOAT")
                    except Exception as e:
                        print(f"Note: Could not convert movies.rating column type (may already be correct): {e}")

    # Check tv_shows table for schema migration
    if inspector.has_table("tv_shows"):
        tv_columns = {col["name"] for col in inspector.get_columns("tv_shows")}

        # If we have the old schema (creator, year_started, year_ended), migrate to new schema
        if "creator" in tv_columns and "year_started" in tv_columns:
            with engine.connect() as conn:
                # Create a backup table with old data
                conn.execute(text("CREATE TABLE tv_shows_backup AS SELECT * FROM tv_shows"))

                # Drop the old table
                conn.execute(text("DROP TABLE tv_shows"))

                # Recreate the table with new schema
                conn.execute(text("""
                    CREATE TABLE tv_shows (
                        id INTEGER PRIMARY KEY,
                        title VARCHAR,
                        year INTEGER,
                        seasons INTEGER,
                        episodes INTEGER,
                        rating FLOAT,
                        watched BOOLEAN DEFAULT 0,
                        review VARCHAR,
                        poster_url VARCHAR
                    )
                """))

                # Migrate data from backup (use year_started as the year)
                conn.execute(text("""
                    INSERT INTO tv_shows (id, title, year, seasons, episodes, rating, watched, review, poster_url)
                    SELECT id, title, year_started, seasons, episodes, rating, watched, review, NULL
                    FROM tv_shows_backup
                """))

                # Drop the backup table
                conn.execute(text("DROP TABLE tv_shows_backup"))

                conn.commit()
                print("Successfully migrated tv_shows table to new schema")
        else:
            # If table exists but doesn't have poster_url column, add it
            if "poster_url" not in tv_columns:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE tv_shows ADD COLUMN poster_url VARCHAR"))
                    conn.commit()
            
            # Check if rating column exists and ensure it's FLOAT type (for decimal ratings support)
            # This handles edge cases where rating might have been created as INTEGER
            rating_column = next((col for col in inspector.get_columns("tv_shows") if col["name"] == "rating"), None)
            if rating_column:
                # For SQLite, we can't directly change column type, but INTEGER values work fine in FLOAT columns
                # For PostgreSQL, we can alter the column type if needed
                if database.DATABASE_URL.startswith("postgresql"):
                    # Check if it's not already a float/numeric type
                    col_type = str(rating_column.get("type", "")).upper()
                    if "INT" in col_type and "FLOAT" not in col_type and "NUMERIC" not in col_type and "REAL" not in col_type:
                        try:
                            with engine.connect() as conn:
                                # PostgreSQL: Convert INTEGER to FLOAT
                                conn.execute(text("ALTER TABLE tv_shows ALTER COLUMN rating TYPE FLOAT USING rating::float"))
                                conn.commit()
                                print("Converted tv_shows.rating column from INTEGER to FLOAT")
                        except Exception as e:
                            print(f"Note: Could not convert tv_shows.rating column type (may already be correct): {e}")

    # Check and create friend_requests table if it doesn't exist
    if not inspector.has_table("friend_requests"):
        with engine.connect() as conn:
            if database.DATABASE_URL.startswith("postgresql"):
                conn.execute(text("""
                    CREATE TABLE friend_requests (
                        id SERIAL PRIMARY KEY,
                        sender_id INTEGER NOT NULL REFERENCES users(id),
                        receiver_id INTEGER NOT NULL REFERENCES users(id),
                        status VARCHAR DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                """))
                conn.execute(text("CREATE INDEX ix_friend_requests_sender_id ON friend_requests(sender_id)"))
                conn.execute(text("CREATE INDEX ix_friend_requests_receiver_id ON friend_requests(receiver_id)"))
                conn.execute(text("CREATE INDEX ix_friend_requests_status ON friend_requests(status)"))
            else:
                # SQLite
                conn.execute(text("""
                    CREATE TABLE friend_requests (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sender_id INTEGER NOT NULL REFERENCES users(id),
                        receiver_id INTEGER NOT NULL REFERENCES users(id),
                        status VARCHAR DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP NOT NULL
                    )
                """))
                conn.execute(text("CREATE INDEX ix_friend_requests_sender_id ON friend_requests(sender_id)"))
                conn.execute(text("CREATE INDEX ix_friend_requests_receiver_id ON friend_requests(receiver_id)"))
                conn.execute(text("CREATE INDEX ix_friend_requests_status ON friend_requests(status)"))
            conn.commit()
            print("Created friend_requests table")

    # Check and create friendships table if it doesn't exist
    if not inspector.has_table("friendships"):
        with engine.connect() as conn:
            if database.DATABASE_URL.startswith("postgresql"):
                conn.execute(text("""
                    CREATE TABLE friendships (
                        id SERIAL PRIMARY KEY,
                        user1_id INTEGER NOT NULL REFERENCES users(id),
                        user2_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT _friendship_uc UNIQUE (user1_id, user2_id)
                    )
                """))
                conn.execute(text("CREATE INDEX ix_friendships_user1_id ON friendships(user1_id)"))
                conn.execute(text("CREATE INDEX ix_friendships_user2_id ON friendships(user2_id)"))
            else:
                # SQLite
                conn.execute(text("""
                    CREATE TABLE friendships (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user1_id INTEGER NOT NULL REFERENCES users(id),
                        user2_id INTEGER NOT NULL REFERENCES users(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user1_id, user2_id)
                    )
                """))
                conn.execute(text("CREATE INDEX ix_friendships_user1_id ON friendships(user1_id)"))
                conn.execute(text("CREATE INDEX ix_friendships_user2_id ON friendships(user2_id)"))
            conn.commit()
            print("Created friendships table")

    # Check and create notifications table if it doesn't exist
    if not inspector.has_table("notifications"):
        with engine.connect() as conn:
            if database.DATABASE_URL.startswith("postgresql"):
                conn.execute(text("""
                    CREATE TABLE notifications (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        type VARCHAR NOT NULL,
                        message VARCHAR NOT NULL,
                        friend_request_id INTEGER REFERENCES friend_requests(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        read_at TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_notifications_user_id ON notifications(user_id)"))
                conn.execute(text("CREATE INDEX ix_notifications_friend_request_id ON notifications(friend_request_id)"))
                conn.execute(text("CREATE INDEX ix_notifications_created_at ON notifications(created_at)"))
            else:
                # SQLite
                conn.execute(text("""
                    CREATE TABLE notifications (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL REFERENCES users(id),
                        type VARCHAR NOT NULL,
                        message VARCHAR NOT NULL,
                        friend_request_id INTEGER REFERENCES friend_requests(id),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        read_at TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_notifications_user_id ON notifications(user_id)"))
                conn.execute(text("CREATE INDEX ix_notifications_friend_request_id ON notifications(friend_request_id)"))
                conn.execute(text("CREATE INDEX ix_notifications_created_at ON notifications(created_at)"))
            conn.commit()
            print("Created notifications table")

except Exception as e:
    # Best-effort migration; avoid crashing app startup if inspection fails
    print(f"Migration warning: {e}")
    pass

# Initialize FastAPI
app = FastAPI(title="OmniTrackr API", description="Manage your movies and TV shows", version="0.1.0")

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup_event():
    """Run tasks on application startup."""
    # Expire old friend requests (30+ days old)
    try:
        db = SessionLocal()
        expired_count = crud.expire_friend_requests(db)
        if expired_count > 0:
            print(f"Expired {expired_count} old friend requests on startup")
        db.close()
    except Exception as e:
        print(f"Error expiring friend requests on startup: {e}")


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Only add HSTS if using HTTPS (check if request is secure)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


# Bot Detection Middleware
class BotFilterMiddleware(BaseHTTPMiddleware):
    """Filter out obvious bot/scanner requests."""
    
    # Suspicious paths that bots commonly scan
    SUSPICIOUS_PATHS = [
        "/.env", "/.env.bak", "/.env.backup", "/.env.local",
        "/.git", "/.git/config", "/.git/logs/HEAD",
        "/wp-admin", "/wp-login.php", "/wp-config.php", "/setup-config.php",
        "/wp-includes", "/wp-content", "/xmlrpc.php", "/wlwmanifest.xml",
        "/admin", "/administrator", "/phpmyadmin",
        "/.aws", "/aws-config.js", "/aws.config.js",
        "/config.json", "/config.js", "/.gitlab-ci.yml",
        "/backend/.env", "/core/.env", "/api/.env",
        "/.htaccess", "/web.config", "/.well-known",
        # WordPress common directory paths
        "/blog/", "/web/", "/wordpress/", "/website/", "/wp/", "/news/",
        "/2018/", "/2019/", "/shop/", "/wp1/", "/test/", "/media/",
        "/wp2/", "/site/", "/cms/", "/sito/",
        # API gateway and config file scanners
        "/api_gateway/", "/apis/", "/app-config", "/app.config",
        "/app.py", "/app.toml", "/app.yaml", "/app.yml", "/app/.secrets",
        "/app/config/", "/app/models/", "/app/sign.go",
        "/application.ini", "/application/config/", "/application/configs/",
        "/application/libraries/", "/appveyor.yml",
        "/aws-example", "/aws-lambda", "/aws-notifications", "/aws-nuke",
        "/aws-s3", "/aws-wrapper", "/aws.config", "/aws.ino", "/aws.md",
        "/aws.properties", "/aws.service", "/aws.show", "/aws/",
        "/awsApp", "/awsKEY", "/awsS3", "/aws_config", "/aws_cred",
        "/aws_credentials", "/aws_ec2", "/awsconfig", "/aws.yml",
        # Backend paths
        "/backend/app.js", "/backend/aws/", "/backend/config/",
        "/backend/constant", "/backend/controller", "/backend/helper",
        "/backend/index.js", "/backend/mail.js", "/backend/mailer.js",
        "/backend/mailserver.js", "/backend/node/", "/backend/server.js",
        "/backend/utils.js",
        # Config file scanners
        "/base.yaml", "/be/config.js", "/circle.yml", "/compose.yaml",
        "/conf.yaml", "/config.rb", "/config.ts", "/config.yaml", "/config.yml",
        "/config/app.js", "/config/common.js", "/config/config.exs",
        "/config/config.go", "/config/config.ino", "/config/constant.js",
        "/config/constants.js", "/config/controller.js", "/config/dev/",
        "/config/index.js", "/config/mail.js", "/config/mailer.js",
        "/config/mailserver.js", "/config/model.properties", "/config/server.js",
        "/config/sitemap.rb", "/config/storage.yml", "/config/template.js",
        "/config/utils.js", "/configs/",
        # Development/staging/production paths
        "/dev/app.js", "/dev/config.js", "/dev/config/", "/dev/constant.js",
        "/dev/constants.js", "/dev/controller.js", "/dev/helper.js",
        "/dev/index.js", "/dev/mail.js", "/dev/mailer.js", "/dev/mailserver.js",
        "/dev/server.js", "/dev/utils.js",
        "/staging/config.js", "/staging/config/", "/staging/index.js",
        "/prod/config.js", "/qa/config.js",
        # Server paths
        "/server/app.js", "/server/config.js", "/server/config/",
        "/server/configs/", "/server/constant.js", "/server/constants.js",
        "/server/controller.js", "/server/helper.js", "/server/helper/",
        "/server/index.js", "/server/mail.js", "/server/mailer.js",
        "/server/mailserver.js", "/server/main.go", "/server/server.js",
        "/server/src/", "/server/utils.js",
        # Source paths
        "/src/FileUpload.js", "/src/Utils/", "/src/app.js", "/src/app/services/",
        "/src/aws.ts", "/src/config.ts", "/src/config/", "/src/constant.js",
        "/src/constants.js", "/src/constants.ts", "/src/controller.js",
        "/src/helper.js", "/src/helpers/", "/src/index.js", "/src/lib/",
        "/src/libs/", "/src/mail.js", "/src/mailer.js", "/src/mailserver.js",
        "/src/main.py", "/src/main.rb", "/src/s3.ts", "/src/server.js",
        "/src/src.js", "/src/utils.js",
        # Web paths
        "/web/app.js", "/web/config/", "/web/constant.js", "/web/constants.js",
        "/web/controller.js", "/web/helper.js", "/web/index.js", "/web/mail.js",
        "/web/mailer.js", "/web/mailserver.js", "/web/server.js", "/web/utils.js",
        "/web/web.js", "/website/index.js",
        # Helper/utils paths
        "/helper.js", "/helper/", "/helpers/", "/utils.js", "/utils/",
        # Mail paths
        "/mail.js", "/mailer.js", "/mailserver.js",
        # Common config files
        "/constant.js", "/constants.ini", "/constants.js", "/constants.json",
        "/constants.ts", "/constants.yml", "/controller.js", "/index.js",
        "/index.md", "/index.ts", "/main.go", "/readme.md", "/server.js",
        # Other paths
        "/cron/", "/default.ts", "/elb.rb", "/libs/", "/minio.md",
        "/model/", "/partner/", "/providers/", "/recipes/", "/scripts/",
        "/shared/", "/user/",
        # CI/CD and hidden files
        "/.remote", "/.local", "/.production", "/.aws-secrets",
        "/.cirrus.yml", "/.drone.yml", "/.git-secrets", "/.jaynes.yml",
        "/.lakectl.yaml", "/.properties", "/.sync.yml", "/.travis.old.yml",
        "/.travis.yml", "/.docker/",
        # Connect paths
        "/connect/",
    ]
    
    # Suspicious user agents (common scanners)
    SUSPICIOUS_AGENTS = [
        "sqlmap", "nikto", "nmap", "masscan", "zap",
        "acunetix", "nessus", "openvas", "w3af",
        "dirbuster", "gobuster", "dirb", "wfuzz",
    ]
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path.lower()
        user_agent = request.headers.get("user-agent", "").lower()
        
        # Check for suspicious paths
        if any(suspicious in path for suspicious in self.SUSPICIOUS_PATHS):
            return StarletteResponse(
                content="Not Found",
                status_code=404,
                headers={"X-Robots-Tag": "noindex, nofollow"}
            )
        
        # Check for suspicious user agents (only block if path is also suspicious)
        if any(agent in user_agent for agent in self.SUSPICIOUS_AGENTS):
            if any(suspicious in path for suspicious in self.SUSPICIOUS_PATHS):
                return StarletteResponse(
                    content="Not Found",
                    status_code=404,
                    headers={"X-Robots-Tag": "noindex, nofollow"}
                )
        
        return await call_next(request)


# Add security middleware (order matters - add before CORS)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BotFilterMiddleware)

# Add rate limiting middleware (must be after other middleware)
app.add_middleware(SlowAPIMiddleware)

# Configure CORS to allow requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for the UI
import os

# Profile pictures storage directory (persistent between deployments)
# Use environment variable if set, otherwise use a data directory outside the app
PROFILE_PICTURES_BASE_DIR = os.getenv(
    "PROFILE_PICTURES_DIR",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "profile_pictures")
)
# Ensure the directory exists
os.makedirs(PROFILE_PICTURES_BASE_DIR, exist_ok=True)

# Serve profile pictures from persistent storage
# Using /profile-pictures/ path to avoid conflict with /static/ mount
@app.get("/profile-pictures/{filename}")
async def serve_profile_picture(filename: str):
    """Serve profile pictures from persistent storage."""
    return await _serve_profile_picture_internal(filename)

# Backward compatibility: redirect old /static/profile_pictures/ URLs
@app.get("/static/profile_pictures/{filename}")
async def serve_profile_picture_old(filename: str):
    """Backward compatibility endpoint for old profile picture URLs."""
    return await _serve_profile_picture_internal(filename)

async def _serve_profile_picture_internal(filename: str):
    """Serve profile pictures from persistent storage."""
    # Security: Sanitize filename to prevent path traversal attacks
    import re
    # Remove any path separators and dangerous characters
    filename = os.path.basename(filename)  # Remove any directory components
    # Only allow alphanumeric, dots, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9._-]+$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    # Construct file path
    file_path = os.path.join(PROFILE_PICTURES_BASE_DIR, filename)
    
    # Security: Normalize path and verify it's still within the base directory
    file_path = os.path.normpath(file_path)
    base_dir_normalized = os.path.normpath(PROFILE_PICTURES_BASE_DIR)
    if not file_path.startswith(base_dir_normalized):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check if file exists
    if os.path.exists(file_path) and os.path.isfile(file_path):
        # Determine content type from extension
        ext = filename.split(".")[-1].lower()
        media_types = {
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp"
        }
        media_type = media_types.get(ext, "image/jpeg")
        return FileResponse(file_path, media_type=media_type)
    raise HTTPException(status_code=404, detail="Profile picture not found")

static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Add individual file serving for assets
@app.get("/credentials.js")
async def get_credentials():
    """Serve OMDB API key from environment variable."""
    omdb_key = os.getenv("OMDB_API_KEY", "")
    js_content = f"// OMDB API Key from environment\nconst OMDB_API_KEY = '{omdb_key}';\n"
    return Response(content=js_content, media_type="application/javascript")


@app.get("/auth.js")
async def get_auth():
    auth_file = os.path.join(os.path.dirname(__file__), "static", "auth.js")
    if os.path.exists(auth_file):
        return FileResponse(auth_file)
    raise HTTPException(status_code=404, detail="auth.js not found")


@app.get("/app.js")
async def get_app():
    app_file = os.path.join(os.path.dirname(__file__), "static", "app.js")
    if os.path.exists(app_file):
        return FileResponse(app_file)
    raise HTTPException(status_code=404, detail="app.js not found")


@app.get("/styles.css")
async def get_styles():
    styles_file = os.path.join(os.path.dirname(__file__), "static", "styles.css")
    if os.path.exists(styles_file):
        return FileResponse(styles_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="styles.css not found")


@app.get("/omnitrackr_vortex.png")
@app.head("/omnitrackr_vortex.png")
async def get_omnitrackr_vortex():
    bg_file = os.path.join(os.path.dirname(__file__), "static", "omnitrackr_vortex.png")
    if os.path.exists(bg_file):
        return FileResponse(bg_file, media_type="image/png")
    raise HTTPException(status_code=404, detail="omnitrackr_vortex.png not found")


@app.get("/film_background.jpg")
@app.head("/film_background.jpg")
async def get_film_bg():
    bg_file = os.path.join(os.path.dirname(__file__), "static", "film_background.jpg")
    if os.path.exists(bg_file):
        return FileResponse(bg_file)
    raise HTTPException(status_code=404, detail="film_background.jpg not found")


@app.get("/favicon.ico")
@app.head("/favicon.ico")
async def get_favicon():
    favicon_file = os.path.join(os.path.dirname(__file__), "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.ico not found")


@app.get("/omnitrackr_favicon.ico")
@app.head("/omnitrackr_favicon.ico")
async def get_omnitrackr_favicon():
    """Serve the OmniTrackr favicon directly."""
    favicon_file = os.path.join(os.path.dirname(__file__), "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="omnitrackr_favicon.ico not found")


@app.get("/favicon.png")
@app.head("/favicon.png")
async def get_favicon_png():
    """Serve favicon as PNG (redirects to .ico version)."""
    favicon_file = os.path.join(os.path.dirname(__file__), "static", "omnitrackr_favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.png not found")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# OAuth2 scheme for token-based authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> models.User:
    """Dependency to get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    payload = auth.decode_access_token(token)
    if payload is None:
        raise credentials_exception
    
    username: str = payload.get("sub")
    if username is None:
        raise credentials_exception
    
    user = crud.get_user_by_username(db, username=username)
    if user is None or not user.is_active:
        raise credentials_exception
    
    return user

@app.get("/", tags=["root"])
@app.head("/", tags=["root"])
async def read_root():
    # Serve the HTML UI file
    html_file = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    return {"message": "OmniTrackr API is running \U0001f680"}


@app.get("/sitemap.xml", tags=["seo"])
async def get_sitemap():
    """Generate and serve sitemap.xml for SEO."""
    base_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{base_url}/</loc>
    <lastmod>{datetime.now().strftime('%Y-%m-%d')}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>"""
    
    return Response(content=sitemap, media_type="application/xml")


@app.get("/robots.txt", tags=["seo"])
async def get_robots():
    """Serve robots.txt for SEO."""
    site_url = os.getenv("SITE_URL", "https://omnitrackr.xyz")
    
    robots = f"""User-agent: *
Allow: /
Disallow: /auth/
Disallow: /api/
Disallow: /static/credentials.js

Sitemap: {site_url}/sitemap.xml"""
    
    return Response(content=robots, media_type="text/plain")


# ============================================================================
# Authentication endpoints
# ============================================================================

@app.post("/auth/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED, tags=["auth"])
async def register(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user and send verification email."""
    if crud.get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    if crud.get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Generate verification token
    verification_token = email_utils.generate_verification_token(user.email)
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = crud.create_user(db, user, hashed_password, verification_token)
    
    # Send verification email (async, non-blocking)
    try:
        await email_utils.send_verification_email(user.email, user.username, verification_token)
    except Exception as e:
        # Log error but don't fail registration
        print(f"Failed to send verification email: {e}")
    
    return db_user


@app.post("/auth/login", response_model=schemas.Token, tags=["auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login to get access token."""
    user = crud.get_user_by_username(db, form_data.username)
    if not user:
        user = crud.get_user_by_email(db, form_data.username)
    
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if account is deactivated
    if not user.is_active:
        # Check if within 90-day reactivation window
        if user.deactivated_at:
            days_since_deactivation = (datetime.utcnow() - user.deactivated_at).days
            if days_since_deactivation > 90:
                raise HTTPException(
                    status_code=403,
                    detail="Account has been permanently deactivated. It cannot be reactivated after 90 days.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                # Account is deactivated but within 90-day window
                raise HTTPException(
                    status_code=403,
                    detail=f"Account is deactivated. You can reactivate it within {90 - days_since_deactivation} days. Please use the reactivate endpoint.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            raise HTTPException(
                status_code=403,
                detail="Account is deactivated. Please reactivate your account.",
                headers={"WWW-Authenticate": "Bearer"},
            )
    
    # Check if email is verified
    if not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Please verify your email address before logging in. Check your inbox for the verification link.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth.create_access_token(data={"sub": user.username})
    return schemas.Token(access_token=access_token, token_type="bearer", user=user)


@app.get("/auth/verify-email", tags=["auth"])
async def verify_email(token: str, db: Session = Depends(get_db)):
    """Verify user email with token (handles both initial verification and email change)."""
    # First, try regular email verification (most common case)
    try:
        email = email_utils.verify_token(token, max_age=3600)  # 1 hour expiration
        # This is a regular email verification token
        user = crud.get_user_by_email(db, email)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        if user.is_verified:
            return {"message": "Email already verified"}
        
        # Mark user as verified
        user.is_verified = True
        user.verification_token = None
        db.commit()
        db.refresh(user)
        
        return {"message": "Email verified successfully! You can now use all features."}
    except HTTPException:
        raise
    except Exception:
        # Not a regular email verification token, try email change token
        try:
            old_email, new_email = email_utils.verify_email_change_token(token, max_age=3600)
            # This is an email change verification
            user = crud.get_user_by_email(db, old_email)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Verify old_email matches the user's current email
            if user.email != old_email:
                raise HTTPException(status_code=400, detail="Email change token does not match current email")
            
            # Extract stored token and new email from stored value
            if not user.verification_token or not user.verification_token.startswith("email_change:"):
                raise HTTPException(status_code=400, detail="No pending email change found")
            
            parts = user.verification_token.split(":", 2)
            if len(parts) != 3:
                raise HTTPException(status_code=400, detail="Invalid email change token format")
            
            stored_token = parts[1]
            stored_new_email = parts[2]
            
            # Verify the new email matches what's stored
            if stored_new_email != new_email:
                raise HTTPException(status_code=400, detail="Email mismatch in token")
            
            # Verify the token from URL matches the stored token
            # Handle URL encoding - FastAPI should decode it, but we'll also try unquote as fallback
            from urllib.parse import unquote
            if stored_token != token:
                # Try URL-decoded version
                decoded_token = unquote(token)
                if stored_token != decoded_token:
                    raise HTTPException(status_code=400, detail="Invalid email change token")
            
            # Check if new email is already taken
            existing_user = crud.get_user_by_email(db, new_email)
            if existing_user and existing_user.id != user.id:
                raise HTTPException(status_code=400, detail="New email is already registered")
            
            # Update email
            user.email = new_email
            user.verification_token = None
            db.commit()
            db.refresh(user)
            
            return {"message": "Email changed successfully! Your new email is now verified."}
        except HTTPException:
            raise
        except Exception:
            # Neither token type worked
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")


@app.post("/auth/resend-verification", tags=["auth"])
async def resend_verification_email(email: str, db: Session = Depends(get_db)):
    """Resend verification email to user."""
    user = crud.get_user_by_email(db, email)
    
    # Don't reveal if email exists for security (same behavior as password reset)
    if not user:
        return {"message": "If that email is registered and unverified, a verification email has been sent."}
    
    # If already verified, don't send another email
    if user.is_verified:
        return {"message": "Email is already verified. You can log in."}
    
    # Generate new verification token
    verification_token = email_utils.generate_verification_token(user.email)
    user.verification_token = verification_token
    db.commit()
    
    # Check if email credentials are configured before attempting to send
    import os
    mail_username = os.getenv("MAIL_USERNAME", "")
    mail_password = os.getenv("MAIL_PASSWORD", "")
    
    if not mail_username or not mail_password:
        print(f"WARNING: Email credentials not configured (MAIL_USERNAME or MAIL_PASSWORD missing).")
        print(f"WARNING: Verification email will NOT be sent to {user.email}.")
        print(f"WARNING: Email will only be printed to console in development mode.")
        verification_url = f"{email_utils.APP_URL}/?token={verification_token}&email_verified=true"
        print(f"INFO: Verification URL for {user.email}: {verification_url}")
        # Still return success message for security (don't reveal email wasn't sent)
        return {"message": "If that email is registered and unverified, a verification email has been sent."}
    
    # Send verification email (async, non-blocking)
    email_sent = False
    try:
        await email_utils.send_verification_email(user.email, user.username, verification_token)
        email_sent = True
        print(f"INFO: Verification email sent successfully to {user.email}")
    except Exception as e:
        # Log detailed error for debugging
        error_msg = str(e)
        print(f"ERROR: Failed to send verification email to {user.email}")
        print(f"ERROR Details: {error_msg}")
        print(f"ERROR Type: {type(e).__name__}")
        import traceback
        print(f"ERROR Traceback: {traceback.format_exc()}")
        # Check if it's a configuration issue
        if "MAIL_USERNAME" in error_msg or "MAIL_PASSWORD" in error_msg or "credentials" in error_msg.lower() or "smtp" in error_msg.lower():
            print(f"WARNING: Email credentials may be incorrect or SMTP server unreachable.")
            print(f"WARNING: Check MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER, and MAIL_PORT environment variables.")
        verification_url = f"{email_utils.APP_URL}/?token={verification_token}&email_verified=true"
        print(f"INFO: Fallback verification URL for {user.email}: {verification_url}")
        email_sent = False
    
    # Return success message (don't reveal if email actually sent for security)
    # But log the actual status for debugging
    if not email_sent:
        print(f"WARNING: Verification email was NOT sent to {user.email}, but user received success message.")
        print(f"WARNING: Check server logs above for email sending errors.")
    
    return {"message": "If that email is registered and unverified, a verification email has been sent."}


@app.post("/auth/request-password-reset", tags=["auth"])
async def request_password_reset(email: str, db: Session = Depends(get_db)):
    """Request a password reset email."""
    user = crud.get_user_by_email(db, email)
    if not user:
        # Don't reveal if email exists - security best practice
        return {"message": "If that email is registered, you will receive a password reset link."}
    
    # Generate reset token
    reset_token = email_utils.generate_reset_token(email)
    
    # Store token in database with expiration
    from datetime import datetime, timedelta
    user.reset_token = reset_token
    user.reset_token_expires = datetime.utcnow() + timedelta(hours=1)
    db.commit()
    
    # Send reset email
    try:
        await email_utils.send_password_reset_email(email, user.username, reset_token)
    except Exception as e:
        print(f"Failed to send password reset email: {e}")
    
    return {"message": "If that email is registered, you will receive a password reset link."}


@app.post("/auth/reset-password", tags=["auth"])
async def reset_password(token: str, new_password: str, db: Session = Depends(get_db)):
    """Reset password with valid token."""
    try:
        email = email_utils.verify_reset_token(token, max_age=3600)  # 1 hour expiration
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    
    user = crud.get_user_by_email(db, email)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify token matches database
    if user.reset_token != token:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    
    # Check if token expired
    from datetime import datetime
    if not user.reset_token_expires or user.reset_token_expires < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset token has expired")
    
    # Update password
    user.hashed_password = auth.get_password_hash(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.commit()
    db.refresh(user)
    
    return {"message": "Password reset successfully! You can now login with your new password."}


# ============================================================================
# Account Management endpoints
# ============================================================================

@app.get("/account/me", response_model=schemas.User, tags=["account"])
async def get_current_account(current_user: models.User = Depends(get_current_user)):
    """Get current user's account information."""
    return current_user


@app.put("/account/username", response_model=schemas.User, tags=["account"])
async def change_username(
    username_change: schemas.UsernameChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change username (requires password confirmation)."""
    # Verify password
    if not auth.verify_password(username_change.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Check if username is already taken
    existing_user = crud.get_user_by_username(db, username_change.new_username)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Update username
    try:
        user_update = schemas.UserUpdate(username=username_change.new_username)
        updated_user = crud.update_user(db, current_user.id, user_update)
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.put("/account/email", response_model=dict, tags=["account"])
async def change_email(
    email_change: schemas.EmailChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change email address (requires password + sends verification email to new address)."""
    # Verify password
    if not auth.verify_password(email_change.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Check if email is already registered
    existing_user = crud.get_user_by_email(db, email_change.new_email)
    if existing_user and existing_user.id != current_user.id:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Generate email change verification token
    email_change_token = email_utils.generate_email_change_token(current_user.email, email_change.new_email)
    
    # Store the new email and token temporarily (we'll update email after verification)
    # For now, store in verification_token field with a special prefix
    current_user.verification_token = f"email_change:{email_change_token}:{email_change.new_email}"
    db.commit()
    
    # Send verification email to new address
    try:
        await email_utils.send_email_change_verification_email(
            email_change.new_email,
            current_user.username,
            email_change_token
        )
    except Exception as e:
        print(f"Failed to send email change verification email: {e}")
        # Don't fail the request, but log the error
    
    return {
        "message": "Verification email sent to new address. Please verify your new email to complete the change."
    }


@app.put("/account/password", response_model=dict, tags=["account"])
async def change_password(
    password_change: schemas.PasswordChange,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password (requires current password)."""
    # Verify current password
    if not auth.verify_password(password_change.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect current password")
    
    # Hash new password and update
    hashed_new_password = auth.get_password_hash(password_change.new_password)
    user_update = schemas.UserUpdate(password=hashed_new_password)
    updated_user = crud.update_user(db, current_user.id, user_update)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"message": "Password changed successfully"}


@app.put("/account/privacy", response_model=schemas.PrivacySettings, tags=["account"])
async def update_privacy_settings(
    privacy_update: schemas.PrivacySettingsUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user's privacy settings."""
    updated_user = crud.update_privacy_settings(db, current_user.id, privacy_update)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return crud.get_privacy_settings(db, current_user.id)


@app.get("/account/privacy", response_model=schemas.PrivacySettings, tags=["account"])
async def get_privacy_settings(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's current privacy settings."""
    privacy_settings = crud.get_privacy_settings(db, current_user.id)
    
    if privacy_settings is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return privacy_settings


@app.post("/account/profile-picture", response_model=schemas.User, tags=["account"])
@limiter.limit("10/minute")  # Rate limit: 10 uploads per minute per IP
async def upload_profile_picture(
    request: Request,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload a profile picture with content validation and image processing."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Allowed types: JPEG, PNG, GIF, WebP"
        )
    
    # Validate file size (max 5MB)
    file_content = await file.read()
    if len(file_content) > 5 * 1024 * 1024:  # 5MB
        raise HTTPException(status_code=400, detail="File size exceeds 5MB limit")
    
    # Content validation: Verify file is actually an image using magic bytes
    try:
        # Check magic bytes (file signature) to verify it's actually an image
        image_signatures = {
            b'\xff\xd8\xff': 'jpeg',  # JPEG
            b'\x89PNG\r\n\x1a\n': 'png',  # PNG
            b'GIF87a': 'gif',  # GIF87a
            b'GIF89a': 'gif',  # GIF89a
            b'RIFF': 'webp',  # WebP (starts with RIFF, but need more checks)
        }
        
        file_signature = file_content[:12]  # Read first 12 bytes
        detected_format = None
        
        # Check JPEG
        if file_signature[:3] == b'\xff\xd8\xff':
            detected_format = 'jpeg'
        # Check PNG
        elif file_signature[:8] == b'\x89PNG\r\n\x1a\n':
            detected_format = 'png'
        # Check GIF
        elif file_signature[:6] in [b'GIF87a', b'GIF89a']:
            detected_format = 'gif'
        # Check WebP (RIFF...WEBP)
        elif file_signature[:4] == b'RIFF' and b'WEBP' in file_content[:20]:
            detected_format = 'webp'
        
        if not detected_format:
            raise HTTPException(
                status_code=400,
                detail="File is not a valid image. Content validation failed."
            )
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(
            status_code=400,
            detail="Failed to validate image content. Please ensure the file is a valid image."
        )
    
    # Process and optimize image
    if not PIL_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Image processing is not available. Please install Pillow."
        )
    
    try:
        # Open image from bytes
        image = Image.open(io.BytesIO(file_content))
        
        # Convert RGBA to RGB for JPEG (JPEG doesn't support transparency)
        if detected_format == 'jpeg' and image.mode in ('RGBA', 'LA', 'P'):
            # Create white background
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode not in ('RGB', 'RGBA', 'L', 'P'):
            image = image.convert('RGB')
        
        # Resize if image is too large (max 800x800 for profile pictures)
        max_size = (800, 800)
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Use persistent profile pictures directory
        profile_pictures_dir = PROFILE_PICTURES_BASE_DIR
        os.makedirs(profile_pictures_dir, exist_ok=True)
        
        # Generate unique filename
        import uuid
        import re
        # Use detected format or fallback to extension
        if "." in file.filename:
            file_extension = file.filename.split(".")[-1].lower()
            file_extension = re.sub(r'[^a-z0-9]', '', file_extension)
            if not file_extension:
                file_extension = detected_format or "jpg"
        else:
            file_extension = detected_format or "jpg"
        
        # Ensure extension is in allowed list
        allowed_extensions = ["jpg", "jpeg", "png", "gif", "webp"]
        if file_extension not in allowed_extensions:
            file_extension = detected_format if detected_format in allowed_extensions else "jpg"
        
        # Normalize jpeg/jpg
        if file_extension == "jpeg":
            file_extension = "jpg"
        
        # Generate unique filename with user ID and UUID
        unique_filename = f"{current_user.id}_{uuid.uuid4().hex}.{file_extension}"
        file_path = os.path.join(profile_pictures_dir, unique_filename)
        
        # Additional security: Ensure the resolved path is still within profile_pictures_dir
        file_path = os.path.normpath(file_path)
        profile_pictures_dir_normalized = os.path.normpath(profile_pictures_dir)
        if not file_path.startswith(profile_pictures_dir_normalized):
            raise HTTPException(status_code=400, detail="Invalid file path")
        
        # Delete old profile picture if exists
        if current_user.profile_picture_url:
            # Extract filename from URL (format: /profile-pictures/filename or /static/profile_pictures/filename for backward compatibility)
            old_url = current_user.profile_picture_url.lstrip("/")
            if "profile-pictures/" in old_url:
                old_filename = old_url.split("profile-pictures/")[-1]
            elif "profile_pictures/" in old_url:
                old_filename = old_url.split("profile_pictures/")[-1]
            else:
                old_filename = old_url.split("/")[-1]
            old_file_path = os.path.join(PROFILE_PICTURES_BASE_DIR, old_filename)
            if os.path.exists(old_file_path):
                try:
                    os.remove(old_file_path)
                except Exception as e:
                    print(f"Warning: Could not delete old profile picture: {e}")
        
        # Save optimized image
        output = io.BytesIO()
        save_kwargs = {}
        
        # Optimize based on format
        if file_extension in ['jpg', 'jpeg']:
            image.save(output, format='JPEG', quality=85, optimize=True)
        elif file_extension == 'png':
            image.save(output, format='PNG', optimize=True)
        elif file_extension == 'gif':
            image.save(output, format='GIF', optimize=True)
        elif file_extension == 'webp':
            image.save(output, format='WEBP', quality=85, method=6)
        else:
            image.save(output, format='JPEG', quality=85, optimize=True)
        
        # Write to file
        with open(file_path, "wb") as f:
            f.write(output.getvalue())
        
        # Update database with relative URL
        profile_picture_url = f"/profile-pictures/{unique_filename}"
        updated_user = crud.update_profile_picture(db, current_user.id, profile_picture_url)
        
        if updated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        
        return updated_user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing image: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to process image: {str(e)}"
        )


@app.delete("/account/profile-picture", response_model=schemas.User, tags=["account"])
async def reset_profile_picture(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reset/remove profile picture."""
    # Delete file if exists
    if current_user.profile_picture_url:
        # Extract filename from URL (format: /profile-pictures/filename or /static/profile_pictures/filename for backward compatibility)
        old_url = current_user.profile_picture_url.lstrip("/")
        if "profile-pictures/" in old_url:
            old_filename = old_url.split("profile-pictures/")[-1]
        elif "profile_pictures/" in old_url:
            old_filename = old_url.split("profile_pictures/")[-1]
        else:
            old_filename = old_url.split("/")[-1]
        file_path = os.path.join(PROFILE_PICTURES_BASE_DIR, old_filename)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not delete profile picture file: {e}")
    
    # Update database
    updated_user = crud.reset_profile_picture(db, current_user.id)
    
    if updated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return updated_user


@app.post("/account/deactivate", response_model=dict, tags=["account"])
async def deactivate_account(
    deactivate: schemas.AccountDeactivate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deactivate account (soft delete, requires password confirmation)."""
    # Verify password
    if not auth.verify_password(deactivate.password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    
    # Deactivate account
    deactivated_user = crud.deactivate_user(db, current_user.id)
    if deactivated_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "message": "Account deactivated. You can reactivate within 90 days. After that, your account will be permanently deleted."
    }


@app.post("/auth/reactivate", response_model=schemas.User, tags=["auth"])
async def reactivate_account_public(
    reactivate: schemas.AccountReactivate,
    db: Session = Depends(get_db)
):
    """Reactivate a deactivated account via public endpoint (within 90-day window)."""
    # Find user by username or email
    user = None
    if reactivate.username:
        user = crud.get_user_by_username(db, reactivate.username)
        if not user:
            user = crud.get_user_by_email(db, reactivate.username)
    elif reactivate.email:
        user = crud.get_user_by_email(db, reactivate.email)
    else:
        raise HTTPException(status_code=400, detail="Username or email is required")
    
    if not user:
        # Don't reveal if account exists for security
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials or account not found"
        )
    
    # Verify password
    if not auth.verify_password(reactivate.password, user.hashed_password):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials or account not found"
        )
    
    # Check if account is already active
    if user.is_active:
        raise HTTPException(status_code=400, detail="Account is already active")
    
    # Check if account was deactivated
    if not user.deactivated_at:
        raise HTTPException(status_code=400, detail="Account was not deactivated")
    
    # Reactivate account
    try:
        reactivated_user = crud.reactivate_user(db, user.id)
        if reactivated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return reactivated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/account/reactivate", response_model=schemas.User, tags=["account"])
async def reactivate_account(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Reactivate a deactivated account (within 90-day window). Requires authentication."""
    if current_user.is_active:
        raise HTTPException(status_code=400, detail="Account is already active")
    
    try:
        reactivated_user = crud.reactivate_user(db, current_user.id)
        if reactivated_user is None:
            raise HTTPException(status_code=404, detail="User not found")
        return reactivated_user
    except ValueError as e:
               raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# Friends & Notifications endpoints
# ============================================================================

@app.post("/friends/request", response_model=schemas.FriendRequestResponse, tags=["friends"])
async def send_friend_request(
    request_data: schemas.FriendRequestCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a friend request to another user by username."""
    # Find the receiver by username
    receiver = crud.get_user_by_username(db, request_data.receiver_username)
    if not receiver:
        raise HTTPException(status_code=404, detail="User not found")
    
    if receiver.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot send friend request to yourself")
    
    try:
        friend_request = crud.create_friend_request(db, current_user.id, receiver.id)
        # Refresh to load relationships
        db.refresh(friend_request)
        return friend_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/friends/requests", response_model=dict, tags=["friends"])
async def get_friend_requests(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get pending friend requests (sent and received)."""
    sent, received = crud.get_friend_requests_by_user(db, current_user.id)
    
    return {
        "sent": [schemas.FriendRequestResponse.model_validate(req) for req in sent],
        "received": [schemas.FriendRequestResponse.model_validate(req) for req in received]
    }


@app.post("/friends/requests/{request_id}/accept", response_model=schemas.FriendRequestResponse, tags=["friends"])
async def accept_friend_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept a friend request."""
    try:
        friend_request = crud.accept_friend_request(db, request_id, current_user.id)
        if not friend_request:
            raise HTTPException(status_code=404, detail="Friend request not found")
        db.refresh(friend_request)
        return friend_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/friends/requests/{request_id}/deny", response_model=schemas.FriendRequestResponse, tags=["friends"])
async def deny_friend_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Deny a friend request."""
    try:
        friend_request = crud.deny_friend_request(db, request_id, current_user.id)
        if not friend_request:
            raise HTTPException(status_code=404, detail="Friend request not found")
        db.refresh(friend_request)
        return friend_request
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/friends/requests/{request_id}", response_model=dict, tags=["friends"])
async def cancel_friend_request(
    request_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel a sent friend request."""
    try:
        friend_request = crud.cancel_friend_request(db, request_id, current_user.id)
        if not friend_request:
            raise HTTPException(status_code=404, detail="Friend request not found")
        return {"message": "Friend request cancelled"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/friends", response_model=List[schemas.FriendshipResponse], tags=["friends"])
async def get_friends(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of all friends."""
    friends = crud.get_friends(db, current_user.id)
    
    # Convert to FriendshipResponse format
    friendships = []
    for friend in friends:
        # Find the friendship record
        user1_id = min(current_user.id, friend.id)
        user2_id = max(current_user.id, friend.id)
        from sqlalchemy import and_
        friendship = db.query(models.Friendship).filter(
            and_(
                models.Friendship.user1_id == user1_id,
                models.Friendship.user2_id == user2_id
            )
        ).first()
        if friendship:
            friendships.append(schemas.FriendshipResponse(
                id=friendship.id,
                friend=friend,
                created_at=friendship.created_at
            ))
    
    return friendships


@app.delete("/friends/{friend_id}", response_model=dict, tags=["friends"])
async def unfriend_user(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Unfriend a user."""
    success = crud.remove_friendship(db, current_user.id, friend_id)
    if not success:
        raise HTTPException(status_code=404, detail="Friendship not found")
    return {"message": "Unfriended successfully"}


@app.get("/friends/{friend_id}/profile", response_model=schemas.FriendProfileSummary, tags=["friends"])
async def get_friend_profile(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's profile summary (counts only, respects privacy)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    profile = crud.get_friend_profile_summary(db, friend_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Friend not found")
    
    return profile


@app.get("/friends/{friend_id}/movies", response_model=schemas.FriendMoviesResponse, tags=["friends"])
async def get_friend_movies(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's movies list (if not private, requires friendship)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    movies = crud.get_friend_movies(db, friend_id)
    if movies is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their movies private")
    
    return schemas.FriendMoviesResponse(movies=movies, count=len(movies))


@app.get("/friends/{friend_id}/tv-shows", response_model=schemas.FriendTVShowsResponse, tags=["friends"])
async def get_friend_tv_shows(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's TV shows list (if not private, requires friendship)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    tv_shows = crud.get_friend_tv_shows(db, friend_id)
    if tv_shows is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their TV shows private")
    
    return schemas.FriendTVShowsResponse(tv_shows=tv_shows, count=len(tv_shows))


@app.get("/friends/{friend_id}/statistics", response_model=schemas.FriendStatisticsResponse, tags=["friends"])
async def get_friend_statistics(
    friend_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get friend's statistics (if not private, requires friendship, compact format)."""
    # Verify friendship
    if not crud.are_friends(db, current_user.id, friend_id):
        raise HTTPException(status_code=403, detail="You are not friends with this user")
    
    stats = crud.get_friend_statistics(db, friend_id)
    if stats is None:
        # Check if friend exists
        friend = crud.get_user_by_id(db, friend_id)
        if friend is None:
            raise HTTPException(status_code=404, detail="Friend not found")
        # Data is private
        raise HTTPException(status_code=403, detail="This user has made their statistics private")
    
    return schemas.FriendStatisticsResponse(
        watch_stats=schemas.WatchStatistics(**stats["watch_stats"]),
        rating_stats=schemas.RatingStatistics(**stats["rating_stats"]),
        generated_at=datetime.now().isoformat()
    )


@app.get("/notifications", response_model=List[schemas.NotificationResponse], tags=["notifications"])
async def get_notifications(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all notifications for the current user (newest first)."""
    notifications = crud.get_notifications(db, current_user.id)
    return [schemas.NotificationResponse.model_validate(notif) for notif in notifications]


@app.get("/notifications/count", response_model=schemas.NotificationCount, tags=["notifications"])
async def get_notification_count(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get unread notification count."""
    count = crud.get_unread_notification_count(db, current_user.id)
    return schemas.NotificationCount(count=count)


@app.delete("/notifications/{notification_id}", response_model=dict, tags=["notifications"])
async def dismiss_notification(
    notification_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Dismiss/delete a notification."""
    success = crud.delete_notification(db, notification_id, current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"message": "Notification dismissed"}


# ============================================================================
# Movie endpoints
# ============================================================================

@app.get("/movies/", response_model=List[schemas.Movie], tags=["movies"])
async def list_movies(
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return crud.get_movies(db, current_user.id, search=search, sort_by=sort_by, order=order)


@app.get("/movies/{movie_id}", response_model=schemas.Movie, tags=["movies"])
async def get_movie(movie_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_movie = crud.get_movie_by_id(db, current_user.id, movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie


@app.post("/movies/", response_model=schemas.Movie, status_code=201, tags=["movies"])
async def create_movie(movie: schemas.MovieCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.create_movie(db, current_user.id, movie)


@app.put("/movies/{movie_id}", response_model=schemas.Movie, tags=["movies"])
async def update_movie(movie_id: int, movie: schemas.MovieUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_movie = crud.update_movie(db, current_user.id, movie_id, movie)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie


@app.delete("/movies/{movie_id}", response_model=schemas.Movie, tags=["movies"])
async def delete_movie(movie_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_movie = crud.delete_movie(db, current_user.id, movie_id)
    if db_movie is None:
        raise HTTPException(status_code=404, detail="Movie not found")
    return db_movie


# TV Show endpoints
@app.get("/tv-shows/", response_model=List[schemas.TVShow], tags=["tv-shows"])
async def list_tv_shows(
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        order: Optional[str] = None,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    return crud.get_tv_shows(db, current_user.id, search=search, sort_by=sort_by, order=order)


@app.get("/tv-shows/{tv_show_id}", response_model=schemas.TVShow, tags=["tv-shows"])
async def get_tv_show(tv_show_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_tv_show = crud.get_tv_show_by_id(db, current_user.id, tv_show_id)
    if db_tv_show is None:
        raise HTTPException(status_code=404, detail="TV Show not found")
    return db_tv_show


@app.post("/tv-shows/", response_model=schemas.TVShow, status_code=201, tags=["tv-shows"])
async def create_tv_show(tv_show: schemas.TVShowCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return crud.create_tv_show(db, current_user.id, tv_show)


@app.put("/tv-shows/{tv_show_id}", response_model=schemas.TVShow, tags=["tv-shows"])
async def update_tv_show(tv_show_id: int, tv_show: schemas.TVShowUpdate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_tv_show = crud.update_tv_show(db, current_user.id, tv_show_id, tv_show)
    if db_tv_show is None:
        raise HTTPException(status_code=404, detail="TV Show not found")
    return db_tv_show


@app.delete("/tv-shows/{tv_show_id}", response_model=schemas.TVShow, tags=["tv-shows"])
async def delete_tv_show(tv_show_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    db_tv_show = crud.delete_tv_show(db, current_user.id, tv_show_id)
    if db_tv_show is None:
        raise HTTPException(status_code=404, detail="TV Show not found")
    return db_tv_show


# Export/Import endpoints
@app.get("/export/", response_model=schemas.ExportData, tags=["export-import"])
async def export_data(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Export all movies and TV shows as JSON"""
    movies = crud.get_all_movies(db, current_user.id)
    tv_shows = crud.get_all_tv_shows(db, current_user.id)

    export_metadata = {
        "export_timestamp": datetime.now().isoformat(),
        "version": "1.0",
        "total_movies": len(movies),
        "total_tv_shows": len(tv_shows)
    }

    return schemas.ExportData(
        movies=movies,
        tv_shows=tv_shows,
        export_metadata=export_metadata
    )


@app.post("/import/", response_model=schemas.ImportResult, tags=["export-import"])
async def import_data(import_data: schemas.ImportData, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Import movies and TV shows from JSON data"""
    movies_created, movies_updated, movie_errors = crud.import_movies(db, current_user.id, import_data.movies)
    tv_shows_created, tv_shows_updated, tv_show_errors = crud.import_tv_shows(db, current_user.id, import_data.tv_shows)

    all_errors = movie_errors + tv_show_errors

    return schemas.ImportResult(
        movies_created=movies_created,
        movies_updated=movies_updated,
        tv_shows_created=tv_shows_created,
        tv_shows_updated=tv_shows_updated,
        errors=all_errors
    )


@app.post("/import/file/", response_model=schemas.ImportResult, tags=["export-import"])
async def import_from_file(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Import data from a JSON file upload"""
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="File must be a JSON file")

    try:
        content = await file.read()
        data = json.loads(content.decode('utf-8'))

        # Validate the imported data structure
        if 'movies' not in data or 'tv_shows' not in data:
            raise HTTPException(status_code=400, detail="Invalid file format. Expected 'movies' and 'tv_shows' arrays.")

        # Convert to Pydantic models
        movies = [schemas.MovieCreate(**movie) for movie in data.get('movies', [])]
        tv_shows = [schemas.TVShowCreate(**tv_show) for tv_show in data.get('tv_shows', [])]

        import_data = schemas.ImportData(movies=movies, tv_shows=tv_shows)

        # Import the data
        movies_created, movies_updated, movie_errors = crud.import_movies(db, current_user.id, import_data.movies)
        tv_shows_created, tv_shows_updated, tv_show_errors = crud.import_tv_shows(db, current_user.id, import_data.tv_shows)

        all_errors = movie_errors + tv_show_errors

        return schemas.ImportResult(
            movies_created=movies_created,
            movies_updated=movies_updated,
            tv_shows_created=tv_shows_created,
            tv_shows_updated=tv_shows_updated,
            errors=all_errors
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


# Statistics endpoints
@app.get("/statistics/", response_model=schemas.StatisticsDashboard, tags=["statistics"])
async def get_statistics_dashboard(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get comprehensive statistics dashboard"""
    watch_stats = crud.get_watch_statistics(db, current_user.id)
    rating_stats = crud.get_rating_statistics(db, current_user.id)
    year_stats = crud.get_year_statistics(db, current_user.id)
    director_stats = crud.get_director_statistics(db, current_user.id)

    return schemas.StatisticsDashboard(
        watch_stats=schemas.WatchStatistics(**watch_stats),
        rating_stats=schemas.RatingStatistics(**rating_stats),
        year_stats=schemas.YearStatistics(**year_stats),
        director_stats=schemas.DirectorStatistics(**director_stats),
        generated_at=datetime.now().isoformat()
    )


@app.get("/statistics/watch/", response_model=schemas.WatchStatistics, tags=["statistics"])
async def get_watch_statistics(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get watch statistics"""
    stats = crud.get_watch_statistics(db, current_user.id)
    return schemas.WatchStatistics(**stats)


@app.get("/statistics/ratings/", response_model=schemas.RatingStatistics, tags=["statistics"])
async def get_rating_statistics(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get rating statistics"""
    stats = crud.get_rating_statistics(db, current_user.id)
    return schemas.RatingStatistics(**stats)


@app.get("/statistics/years/", response_model=schemas.YearStatistics, tags=["statistics"])
async def get_year_statistics(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get year-based statistics"""
    stats = crud.get_year_statistics(db, current_user.id)
    return schemas.YearStatistics(**stats)


@app.get("/statistics/directors/", response_model=schemas.DirectorStatistics, tags=["statistics"])
async def get_director_statistics(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get director statistics"""
    stats = crud.get_director_statistics(db, current_user.id)
    return schemas.DirectorStatistics(**stats)


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




