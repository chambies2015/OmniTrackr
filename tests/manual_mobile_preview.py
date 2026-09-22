"""Run `python -m tests.manual_mobile_preview`, then open localhost:8765/qa.

Disposable local browser fixture. Never mounts its helper route in production.
All writes go to a newly created temporary SQLite database; stop with Ctrl+C.
Add --quick-capture for deterministic, local-only metadata search QA: movies and
music load promptly, TV is empty, anime is slow, games fail once, and books time
out once. Games and books recover on retry for each new search query.
Add --reviews for synthetic community reviews and a private existing-title match.
Add --collections for a synthetic shared collection with an existing private book.
"""
import os
import argparse
import secrets
import tempfile
from pathlib import Path


def _install_quick_capture_sources(app):
    """Keep real proxy/auth behavior while replacing all upstream network access."""
    import asyncio
    from contextlib import asynccontextmanager
    import httpx

    class PreviewMetadataClient:
        def __init__(self):
            self.attempts = {}

        async def get(self, url, *, params):
            request = httpx.Request("GET", url, params=params)
            sources = {
                "https://www.omdbapi.com/": "tv" if params.get("type") == "series" else "movies",
                "https://api.rawg.io/api/games": "games",
                "https://api.jikan.moe/v4/anime": "anime",
                "https://itunes.apple.com/search": "music",
                "https://openlibrary.org/search.json": "books",
            }
            source = sources.get(url)
            if source is None:
                raise httpx.ConnectError("Unconfigured local preview metadata source", request=request)
            query = next((params[key] for key in ("t", "search", "q", "term") if key in params), "")
            key = (source, query)
            attempt = self.attempts[key] = self.attempts.get(key, 0) + 1
            delays = {"movies": 0.2, "tv": 0.4, "anime": 3.5, "games": 0.6, "music": 0.3, "books": 0.3}
            await asyncio.sleep(20 if source == "books" and attempt == 1 else delays[source])
            if source == "games" and attempt == 1:
                return httpx.Response(503, json={"detail": "Synthetic temporary failure"}, request=request)
            payloads = {
                "movies": {"Response": "True", "Title": "Preview film", "Year": "2024",
                           "Genre": "Adventure", "Director": "Preview director", "Poster": "N/A"},
                "tv": {"Response": "False", "Error": "Series not found!"},
                "anime": {"data": [{"title": "Preview anime", "year": 2024, "type": "TV",
                                    "episodes": 12, "genres": [{"name": "Adventure"}]}]},
                "games": {"results": [{"name": "Preview game", "released": "2024-01-01",
                                       "genres": [{"name": "Adventure"}]}]},
                "music": {"results": [{"collectionName": "Preview album", "artistName": "Preview artist",
                                       "releaseDate": "2024-01-01", "primaryGenreName": "Alternative"}]},
                "books": {"docs": [{"title": "Preview book", "author_name": ["Preview author"],
                                    "first_publish_year": 2024, "subject": ["Adventure"]}]},
            }
            return httpx.Response(200, json=payloads[source], request=request)

    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def preview_lifespan(application):
        async with original_lifespan(application):
            upstream_client = application.state.external_api_client
            application.state.external_api_client = PreviewMetadataClient()
            try:
                yield
            finally:
                # The original lifespan still owns and closes its real client.
                application.state.external_api_client = upstream_client

    app.router.lifespan_context = preview_lifespan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--empty', action='store_true', help='Start with an empty synthetic library for onboarding QA')
    parser.add_argument('--quick-capture', action='store_true',
                        help='Use local synthetic metadata with progressive results, failures, and retry recovery')
    parser.add_argument('--reviews', action='store_true',
                        help='Seed local public reviews for browsing, login handoff, and save QA')
    parser.add_argument('--collections', action='store_true',
                        help='Seed a local public collection and existing private title for save QA')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="omnitrackr-mobile-") as directory:
        os.environ.update(PYTHON_DOTENV_DISABLED="1", DATABASE_URL=f"sqlite:///{Path(directory).as_posix()}/preview.db",
                          ENVIRONMENT="development", TESTING="true",
                          SECRET_KEY=secrets.token_urlsafe(32))
        if args.quick_capture:
            os.environ.update(PYTHON_DOTENV_DISABLED="1", OMDB_API_KEY="local-preview-only",
                              RAWG_API_KEY="local-preview-only")
        # Fresh model-created schema: legacy migrations are not part of this UI fixture.
        from app import migrations
        migrations.run_migrations = lambda: None
        from app.main import app
        from app import auth, models
        from app.database import SessionLocal, engine
        from fastapi.responses import HTMLResponse
        from app.csp import nonce_html_response
        import uvicorn

        if args.quick_capture:
            _install_quick_capture_sources(app)

        with SessionLocal() as db:
            user = models.User(username="preview", email="preview@example.invalid",
                               hashed_password=auth.get_password_hash("local-preview-only"), is_verified=True)
            db.add(user)
            db.flush()
            for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book):
                for index in range(0 if args.empty else 52):
                    data = dict(user_id=user.id, title=f"A journey through the stars — chapter {index + 1}",
                                rating=8.5, review="A thoughtful story. This private note should remain private.")
                    for key, value in dict(year=2024, director="Sample director", author="Sample author",
                                           artist="Sample artist", genre="Adventure", genres="Adventure",
                                           seasons=2, episodes=12, poster_url="/static/omnitrackr_vortex.png",
                                           cover_art_url="/static/omnitrackr_vortex.png").items():
                        if hasattr(model, key):
                            data[key] = value
                    db.add(model(**data))
            if args.reviews:
                author = models.User(username="sample_reader", email="reader@example.invalid",
                                     hashed_password=auth.get_password_hash("local-preview-only"), is_verified=True)
                db.add(author)
                db.flush()
                titles = ["The Lantern Atlas", "River of Small Wonders", "A Garden After Rain",
                          "The Quiet Observatory", "Northbound", "Letters from Tomorrow"]
                review = (
                    "The slower opening gives the characters room to reveal their loyalties through small decisions. "
                    "I especially enjoyed the contrast between the bright setting and the uneasy conversations. "
                    "Choose this for a quiet evening when you can pay attention to details; the ending rewards that patience."
                )
                for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book):
                    for index, title in enumerate(titles):
                        data = dict(user_id=author.id, title=title, review_public=True, rating=8.5,
                                    review=review if index != 2 else "A gentle, colorful experience with memorable characters. The thoughtful pacing made a welcome change from my usual choices.")
                        for key, value in dict(year=2024, director="Sample director", author="Sample author",
                                               artist="Sample artist", genre="Adventure", genres="Adventure",
                                               seasons=1, episodes=8, poster_url="/static/omnitrackr_vortex.png",
                                               cover_art_url="/static/omnitrackr_vortex.png").items():
                            if hasattr(model, key):
                                data[key] = value
                        db.add(model(**data))
                db.add(models.Movie(user_id=user.id, title=titles[0], year=2024, rating=9.2, watched=True,
                                    review="My private review must survive the public-review save flow.",
                                    poster_url="/static/omnitrackr_vortex.png"))
            if args.collections:
                curator = models.User(username="sample_curator", email="curator@example.invalid",
                                      hashed_password=auth.get_password_hash("local-preview-only"), is_verified=True)
                db.add(curator)
                db.flush()
                collection = models.Collection(
                    user_id=curator.id, name="A quiet weekend across six worlds", is_public=True,
                    moderation_status="approved", description=(
                        "Some weekends are better spent following a small curiosity than chasing a big checklist. "
                        "These six fictional choices offer a little room to breathe, each in a different medium. "
                        "Start with the film if you have an evening free, take the album on a slow walk, or keep "
                        "the book nearby for a chapter before bed. The common thread is patient storytelling and "
                        "the pleasure of noticing details. Choose what fits your time and leave the rest for later."
                    ),
                )
                db.add(collection)
                db.flush()
                titles = ["The Quiet Observatory", "Letters from Tomorrow", "A Garden After Rain",
                          "River of Small Wonders", "Northbound", "The Lantern Atlas"]
                notes = ["A gentle film for an evening with no interruptions.",
                         "Short episodes make room for one more small mystery.",
                         "The artwork rewards a slower look at the background details.",
                         "Explore at your own pace and follow the paths that interest you.",
                         "A companion for a long walk or a quiet afternoon.",
                         "Read a chapter before bed and let the map unfold slowly."]
                categories = ["movies", "tv-shows", "anime", "video-games", "music", "books"]
                for position, (category, model, title, note) in enumerate(zip(
                    categories, (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book),
                    titles, notes,
                )):
                    data = dict(user_id=curator.id, title=title, rating=8.5,
                                review="Curator personal review is not copied.", review_public=False)
                    for key, value in dict(year=2024, director="Sample director", author="Sample author",
                                           artist="Sample artist", genre="Adventure", genres="Adventure",
                                           seasons=1, episodes=8, poster_url="/static/omnitrackr_vortex.png",
                                           cover_art_url="/static/omnitrackr_vortex.png").items():
                        if hasattr(model, key):
                            data[key] = value
                    item = model(**data)
                    db.add(item)
                    db.flush()
                    db.add(models.CollectionItem(collection_id=collection.id, category=category,
                                                 item_id=item.id, position=position, curator_note=note))
                db.add(models.Book(user_id=user.id, title=titles[-1], author="Sample author", year=2024,
                                   rating=9.2, read=True, review="My private book note must survive saving this collection.",
                                   review_public=False, cover_art_url="/static/omnitrackr_vortex.png"))
            db.commit()

        @app.get("/qa", response_class=HTMLResponse)
        def preview():
            response = nonce_html_response('''<!doctype html><html><head><title>Local mobile QA</title></head>
              <body style="background:#171727;color:white;font:16px sans-serif">
              <p>Disposable synthetic library for local QA.</p>
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
