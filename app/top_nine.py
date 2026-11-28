"""Top nine (/top-nine): the year's nine favourites as a 3x3 poster grid, a picture and a link (Nov 2026).

Anyone can make one, with or without an account. A visitor searches the titles the
site already knows (members' titles, the Essential 100, the editors' picks, the
year's big releases and the browse shelves) or types any title, and the grid turns
into three pictures (a 3:4 post, a story and a link preview, app/top_nine_card.py)
and a link at /top-nine/<token>.

Whoever opens the link can tap the squares they've seen too and start their own
grid with them, which is how a grid travels from one group chat to the next.

The grid is stored as plain data (title, kind, year, creator, an allowlisted poster
URL), so a top nine never reads or changes anyone's library. Grids made without an
account have no owner: the browser that made one holds an edit key, the link stops
working after GUEST_DAYS, and signing up claims it. A member can then put the nine
into their library, marked finished (``keep``). Shared pages are always noindex.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
import unicodedata
from datetime import date, datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from . import models, tier_list, title_pages
from .review_quality import PROMOTIONAL_PHRASES
from .tier_list_shares import text_allowed

SLOTS = 9
MIN_FILLED = 3
MAX_NAME = 40
MAX_TITLE = 200
MAX_CREATOR = 120
GUEST_DAYS = 60
GUEST_MAX_LIVE = 6      # live grids per browser without an account
MEMBER_MAX = 24
CLAIM_MAX = 12
MINE_SHOWN = 24
THEMES = ("night", "paper", "berry")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{16,32}$")
SLUG = re.compile(r"^[a-z0-9-]{1,130}$")
KIND_ORDER = ("movie", "tv", "anime", "game", "album", "book", "manga", "podcast", "audiobook")
KIND_SHORT = {"movie": "Film", "tv": "Show", "anime": "Anime", "game": "Game", "album": "Album", "book": "Book",
              "manga": "Manga", "podcast": "Podcast", "audiobook": "Audiobook"}
KIND_PLURAL = {"movie": "films", "tv": "shows", "anime": "anime", "game": "games", "album": "albums",
               "book": "books", "manga": "manga", "podcast": "podcasts", "audiobook": "audiobooks"}
SEARCH_LIMIT = 12
SUGGEST_LIMIT = 60
MEMBER_OPTIONS_MAX = 36
LOVED_RATING = 8
# Combining marks allowed on one letter. Real text needs one or two (Vietnamese, Thai tone marks);
# "zalgo" text stacks dozens, which climb out of the name and the squares in the pictures.
MAX_MARKS = 2
# Right-to-left overrides and isolates turn "evil" into "live" on the page and in the pictures.
BIDI_CONTROLS = frozenset("\u202a\u202b\u202c\u202d\u202e\u2066\u2067\u2068\u2069")


class TopNineError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.utcnow()


def season_year(today: Optional[date] = None) -> int:
    """The year a new grid is about: the year that just ended through January, else this one."""
    today = today or _now().date()
    return today.year - 1 if today.month == 1 else today.year


def promo_season(today: Optional[date] = None) -> bool:
    """When the homepage and Year in Review point at the maker: Nov 25 to the end of January (year-end list
    season). The maker itself works all year."""
    today = today or _now().date()
    return (today.month, today.day) >= (11, 25) or today.month == 1


def year_words(year: int, today: Optional[date] = None) -> str:
    """ "this year" while it is that year, "in 2026" in the January after, when the grids look back."""
    today = today or _now().date()
    return "this year" if today.year == year else f"in {year}"


def hero_link_html(today: Optional[date] = None) -> str:
    """The guest homepage's "New" pill above the headline, in season."""
    if not promo_season(today):
        return ""
    year = season_year(today)
    return ('<a href="/top-nine" data-home-tool="top-nine"><span class="lp-hero__news-tag">New</span>'
            f'<span>Make your {year} top nine and post it</span>'
            '<svg class="lp-icon" aria-hidden="true"><use href="#i-arrow"/></svg></a>')


def tools_tile_html(today: Optional[date] = None) -> str:
    """A wide tile at the top of the homepage's free tools, in season."""
    if not promo_season(today):
        return ""
    today = today or _now().date()
    year = season_year(today)
    # In January the year being looked back on is over, so it isn't "new for the end of" it any more.
    kicker = f"New for the end of {year}" if today.year == year else f"Looking back on {year}"
    squares = "".join(f'<i class="lp-nine__sq lp-nine__sq--{kind}"></i>' for kind in KIND_ORDER)
    return ('<li class="lp-try-wide"><a class="lp-try lp-try--nine" href="/top-nine" data-home-tool="top-nine">'
            f'<span class="lp-nine" aria-hidden="true">{squares}</span>'
            f'<span class="lp-try__kicker">{kicker}</span>'
            f'<strong>Your {year} top nine</strong>'
            '<span>Pick the nine films, shows, games, albums or books you loved most '
            f'{year_words(year, today)}. You get a picture to post and a link friends can open to see how many '
            'they\'ve seen too.</span></a></li>')


def default_name(year: int) -> str:
    return f"My {year}"


def valid_token(token) -> bool:
    return isinstance(token, str) and TOKEN.match(token) is not None


def path_for(grid: models.TopNine) -> str:
    return f"/top-nine/{grid.token}"


def key_hash(key: str) -> str:
    return hashlib.sha256(f"top-nine:{key}".encode("utf-8")).hexdigest()


def key_matches(grid: models.TopNine, key) -> bool:
    return isinstance(key, str) and 20 <= len(key) <= 80 and hmac.compare_digest(grid.key_hash, key_hash(key))


def tidy(value) -> str:
    """Text as people typed it, minus control characters, lone surrogates, direction overrides and stacked marks."""
    out, marks = [], 0
    for char in unicodedata.normalize("NFC", str(value or "")):
        category = unicodedata.category(char)
        if category in ("Mn", "Me"):
            marks += 1
            if marks > MAX_MARKS:
                continue
        else:
            marks = 0
        if char in BIDI_CONTROLS or category == "Cs" or (category == "Cc" and not char.isspace()):
            continue
        out.append(char)
    return "".join(out)


def _clean_text(value, limit: int) -> str:
    return " ".join(tidy(value).split())[:limit]


# The public reviews' list of ad phrases, less one that is also a hit song's title.
AD_PHRASES = tuple(phrase for phrase in PROMOTIONAL_PHRASES if phrase != "work from home")


def _promotional(text: str) -> bool:
    folded = " ".join(text.casefold().split())
    return any(phrase in folded for phrase in AD_PHRASES)


# ---------------------------------------------------------------- the grid

def clean_tile(raw) -> Optional[dict]:
    """One square from what a browser sent, or None for an empty or unreadable one."""
    if not isinstance(raw, dict):
        return None
    title = _clean_text(raw.get("title"), MAX_TITLE)
    kind = raw.get("kind")
    if not title or kind not in title_pages.KINDS:
        return None
    year = raw.get("year")
    year = year if isinstance(year, int) and not isinstance(year, bool) and 1000 <= year <= 2200 else None
    slug = raw.get("slug")
    slug = slug if isinstance(slug, str) and SLUG.match(slug) else None
    image = raw.get("image")
    # Only poster hosts the image proxy already trusts, so a shared grid can't carry a tracking pixel.
    image = image if tier_list.image_allowed(image) and str(image).startswith("https://") else None
    creator = _clean_text(raw.get("creator"), MAX_CREATOR) or None
    return {"title": title, "kind": kind, "year": year, "slug": slug, "creator": creator, "image": image}


def clean_grid(name, theme, tiles, year: int) -> tuple[str, str, list, int]:
    """(name, theme, nine squares, filled count) from what a browser sent, or TopNineError."""
    name = _clean_text(name, MAX_NAME) or default_name(year)
    theme = theme if theme in THEMES else THEMES[0]
    source = tiles if isinstance(tiles, list) else []
    squares: list = []
    seen = set()
    for raw in source[:SLOTS]:
        tile = clean_tile(raw)
        if tile is not None:
            identity = (tile["title"].casefold(), tile["kind"], tile["year"] or 0)
            if identity in seen:
                tile = None
            else:
                seen.add(identity)
        squares.append(tile)
    squares += [None] * (SLOTS - len(squares))
    filled = sum(1 for tile in squares if tile)
    if filled < MIN_FILLED:
        raise TopNineError(f"Fill at least {MIN_FILLED} squares first.")
    texts = [name] + [part for tile in squares if tile for part in (tile["title"], tile["creator"] or "")]
    if not all(text_allowed(text) for text in texts if text):
        raise TopNineError("Links, email addresses and phone numbers can't go on a top nine. "
                           "Take them out of the name or the titles and try again.")
    # Anyone can make one without an account, and the pictures carry the site's name.
    if any(_promotional(text) for text in texts if text):
        raise TopNineError("That reads like an ad, so it can't go on a top nine. Change the name or the titles "
                           "and try again.")
    return name, theme, squares, filled


def tiles_of(grid: models.TopNine) -> list:
    try:
        data = json.loads(grid.tiles or "[]")
    except ValueError:
        data = []
    squares = []
    for raw in (data if isinstance(data, list) else [])[:SLOTS]:
        squares.append(raw if isinstance(raw, dict) and raw.get("title") and raw.get("kind") in title_pages.KINDS
                       else None)
    return squares + [None] * (SLOTS - len(squares))


def _dump(squares: list) -> str:
    return json.dumps(squares, ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------- storage

def by_token(db: Session, token, *, lock: bool = False) -> Optional[models.TopNine]:
    """A live grid, or None (unknown, malformed, expired, or its owner's account is closed)."""
    if not valid_token(token):
        return None
    query = db.query(models.TopNine).filter(models.TopNine.token == token)
    if lock and db.get_bind().dialect.name != "sqlite":
        query = query.with_for_update()
    grid = query.first()
    if grid is None or (grid.expires_at is not None and grid.expires_at <= _now()):
        return None
    if grid.owner_id is not None:
        active = db.query(models.User.is_active).filter(models.User.id == grid.owner_id).scalar()
        if not active:
            return None
    return grid


def _purge_expired(db: Session) -> None:
    expired = (db.query(models.TopNine.id)
               .filter(models.TopNine.expires_at.isnot(None), models.TopNine.expires_at <= _now())
               .limit(200).all())
    if expired:
        db.query(models.TopNine).filter(models.TopNine.id.in_([row.id for row in expired])) \
            .delete(synchronize_session=False)


def _new_token(db: Session) -> str:
    while True:
        token = secrets.token_urlsafe(12)
        if not db.query(models.TopNine.id).filter(models.TopNine.token == token).first():
            return token


def create(db: Session, user, visitor: Optional[str], payload: dict,
           today: Optional[date] = None) -> tuple[models.TopNine, str]:
    """A new grid and its edit key (the key is shown once, to the browser that made it)."""
    year = season_year(today)
    name, theme, squares, filled = clean_grid(payload.get("name"), payload.get("theme"), payload.get("tiles"), year)
    _purge_expired(db)
    now = _now()
    if user is not None:
        mine_count = db.query(models.TopNine.id).filter(models.TopNine.owner_id == user.id).count()
        if mine_count >= MEMBER_MAX:
            raise TopNineError(f"You have {MEMBER_MAX} top nines. Delete one to make another.", 409)
    else:
        live = (db.query(models.TopNine.id)
                .filter(models.TopNine.owner_id.is_(None), models.TopNine.visitor == visitor).count()
                if visitor else 0)
        if live >= GUEST_MAX_LIVE:
            raise TopNineError("This browser already has a few top nines. Create a free account to make more "
                               "and keep them for good.", 409)
    source = by_token(db, payload.get("source")) if payload.get("source") else None
    key = secrets.token_urlsafe(24)
    grid = models.TopNine(
        token=_new_token(db), owner_id=user.id if user is not None else None,
        visitor=None if user is not None else visitor, key_hash=key_hash(key), year=year, name=name, theme=theme,
        tiles=_dump(squares), tile_count=filled, source_id=source.id if source is not None else None,
        created_at=now, updated_at=now,
        expires_at=None if user is not None else now + timedelta(days=GUEST_DAYS),
    )
    db.add(grid)
    if source is not None:
        db.query(models.TopNine).filter(models.TopNine.id == source.id) \
            .update({models.TopNine.remixes: models.TopNine.remixes + 1}, synchronize_session=False)
    db.commit()
    db.refresh(grid)
    return grid, key


def can_edit(grid: models.TopNine, user, key) -> bool:
    if user is not None and grid.owner_id == user.id:
        return True
    return grid.owner_id is None and key_matches(grid, key)


def update(db: Session, grid: models.TopNine, user, payload: dict) -> models.TopNine:
    if not can_edit(grid, user, payload.get("key")):
        raise TopNineError("Only the person who made this top nine can change it.", 403)
    name, theme, squares, filled = clean_grid(payload.get("name"), payload.get("theme"), payload.get("tiles"),
                                              grid.year)
    grid.name, grid.theme, grid.tiles, grid.tile_count = name, theme, _dump(squares), filled
    grid.updated_at = _now()
    db.commit()
    db.refresh(grid)
    return grid


def delete(db: Session, grid: models.TopNine, user, key) -> None:
    if not can_edit(grid, user, key):
        raise TopNineError("Only the person who made this top nine can delete it.", 403)
    db.delete(grid)
    db.commit()


def claim(db: Session, user, links) -> list[str]:
    """Move grids this browser made before signing up into the member's account. Returns their tokens."""
    claimed = []
    for link in (links if isinstance(links, list) else [])[:CLAIM_MAX]:
        if not isinstance(link, dict):
            continue
        grid = by_token(db, link.get("token"), lock=True)
        if grid is None or grid.owner_id is not None or not key_matches(grid, link.get("key")):
            continue
        if db.query(models.TopNine.id).filter(models.TopNine.owner_id == user.id).count() >= MEMBER_MAX:
            break
        grid.owner_id = user.id
        grid.visitor = None
        grid.expires_at = None
        db.flush()
        claimed.append(grid.token)
    if claimed:
        db.commit()
    return claimed


def count_view(db: Session, grid: models.TopNine) -> None:
    db.query(models.TopNine).filter(models.TopNine.id == grid.id) \
        .update({models.TopNine.views: models.TopNine.views + 1}, synchronize_session=False)
    db.commit()


def count_answer(db: Session, grid: models.TopNine) -> None:
    db.query(models.TopNine).filter(models.TopNine.id == grid.id) \
        .update({models.TopNine.answers: models.TopNine.answers + 1}, synchronize_session=False)
    db.commit()


def credit(db: Session, grid: models.TopNine) -> Optional[tuple[str, str]]:
    """(name, profile link) when the maker already shows a public profile; otherwise None."""
    if grid.owner_id is None:
        return None
    from .public_profiles import profile_path
    row = (db.query(models.User, models.PublicProfile)
           .outerjoin(models.PublicProfile, models.PublicProfile.user_id == models.User.id)
           .filter(models.User.id == grid.owner_id, models.User.is_active == True).first())  # noqa: E712
    if row is None:
        return None
    user, profile = row
    if profile is not None and profile.enabled:
        return user.username, profile_path(user)
    return None


def _linked(db: Session, squares: list) -> list:
    """The squares with a title page link where one exists (a title members track)."""
    from . import title_search
    pages = {(entry["kind"], entry["slug"]) for entry in title_search.index(db)}
    out = []
    for tile in squares:
        if not tile:
            out.append(None)
            continue
        slug = tile.get("slug") or title_pages.title_slug(tile["title"], tile.get("year"))
        link = f"/titles/{tile['kind']}/{slug}" if (tile["kind"], slug) in pages else None
        out.append({**tile, "url": link, "label": KIND_SHORT[tile["kind"]]})
    return out


def public_state(db: Session, grid: models.TopNine) -> dict:
    """What anyone with the link may read: the squares, the maker's public name and the counts."""
    named = credit(db, grid)
    return {
        "token": grid.token, "path": path_for(grid), "year": grid.year, "name": grid.name, "theme": grid.theme,
        "tiles": _linked(db, tiles_of(grid)), "count": grid.tile_count,
        "by": named[0] if named else None, "by_url": named[1] if named else None,
        "member": grid.owner_id is not None,
        "views": grid.views or 0, "remixes": grid.remixes or 0, "answers": grid.answers or 0,
        "version": fingerprint(grid),
    }


def owner_reply(grid: models.TopNine, key: Optional[str] = None) -> dict:
    reply = {"token": grid.token, "path": path_for(grid), "url": f"https://omnitrackr.xyz{path_for(grid)}",
             "count": grid.tile_count, "member": grid.owner_id is not None, "year": grid.year,
             "version": fingerprint(grid),
             "expires_at": grid.expires_at.isoformat() + "Z" if grid.expires_at else None}
    if key:
        reply["key"] = key
    return reply


def mine(db: Session, user) -> list[dict]:
    rows = (db.query(models.TopNine).filter(models.TopNine.owner_id == user.id)
            .order_by(models.TopNine.updated_at.desc(), models.TopNine.id.desc()).limit(MINE_SHOWN).all())
    out = []
    for row in rows:
        squares = tiles_of(row)
        out.append({"token": row.token, "path": path_for(row), "name": row.name, "year": row.year,
                    "count": row.tile_count, "views": row.views or 0, "remixes": row.remixes or 0,
                    "answers": row.answers or 0, "version": fingerprint(row),
                    "images": [tile["image"] for tile in squares if tile and tile.get("image")][:3],
                    "updated_at": row.updated_at.isoformat() + "Z" if row.updated_at else None})
    return out


def fingerprint(grid: models.TopNine) -> str:
    return hashlib.sha256(json.dumps([grid.id, grid.name, grid.theme, grid.tiles, grid.year]).encode("utf-8")) \
        .hexdigest()[:16]


def byline(db: Session, grid: models.TopNine) -> Optional[str]:
    named = credit(db, grid)
    return named[0] if named else None


# ---------------------------------------------------------------- keeping the nine

def keep(db: Session, user, grid: models.TopNine) -> dict:
    """Put the grid's titles into the member's library, already finished. Titles they have stay as they are.

    Commits. Only the grid's owner may call it (the router checks).
    """
    from . import browse, pick
    from .progress import lock_progress_owner
    lock_progress_owner(db, user.id)
    added, existing = [], []
    for tile in tiles_of(grid):
        if not tile:
            continue
        entry = {"kind": tile["kind"], "title": tile["title"], "year": tile.get("year"),
                 "creator": tile.get("creator"), "extra": {}}
        if tile["kind"] in browse.TITLE_KIND_TO_KIND:
            state, record = browse.add_to_library(db, user, browse.TITLE_KIND_TO_KIND[tile["kind"]], entry,
                                                  tile.get("image"), finished=True)
        else:
            state, record = pick.add_to_library(db, user, entry, tile.get("image"), finished=True)
        (added if state == "created" else existing).append({"title": record.title, "kind": tile["kind"]})
    db.commit()
    return {"added": added, "existing": existing}


# ---------------------------------------------------------------- what to put in it

_catalog_lock = threading.Lock()
_catalog: dict = {"members": None, "pool": None, "entries": None}


def _entry(kind: str, title: str, year, creator, weight: int, image=None) -> Optional[dict]:
    if kind not in title_pages.KINDS or not isinstance(title, str) or not title.strip():
        return None
    year = year if isinstance(year, int) and not isinstance(year, bool) and 1000 <= year <= 2200 else None
    base = title_pages.slugify(title)
    if base == "title" and "title" not in title.lower():
        return None
    return {"kind": kind, "label": title_pages.KINDS[kind][3], "title": title.strip(), "year": year,
            "slug": f"{base}-{year}" if year else base, "creator": creator or None, "image": image,
            "members": weight, "words": base.split("-"), "base": base}


def _curated() -> list[dict]:
    """Every title the editors' writing names: the year's big ones, the Essential 100, Pick for me's pool
    (trails, editions, collections, guides) and the manga, podcast and audiobook shelves."""
    found = []
    from . import essentials, pick, year_catchup
    for year in year_catchup.years():
        for item in year_catchup.entries(year):
            found.append(_entry(item["kind"], item["title"], item["year"], item["creator"], 6))
    for item in essentials.all_items():
        found.append(_entry(item["kind"], item["title"], item.get("year"), item.get("creator"), 3))
    for item in pick.pool():
        found.append(_entry(item["kind"], item["title"], item.get("year"), item.get("creator"), 3))
    try:
        from . import browse_catalog
        for shelf_kind, title_kind in (("manga", "manga"), ("podcasts", "podcast"), ("audiobooks", "audiobook")):
            for item in browse_catalog.entries(shelf_kind):
                found.append(_entry(title_kind, item["title"], item.get("year"), item.get("creator"), 2))
    except Exception:
        pass
    return [entry for entry in found if entry]


def catalog(db: Session) -> list[dict]:
    """Members' titles first (they have covers and title pages), then the editors' titles nobody tracks yet."""
    from . import pick, title_search
    members = title_search.index(db)
    pool = pick.pool()
    with _catalog_lock:
        if _catalog["entries"] is not None and _catalog["members"] is members and _catalog["pool"] is pool:
            return _catalog["entries"]
    entries = list(members)
    have = {(entry["kind"], entry["base"]) for entry in members}
    for entry in _curated():
        identity = (entry["kind"], entry["base"])
        if identity not in have:
            have.add(identity)
            entries.append(entry)
    with _catalog_lock:
        _catalog.update(members=members, pool=pool, entries=entries)
    return entries


def clear_cache() -> None:
    with _catalog_lock:
        _catalog.update(members=None, pool=None, entries=None)


def _with_covers(db: Session, rows: list[dict]) -> list[dict]:
    """Search answers with a cover from the site's cache where the entry has none. Never fetches."""
    from . import explore_art, image_sizes
    missing = [(row["kind"], row["title"], row["year"]) for row in rows if not row.get("image")]
    covers = {}
    if missing:
        try:
            covers = explore_art.cached_posters(db, missing)
        except Exception:
            db.rollback()
    out = []
    for row in rows:
        image = row.get("image") or covers.get((row["kind"], row["title"], row["year"]))
        image = image if tier_list.image_allowed(image) and str(image).startswith("https://") else None
        out.append({"kind": row["kind"], "label": KIND_SHORT[row["kind"]], "title": row["title"],
                    "year": row["year"], "creator": row.get("creator"), "slug": row["slug"], "image": image,
                    "thumb": image_sizes.sized(image, 200) if image else None})
    return out


def ranked(entries: list[dict], text: str, kind: Optional[str] = None) -> list[dict]:
    """The homepage search's ranking (app/title_search.py) over the wider catalog. Its two-letter
    lookup is cached for the member index alone, so this walks the list (a few thousand entries)."""
    from . import title_search
    query = title_pages.slugify((text or "")[:title_search.QUERY_MAX])
    if query == "title" and "title" not in (text or "").lower():
        return []
    if len(query.replace("-", "")) < 2:
        return []
    tokens = [token for token in query.split("-") if token]
    scored = []
    for entry in entries:
        if kind is not None and entry["kind"] != kind:
            continue
        rank = title_search._rank(entry, query, tokens)
        if rank is not None:
            scored.append((rank, -entry["members"], KIND_ORDER.index(entry["kind"]), len(entry["title"]),
                           entry["title"].casefold(), entry))
    scored.sort(key=lambda row: row[:5])
    return [row[-1] for row in scored]


def search(db: Session, text: str, kind: Optional[str] = None, limit: int = SEARCH_LIMIT) -> list[dict]:
    kind = kind if kind in title_pages.KINDS else None
    return _with_covers(db, ranked(catalog(db), text, kind)[:limit])


def big_ones(db: Session, year: int, kind: Optional[str] = None, today: Optional[date] = None) -> list[dict]:
    """The year's big releases (app/year_catchup_data.py), biggest first, with cached covers."""
    from . import year_catchup
    if not year_catchup.has_year(year):
        return []
    rows = year_catchup.shown(year, today) if year == (today or _now().date()).year else year_catchup.entries(year)
    rows = [row for row in rows if kind is None or row["kind"] == kind]
    rows.sort(key=lambda row: row["feature"])
    return _with_covers(db, [{**row, "image": None} for row in rows[:SUGGEST_LIMIT]])


def member_options(db: Session, user, year: int) -> dict:
    """The member's own titles for the picker: the year's finishes (favourites, then by score), then
    titles they rated highly at any time. Their own library, so private shelves count too."""
    from . import check_in, rankings, year_in_review
    categories = list(check_in.CATEGORIES)
    _, finished = year_in_review._finishes(db, user.id, year, categories)
    wanted: list[tuple[str, int]] = []
    for row in sorted(finished.values(), key=lambda r: (not r["favorite"], -(r["rating"] or 0), r["finished_at"])):
        if row.get("item_id") and (row["category"], row["item_id"]) not in wanted:
            wanted.append((row["category"], row["item_id"]))
    this_year = set(wanted)
    loved = []
    for category in categories:
        model = check_in.CATEGORIES[category][0]
        rating = getattr(model, "rating", None)
        if rating is None:
            continue
        for item_id, score in (db.query(model.id, rating)
                               .filter(model.user_id == user.id, rating >= LOVED_RATING, model.title.isnot(None))
                               .order_by(rating.desc(), model.id.desc()).limit(12)):
            loved.append((float(score or 0), category, item_id))
    for _score, category, item_id in sorted(loved, key=lambda entry: -entry[0]):
        if (category, item_id) not in wanted:
            wanted.append((category, item_id))
    wanted = wanted[:MEMBER_OPTIONS_MAX]
    by_category: dict[str, list[int]] = {}
    for category, item_id in wanted:
        by_category.setdefault(category, []).append(item_id)
    rows = {}
    for category, ids in by_category.items():
        model = check_in.CATEGORIES[category][0]
        for row in db.query(model).filter(model.user_id == user.id, model.id.in_(ids)):
            rows[(category, row.id)] = row
    groups = {"year": [], "loved": []}
    for key in wanted:
        row = rows.get(key)
        if row is None or not (row.title or "").strip():
            continue
        card = rankings.card(key[0], row)
        kind = title_pages.LIBRARY_TO_KIND[key[0]]
        groups["year" if key in this_year else "loved"].append(
            {"kind": kind, "title": card["title"], "year": card["year"], "creator": card["creator"],
             "image": card["image"], "slug": title_pages.title_slug(card["title"], card["year"])})
    return {"year": _with_covers(db, groups["year"]), "loved": _with_covers(db, groups["loved"])}
