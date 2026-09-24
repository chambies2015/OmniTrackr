"""Run `python -m tests.manual_mobile_preview`, then open localhost:8765/qa.

Disposable local browser fixture. Never mounts its helper route in production.
All writes go to a newly created temporary SQLite database; stop with Ctrl+C.
Add --quick-capture for deterministic, local-only metadata search QA: movies and
music load promptly, TV is empty, anime is slow, games fail once, and books time
out once. Games and books recover on retry for each new search query.
Add --reviews for synthetic community reviews and a private existing-title match.
Add --collections for a synthetic shared collection with an existing private book.
Add --progress for unfinished titles with private episode and reading checkpoints.
Add --friends N for 0 to 100 accepted synthetic friends (defaults to none).
Add --daily-dashboard for a compact fixture with checkpoints, an eight-entry queue,
and a checkpointed book behind 51 same-title editions. The /qa page identifies
the exact target book and includes the suggested dashboard checks. This flag
skips the default 52-title-per-category seed and works with --empty.
Open /qa/expire in a second tab to test background session-expiry cleanup.
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
    parser.add_argument('--progress', action='store_true',
                        help='Seed a local private library with episode and reading checkpoints')
    parser.add_argument('--daily-dashboard', action='store_true',
                        help='Seed checkpoints, an eight-entry queue, and a duplicate-title target beyond page one')
    parser.add_argument('--friends', type=int, default=0, metavar='N',
                        help='Seed N accepted synthetic friends for panel sizing QA (0 to 100)')
    args = parser.parse_args()
    if not 0 <= args.friends <= 100:
        parser.error('--friends must be between 0 and 100')
    daily_dashboard_note = ''
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
            for index in range(1, args.friends + 1):
                friend = models.User(username=f"preview_friend_{index:03d}",
                                     email=f"preview-friend-{index:03d}@example.invalid",
                                     hashed_password=user.hashed_password, is_verified=True)
                db.add(friend)
                db.flush()
                # Friendship rows represent accepted connections. Keep the same
                # canonical user ordering as the ordinary acceptance workflow.
                db.add(models.Friendship(user1_id=min(user.id, friend.id),
                                         user2_id=max(user.id, friend.id)))
            for model in (models.Movie, models.TVShow, models.Anime, models.VideoGame, models.Music, models.Book):
                for index in range(0 if args.empty or args.daily_dashboard else 52):
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
            if args.daily_dashboard:
                # The checkpointed edition is created after these 51 exact-title
                # matches, so ordinary first-page browsing cannot include it.
                # Completed editions do not crowd the unfinished-title prompts.
                for edition in range(1, 52):
                    db.add(models.Book(user_id=user.id, title="The Lantern Atlas", year=2024,
                                       author=f"Archive edition {edition:02d}", read=True, rating=8,
                                       review="Finished synthetic edition for exact-title navigation QA.",
                                       review_public=False, cover_art_url="/static/omnitrackr_vortex.png"))
                db.flush()
            if args.progress or args.daily_dashboard:
                from datetime import datetime
                for category, model, title, unit, position, season in (
                    ("tv-shows", models.TVShow, "Letters from Tomorrow", "episode", 4, 2),
                    ("anime", models.Anime, "A Garden After Rain", "episode", 7, None),
                    ("books", models.Book, "The Lantern Atlas", "page", 128, None),
                ):
                    data = dict(user_id=user.id, title=title, year=2024, rating=8,
                                review="My review stays separate from progress.", review_public=False)
                    if category == "books":
                        data.update(author="Dashboard target edition" if args.daily_dashboard else "Sample Author",
                                    read=False)
                    else:
                        data.update(seasons=3, episodes=24, watched=False)
                    item = model(**data)
                    db.add(item)
                    db.flush()
                    db.add(models.ProgressCheckpoint(user_id=user.id, category=category, item_id=item.id,
                        unit=unit, position=position, season=season, note="Private place reminder", revision=1,
                        updated_at=datetime.utcnow()))
                    db.add(models.NextUpItem(user_id=user.id, category=category, item_id=item.id,
                                            position={"tv-shows": 0, "anime": 1, "books": 2}[category]))
                    if args.daily_dashboard and category == "books":
                        daily_dashboard_note = (
                            f'<p>Exact navigation target: book ID <strong>{item.id}</strong>, '
                            '<strong>The Lantern Atlas</strong>, author <strong>Dashboard target edition</strong>, '
                            'with page 128 saved. Its 51 same-title editions precede it in ordinary browsing.</p>'
                            '<p>Check Continue and Next Up Open actions, expand the eight-entry queue, '
                            'reorder or remove an entry, and confirm the expanded state survives refresh. '
                            'The last entry is deliberately unavailable. Switch categories and check search '
                            'and Add anything at desktop and mobile widths.</p>'
                        )
            if args.daily_dashboard:
                for position, category, item in (
                    (3, "movies", models.Movie(user_id=user.id, title="The Quiet Observatory", year=2024,
                                               watched=False, poster_url="/static/omnitrackr_vortex.png")),
                    (4, "video-games", models.VideoGame(user_id=user.id, title="River of Small Wonders",
                                                         played=False, cover_art_url="/static/omnitrackr_vortex.png")),
                    (5, "music", models.Music(user_id=user.id, title="Northbound", artist="Sample artist",
                                              listened=False, cover_art_url="/static/omnitrackr_vortex.png")),
                    (6, "movies", models.Movie(user_id=user.id, title="Letters Across the Harbor", year=2023,
                                               watched=False, poster_url="/static/omnitrackr_vortex.png")),
                ):
                    db.add(item)
                    db.flush()
                    db.add(models.NextUpItem(user_id=user.id, category=category, item_id=item.id,
                                            position=position))
                # Queue references are intentionally polymorphic. A missing ID
                # safely represents an unavailable title in this disposable DB.
                db.add(models.NextUpItem(user_id=user.id, category="movies", item_id=2147483000, position=7))
            db.commit()

        @app.get("/qa", response_class=HTMLResponse)
        def preview():
            response = nonce_html_response('''<!doctype html><html><head><title>Local mobile QA</title></head>
              <body style="background:#171727;color:white;font:16px sans-serif">
              <p>Disposable synthetic library for local QA.</p>
              <!-- fixture notes -->
              <script>localStorage.setItem('omnitrackr_user', JSON.stringify({id:1,username:'preview'}));</script>
              <a href="/">Open preview library</a></body></html>'''.replace(
                  '<!-- fixture notes -->',
                  f'<p>Accepted synthetic friends: {args.friends}.</p>' + daily_dashboard_note))
            response.set_cookie(auth.AUTH_COOKIE_NAME, auth.create_access_token({"sub": "preview"}), httponly=True)
            return response

        @app.get("/qa/expire", response_class=HTMLResponse)
        def expire_preview_session():
            response = nonce_html_response('''<!doctype html><html><head><title>Expired local QA session</title></head>
              <body><p>The disposable preview session has expired. Keep the original library tab open
              to check that its next background request clears private editors.</p></body></html>''')
            response.delete_cookie(auth.AUTH_COOKIE_NAME)
            return response

        try:
            uvicorn.run(app, host="127.0.0.1", port=8765)
        finally:
            engine.dispose()


if __name__ == "__main__":
    main()
