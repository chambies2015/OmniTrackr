"""Starter public collections written by the OmniTrackr editors.

The site owner publishes them once from the Site stats page. They live in a
dedicated editors account (never a member's library), are ordinary public
collections, and can be edited, unpublished or deleted like any other.
Publishing is idempotent: a collection whose name already exists is skipped.
"""
from __future__ import annotations

import asyncio
import secrets
from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from . import auth, models

EDITOR_USERNAME = "omnitrackr_editors"
EDITOR_EMAIL = "editors@omnitrackr.xyz"

# (category, title, year, creator, note). Creator is the director, author or artist.
COLLECTIONS = [
    {
        "name": "Mind-Bending Sci-Fi Worth a Second Watch",
        "description": (
            "These are the science fiction films that reward a rewatch, because the first viewing is spent keeping up "
            "and the second is spent noticing how carefully everything was set up. Some are big studio spectacles, "
            "others were made for the price of a used car, but each one trusts you to think alongside it. "
            "Start anywhere, and leave a free evening afterwards for the conversation it will start."
        ),
        "items": [
            ("movies", "Interstellar", 2014, "Christopher Nolan", "The docking scene alone is worth it, but the father-daughter story is what stays with you."),
            ("movies", "Arrival", 2016, "Denis Villeneuve", "A first-contact film about language and grief. The ending reframes everything that came before it."),
            ("movies", "Inception", 2010, "Christopher Nolan", "A heist movie with dream logic. Watch the rules being explained in the first hour; they all come back."),
            ("movies", "Ex Machina", 2014, "Alex Garland", "Three people, one house, and a quiet question about who is testing whom."),
            ("movies", "Blade Runner 2049", 2017, "Denis Villeneuve", "Slow, enormous and gorgeous. Works even if you haven't seen the original, though it's richer if you have."),
            ("movies", "Primer", 2004, "Shane Carruth", "Made on a tiny budget and famously dense. Keep a notepad handy, and don't feel bad about pausing."),
            ("movies", "Annihilation", 2018, "Alex Garland", "Beautiful and unsettling in equal measure; the final act is best seen with the sound up."),
            ("movies", "Everything Everywhere All at Once", 2022, "Daniel Kwan and Daniel Scheinert", "Absurd, loud and unexpectedly tender. It is, underneath everything, a film about a family."),
        ],
    },
    {
        "name": "Anime Gateways: Where to Start",
        "description": (
            "If you have been meaning to try anime but never knew where to begin, start here. Every pick on this "
            "list is complete or has a satisfying first season, is easy to find with English subtitles or a dub, "
            "and shows a different side of what the medium does well: action, comedy, slow-burn fantasy and pure style. "
            "Pick the one whose note sounds most like you and give it three episodes before you decide."
        ),
        "items": [
            ("anime", "Fullmetal Alchemist: Brotherhood", 2009, None, "The safest first pick there is: a complete story with a real ending and no filler."),
            ("anime", "Cowboy Bebop", 1998, None, "Jazz, bounty hunters and space noir. Mostly standalone episodes, so it's easy to dip into."),
            ("anime", "Frieren: Beyond Journey's End", 2023, None, "A fantasy that begins after the heroes have already won. Gentle, funny and quietly moving."),
            ("anime", "Mob Psycho 100", 2016, None, "Wild animation wrapped around a very kind story about a boy who would rather be ordinary."),
            ("anime", "Jujutsu Kaisen", 2020, None, "Modern action at its sharpest, with fights that are choreographed like dance numbers."),
            ("anime", "Attack on Titan", 2013, None, "Starts as survival horror and keeps changing shape. Commit to it; it gets bigger every season."),
            ("anime", "Spirited Away", 2001, None, "A feature film, not a series, and a perfect one-evening introduction to Studio Ghibli."),
        ],
    },
    {
        "name": "Prestige TV You Can Actually Finish",
        "description": (
            "Great television is easy to start and hard to finish, so this list sticks to series with a clear shape: "
            "limited runs, short seasons, or shows that ended exactly when they meant to. Each one respects your time, "
            "and none of them will leave you waiting years for a cliffhanger to resolve. Most can be finished over a few "
            "weekends; a couple will take a month of evenings and are worth every one of them."
        ),
        "items": [
            ("tv-shows", "Chernobyl", 2019, None, "Five episodes, and among the tensest television ever made. The third episode is hard to forget."),
            ("tv-shows", "Band of Brothers", 2001, None, "Ten episodes following one company through the Second World War, told with enormous care."),
            ("tv-shows", "Fleabag", 2016, None, "Two short seasons, twelve half-hours, and a fourth wall that becomes part of the story."),
            ("tv-shows", "True Detective", 2014, None, "The first season stands entirely on its own. Two detectives, one case, seventeen years apart."),
            ("tv-shows", "Breaking Bad", 2008, None, "The long one on this list, but it builds with rare discipline right to its final scene."),
            ("tv-shows", "Dark", 2017, None, "A German time-travel mystery planned from start to finish across three seasons. Keep track of the family trees."),
            ("tv-shows", "Severance", 2022, None, "An office satire that turns into a mystery box. Short seasons, and every episode ends with a hook."),
            ("tv-shows", "The Bear", 2022, None, "Half-hour episodes that feel like a double shift in a restaurant kitchen, in the best possible way."),
        ],
    },
    {
        "name": "Cozy Games for Slow Evenings",
        "description": (
            "Not every game needs to test your reflexes. These are the ones to reach for after a long day: low pressure, "
            "gentle music, and loops that feel good in twenty-minute sessions or three-hour ones. Nothing here punishes you "
            "for walking away, and several are just as good played on a sofa next to someone watching. "
            "Most run happily on modest hardware and handhelds, too."
        ),
        "items": [
            ("video-games", "Stardew Valley", 2016, None, "The farming game that started a genre revival. Plant, fish, befriend the town, repeat happily."),
            ("video-games", "A Short Hike", 2019, None, "A small island, a mountain to climb, and about two hours of pure charm. A perfect single-evening game."),
            ("video-games", "Unpacking", 2021, None, "You unpack boxes across a life's worth of homes, and somehow tell a whole story without a word."),
            ("video-games", "Spiritfarer", 2020, None, "A management game about ferrying spirits to the afterlife. Warm, sad and beautifully drawn."),
            ("video-games", "Animal Crossing: New Horizons", 2020, None, "An island that runs on real time. Best in short daily visits rather than long binges."),
            ("video-games", "Dorfromantik", 2022, None, "Place hexagon tiles, grow a peaceful countryside, and try to beat your last score. Endlessly calming."),
            ("video-games", "Night in the Woods", 2017, None, "A small-town story about coming home and not fitting anymore, with great writing and music."),
        ],
    },
    {
        "name": "Read It, Then Watch It",
        "description": (
            "Books that became memorable films or series, paired so you can do both and argue about which was better. "
            "Each pair shows something different about adaptation: what a screen can add, what only a page can do, and "
            "what gets lost or found in between. Read first if you can, since most of these books hold surprises the "
            "adaptations give away in their opening minutes."
        ),
        "items": [
            ("books", "Dune", 1965, "Frank Herbert", "Dense but rewarding. The appendices and glossary are worth keeping a finger in."),
            ("movies", "Dune", 2021, "Denis Villeneuve", "Covers roughly the first half of the novel, and the scale of the desert finally matches the book."),
            ("books", "The Martian", 2011, "Andy Weir", "Science problems as page-turners, told with a very funny narrator."),
            ("movies", "The Martian", 2015, "Ridley Scott", "A faithful, crowd-pleasing adaptation that keeps the book's humor intact."),
            ("books", "No Country for Old Men", 2005, "Cormac McCarthy", "Spare, fast and violent, with long passages from the sheriff that give it its heart."),
            ("movies", "No Country for Old Men", 2007, "Joel Coen and Ethan Coen", "Remarkably close to the book, with almost no music and nerves on edge the entire time."),
            ("books", "Normal People", 2018, "Sally Rooney", "Two people from the same small town, told in short, precise chapters across several years."),
            ("tv-shows", "Normal People", 2020, None, "Twelve half-hour episodes that capture the book's intimacy better than most adaptations manage."),
        ],
    },
    {
        "name": "Albums for Late-Night Focus",
        "description": (
            "Records that work as a backdrop for reading, writing or thinking late at night, but also reward close "
            "listening when you give them your full attention. The list moves from ambient pieces with no vocals at all "
            "to warmer, more personal albums for when the work is done. Play them front to back; every one of these was "
            "made as a whole album rather than a collection of singles."
        ),
        "items": [
            ("music", "Ambient 1: Music for Airports", 1978, "Brian Eno", "The record that named ambient music. Designed to be ignored or listened to closely, and it works both ways."),
            ("music", "Selected Ambient Works 85-92", 1992, "Aphex Twin", "Warm, hazy electronic pieces that sound like a memory of a club rather than the club itself."),
            ("music", "Promises", 2021, "Floating Points, Pharoah Sanders & The London Symphony Orchestra", "One piece in nine movements, built from a single repeating phrase that slowly blooms."),
            ("music", "Mezzanine", 1998, "Massive Attack", "Dark, heavy and hypnotic trip-hop, best heard on good headphones."),
            ("music", "Kid A", 2000, "Radiohead", "The band's sharp turn toward electronics. Cold on the surface and surprisingly emotional underneath."),
            ("music", "In Rainbows", 2007, "Radiohead", "Radiohead at their warmest. A good one for when the focus session turns into winding down."),
            ("music", "Blonde", 2016, "Frank Ocean", "Sparse, drifting and personal; it rewards a quiet room more than any playlist shuffle."),
            ("music", "Carrie & Lowell", 2015, "Sufjan Stevens", "Hushed and heartbreaking, mostly just voice and guitar. Save it for the very end of the night."),
        ],
    },
]

MODEL_FOR = {
    "movies": models.Movie, "tv-shows": models.TVShow, "anime": models.Anime,
    "video-games": models.VideoGame, "music": models.Music, "books": models.Book,
}
IMAGE_FIELD = {"movies": "poster_url", "tv-shows": "poster_url", "anime": "poster_url",
               "video-games": "cover_art_url", "music": "cover_art_url", "books": "cover_art_url"}


def status(db: Session) -> dict:
    editor = db.query(models.User).filter_by(username=EDITOR_USERNAME).first()
    existing = set()
    if editor:
        existing = {name for name, in db.query(models.Collection.name).filter_by(user_id=editor.id).all()}
    names = [collection["name"] for collection in COLLECTIONS]
    return {
        "available": len(names),
        "published": sum(1 for name in names if name in existing),
        "names": names,
        "published_names": [name for name in names if name in existing],
    }


def _editor_account(db: Session) -> models.User:
    editor = db.query(models.User).filter_by(username=EDITOR_USERNAME).first()
    if editor is not None and (editor.email or "").lower() != EDITOR_EMAIL:
        raise ValueError(f"The username {EDITOR_USERNAME} belongs to someone else; rename it before publishing.")
    if editor is None:
        editor = models.User(username=EDITOR_USERNAME, email=EDITOR_EMAIL, is_verified=True, is_active=True,
                             hashed_password=auth.get_password_hash(secrets.token_urlsafe(24)),
                             movies_private=False, tv_shows_private=False, anime_private=False,
                             video_games_private=False, music_private=False, books_private=False)
        db.add(editor)
        db.flush()
    else:
        # Nobody can sign in to the editors account: the password is always a fresh random value.
        editor.hashed_password = auth.get_password_hash(secrets.token_urlsafe(24))
        editor.is_verified = True
        editor.is_active = True
    return editor


# ---------------------------------------------------------------- artwork (best effort)

async def _artwork(client, category: str, title: str, year: int, creator: Optional[str]) -> Optional[str]:
    """Look up cover art from the same public sources the dashboard uses. Never raises."""
    import os
    if client is None:
        return None
    try:
        if category in ("movies", "tv-shows") and os.getenv("OMDB_API_KEY"):
            params = {"t": title, "y": str(year), "type": "movie" if category == "movies" else "series",
                      "apikey": os.getenv("OMDB_API_KEY")}
            data = (await client.get("https://www.omdbapi.com/", params=params, timeout=8)).json()
            poster = data.get("Poster")
            return poster if isinstance(poster, str) and poster.startswith("http") else None
        if category == "anime":
            data = (await client.get("https://api.jikan.moe/v4/anime", params={"q": title, "limit": 1}, timeout=8)).json()
            results = data.get("data") or []
            return ((results[0].get("images") or {}).get("jpg") or {}).get("large_image_url") if results else None
        if category == "video-games" and os.getenv("RAWG_API_KEY"):
            data = (await client.get("https://api.rawg.io/api/games",
                                     params={"search": title, "page_size": 1, "key": os.getenv("RAWG_API_KEY")}, timeout=8)).json()
            results = data.get("results") or []
            return results[0].get("background_image") if results else None
        if category == "music":
            term = f"{creator or ''} {title}".strip()
            data = (await client.get("https://itunes.apple.com/search",
                                     params={"term": term, "entity": "album", "limit": 1}, timeout=8)).json()
            results = data.get("results") or []
            art = results[0].get("artworkUrl100") if results else None
            return art.replace("100x100bb", "600x600bb") if isinstance(art, str) else None
        if category == "books":
            data = (await client.get("https://openlibrary.org/search.json",
                                     params={"title": title, "author": creator or "", "limit": 1}, timeout=8)).json()
            docs = data.get("docs") or []
            cover = docs[0].get("cover_i") if docs else None
            return f"https://covers.openlibrary.org/b/id/{int(cover)}-L.jpg" if cover else None
    except Exception:
        return None
    return None


def _library_entry(db: Session, editor: models.User, category: str, title: str, year: int,
                   creator: Optional[str], image: Optional[str]):
    model = MODEL_FOR[category]
    existing = db.query(model).filter_by(user_id=editor.id, title=title).first()
    if existing is not None:
        if image and not getattr(existing, IMAGE_FIELD[category], None):
            setattr(existing, IMAGE_FIELD[category], image)
        return existing
    fields = {"user_id": editor.id, "title": title, IMAGE_FIELD[category]: image}
    if category == "movies":
        fields.update(director=creator or "", year=year, watched=True)
    elif category in ("tv-shows", "anime"):
        fields.update(year=year, watched=True)
    elif category == "video-games":
        fields.update(release_date=datetime(year, 1, 1), played=True)
    elif category == "music":
        fields.update(artist=creator or "", year=year, listened=True)
    elif category == "books":
        fields.update(author=creator or "", year=year, read=True)
    entry = model(**fields)
    db.add(entry)
    db.flush()
    return entry


async def publish(db: Session, client=None, lookup_artwork: bool = True) -> dict:
    """Create any editor collections that don't exist yet. Returns what happened."""
    from .routers.collections import _apply_automated_readiness, _collection_is_discoverable

    editor = _editor_account(db)
    existing = {name for name, in db.query(models.Collection.name).filter_by(user_id=editor.id).all()}
    created, skipped = [], []
    # Newest-first galleries then show the list in the order written above.
    for spec in reversed(COLLECTIONS):
        if spec["name"] in existing:
            skipped.append(spec["name"])
            continue
        artwork = [None] * len(spec["items"])
        if lookup_artwork and client is not None:
            artwork = await asyncio.gather(*(
                _artwork(client, category, title, year, creator) for category, title, year, creator, _ in spec["items"]
            ))
        collection = models.Collection(user_id=editor.id, name=spec["name"], description=spec["description"],
                                       is_public=True, published_at=datetime.utcnow())
        db.add(collection)
        db.flush()
        for position, ((category, title, year, creator, note), image) in enumerate(zip(spec["items"], artwork)):
            entry = _library_entry(db, editor, category, title, year, creator, image)
            db.add(models.CollectionItem(collection_id=collection.id, category=category, item_id=entry.id,
                                         position=position, curator_note=note))
        db.flush()
        cover = next((image for image in artwork if image), None)
        if cover:
            collection.cover_url = cover
        db.refresh(collection)
        _apply_automated_readiness(collection, db)
        created.append({"name": spec["name"], "listed": _collection_is_discoverable(collection, db),
                        "with_artwork": sum(1 for image in artwork if image), "items": len(spec["items"])})
    db.commit()
    return {"created": created, "skipped": skipped, "status": status(db)}
