"""
Entry point for the OmniTrackr API.
Provides CRUD endpoints for managing movies and TV shows.
"""
from typing import List, Optional
from datetime import datetime
import json

from fastapi import Depends, FastAPI, HTTPException, UploadFile, File, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from sqlalchemy import inspect, text

from . import crud, schemas, auth, models, email as email_utils
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

    # Check movies table for review and poster_url columns
    existing_columns = {col["name"] for col in inspector.get_columns("movies")}
    if "review" not in existing_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE movies ADD COLUMN review VARCHAR"))
            conn.commit()
    if "poster_url" not in existing_columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE movies ADD COLUMN poster_url VARCHAR"))
            conn.commit()

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

except Exception as e:
    # Best-effort migration; avoid crashing app startup if inspection fails
    print(f"Migration warning: {e}")
    pass

# Initialize FastAPI
app = FastAPI(title="OmniTrackr API", description="Manage your movies and TV shows", version="0.1.0")

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


@app.get("/movie_theater_background.jpg")
async def get_movie_theater_bg():
    bg_file = os.path.join(os.path.dirname(__file__), "static", "movie_theater_background.jpg")
    if os.path.exists(bg_file):
        return FileResponse(bg_file)
    raise HTTPException(status_code=404, detail="movie_theater_background.jpg not found")


@app.get("/film_background.jpg")
async def get_film_bg():
    bg_file = os.path.join(os.path.dirname(__file__), "static", "film_background.jpg")
    if os.path.exists(bg_file):
        return FileResponse(bg_file)
    raise HTTPException(status_code=404, detail="film_background.jpg not found")


@app.get("/favicon.ico")
async def get_favicon():
    favicon_file = os.path.join(os.path.dirname(__file__), "static", "favicon.ico")
    if os.path.exists(favicon_file):
        return FileResponse(favicon_file, media_type="image/x-icon")
    raise HTTPException(status_code=404, detail="favicon.ico not found")


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
    """Verify user email with token."""
    try:
        email = email_utils.verify_token(token, max_age=3600)  # 1 hour expiration
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or expired verification token")
    
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
    
    # Send verification email (async, non-blocking)
    try:
        await email_utils.send_verification_email(user.email, user.username, verification_token)
    except Exception as e:
        # Log error but don't fail the request
        print(f"Failed to send verification email: {e}")
    
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




