"""Run `python -m tests.manual_mobile_preview`, then open localhost:8765/qa.

Disposable local browser fixture. Never mounts its helper route in production.
All writes go to a newly created temporary SQLite database; stop with Ctrl+C.
"""
import os
import tempfile
from pathlib import Path


def main():
    with tempfile.TemporaryDirectory(prefix="omnitrackr-mobile-") as directory:
        os.environ.update(DATABASE_URL=f"sqlite:///{Path(directory).as_posix()}/preview.db",
                          ENVIRONMENT="development", TESTING="true",
                          SECRET_KEY="local-disposable-mobile-preview-only")
        # Fresh model-created schema: legacy migrations are not part of this UI fixture.
        from app import migrations
        migrations.run_migrations = lambda: None
        from app.main import app
        from app import auth, models
        from app.database import SessionLocal, engine
        from fastapi.responses import HTMLResponse
        from app.csp import nonce_html_response
        import uvicorn

        with SessionLocal() as db:
            user = models.User(username="preview", email="preview@example.invalid",
                               hashed_password=auth.get_password_hash("local-preview-only"), is_verified=True)
            db.add(user)
            db.flush()
            for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book):
                for index in range(52):
                    data = dict(user_id=user.id, title=f"A journey through the stars — chapter {index + 1}",
                                rating=8.5, review="A thoughtful story. This private note should remain private.")
                    for key, value in dict(year=2024, director="Sample director", author="Sample author",
                                           artist="Sample artist", genre="Adventure", genres="Adventure",
                                           seasons=2, episodes=12, poster_url="/static/omnitrackr_vortex.png",
                                           cover_art_url="/static/omnitrackr_vortex.png").items():
                        if hasattr(model, key):
                            data[key] = value
                    db.add(model(**data))
            db.commit()

        @app.get("/qa", response_class=HTMLResponse)
        def preview():
            response = nonce_html_response('''<!doctype html><html><head><title>Local mobile QA</title></head>
              <body style="background:#171727;color:white;font:16px sans-serif">
              <p>Disposable synthetic library: 52 titles in each category.</p>
              <script>localStorage.setItem('omnitrackr_user', JSON.stringify({id:1,username:'preview'}));</script>
              <a href="/">Open preview library</a></body></html>''')
            response.set_cookie(auth.AUTH_COOKIE_NAME, auth.create_access_token({"sub": "preview"}), httponly=True)
            return response

        try:
            uvicorn.run(app, host="127.0.0.1", port=8765)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
