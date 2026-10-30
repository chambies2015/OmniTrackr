"""The start page (/start): a new member's first few minutes, aimed at five saved titles.

Right after a new account's first log-in, the dashboard sends the member here once
(see COOKIE). The page offers three ways in, all of which already exist elsewhere
on the site and are only gathered here:

* Quick add: a deck of popular titles in the formats the member picks, answered
  Seen it, Want to or Skip. Popular means saved by two or more members (from the
  homepage search index), topped up with a short list of widely known titles per
  format so a thin catalog (manga, podcasts, audiobooks) still has cards.
* Import: the Import Studio on the dashboard (/?start=import).
* Search: the homepage title search (/api/titles/search).

The taste quiz is linked too. When the library reaches five titles the page hands
over to the first-week steps the dashboard launchpad already tracks (a rating, a
friend, the weekly email).

Only public details are copied into the library (title, year, creator, artwork),
never anyone's rating or notes, and a title the member already has is left as it is.
Each step is counted once per member (MemberStart) for the Site stats page.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import funnel, models, title_pages
from .for_you import LIBRARY, STARTER_GOAL

GOAL = STARTER_GOAL
# Accounts made from this day on are sent to /start after their first log-in.
# Older accounts are never redirected (they can still open the page from the dashboard).
LAUNCH = datetime(2026, 10, 30)
COOKIE = "omnitrackr_start"
COOKIE_MAX_AGE = 2 * 24 * 3600
DECK_SIZE = 40
POPULAR_MIN_MEMBERS = 2

# Format chips, in the order the page shows them: kind -> (chip label, card label).
FORMATS = {
    "movie": ("Movies", "Movie"),
    "tv": ("TV shows", "TV show"),
    "anime": ("Anime", "Anime"),
    "game": ("Games", "Game"),
    "book": ("Books", "Book"),
    "album": ("Music", "Album"),
    "manga": ("Manga", "Manga"),
    "podcast": ("Podcasts", "Podcast"),
    "audiobook": ("Audiobooks", "Audiobook"),
}
DEFAULT_KINDS = ("movie", "tv", "anime", "game")

# Widely known titles per format: (title, year, creator). Games carry no creator;
# audiobooks add a narrator as a fourth value. Years are first release.
WELL_KNOWN = {
    "movie": (
        ("Interstellar", 2014, "Christopher Nolan"), ("The Dark Knight", 2008, "Christopher Nolan"),
        ("Inception", 2010, "Christopher Nolan"), ("Oppenheimer", 2023, "Christopher Nolan"),
        ("Barbie", 2023, "Greta Gerwig"), ("Dune: Part Two", 2024, "Denis Villeneuve"),
        ("Spider-Man: Into the Spider-Verse", 2018, "Bob Persichetti, Peter Ramsey, Rodney Rothman"),
        ("Avengers: Endgame", 2019, "Anthony Russo, Joe Russo"), ("Parasite", 2019, "Bong Joon-ho"),
        ("Everything Everywhere All at Once", 2022, "Daniel Kwan, Daniel Scheinert"),
        ("Top Gun: Maverick", 2022, "Joseph Kosinski"), ("Pulp Fiction", 1994, "Quentin Tarantino"),
        ("The Shawshank Redemption", 1994, "Frank Darabont"), ("The Matrix", 1999, "Lana Wachowski, Lilly Wachowski"),
        ("Get Out", 2017, "Jordan Peele"), ("Titanic", 1997, "James Cameron"), ("Toy Story", 1995, "John Lasseter"),
        ("The Lord of the Rings: The Fellowship of the Ring", 2001, "Peter Jackson"),
    ),
    "tv": (
        ("Breaking Bad", 2008, None), ("Stranger Things", 2016, None), ("Game of Thrones", 2011, None),
        ("The Office", 2005, None), ("Friends", 1994, None), ("The Last of Us", 2023, None),
        ("Succession", 2018, None), ("The Bear", 2022, None), ("Severance", 2022, None), ("Arcane", 2021, None),
        ("The Boys", 2019, None), ("Wednesday", 2022, None), ("Squid Game", 2021, None),
        ("The Mandalorian", 2019, None), ("Better Call Saul", 2015, None), ("Ted Lasso", 2020, None),
        ("Shōgun", 2024, None), ("House of the Dragon", 2022, None),
    ),
    "anime": (
        ("Attack on Titan", 2013, None), ("Death Note", 2006, None), ("One Piece", 1999, None),
        ("Demon Slayer: Kimetsu no Yaiba", 2019, None), ("Jujutsu Kaisen", 2020, None),
        ("Fullmetal Alchemist: Brotherhood", 2009, None), ("My Hero Academia", 2016, None), ("Naruto", 2002, None),
        ("Spy x Family", 2022, None), ("Frieren: Beyond Journey's End", 2023, None), ("Cowboy Bebop", 1998, None),
        ("Chainsaw Man", 2022, None), ("Hunter x Hunter", 2011, None), ("Spirited Away", 2001, None),
        ("Your Name", 2016, None), ("One-Punch Man", 2015, None), ("Neon Genesis Evangelion", 1995, None),
        ("Solo Leveling", 2024, None),
    ),
    "game": (
        ("Minecraft", 2011, None), ("The Legend of Zelda: Breath of the Wild", 2017, None), ("Elden Ring", 2022, None),
        ("Red Dead Redemption 2", 2018, None), ("The Witcher 3: Wild Hunt", 2015, None),
        ("Grand Theft Auto V", 2013, None), ("Baldur's Gate 3", 2023, None), ("Stardew Valley", 2016, None),
        ("Hades", 2020, None), ("Hollow Knight", 2017, None), ("Fortnite", 2017, None), ("Among Us", 2018, None),
        ("The Last of Us", 2013, None), ("God of War", 2018, None), ("Super Mario Odyssey", 2017, None),
        ("Animal Crossing: New Horizons", 2020, None), ("Portal 2", 2011, None), ("Celeste", 2018, None),
    ),
    "book": (
        ("Harry Potter and the Sorcerer's Stone", 1997, "J.K. Rowling"), ("The Hobbit", 1937, "J.R.R. Tolkien"),
        ("1984", 1949, "George Orwell"), ("To Kill a Mockingbird", 1960, "Harper Lee"),
        ("Pride and Prejudice", 1813, "Jane Austen"), ("The Great Gatsby", 1925, "F. Scott Fitzgerald"),
        ("Dune", 1965, "Frank Herbert"), ("Project Hail Mary", 2021, "Andy Weir"),
        ("The Hunger Games", 2008, "Suzanne Collins"), ("Fourth Wing", 2023, "Rebecca Yarros"),
        ("It Ends with Us", 2016, "Colleen Hoover"), ("The Midnight Library", 2020, "Matt Haig"),
        ("Where the Crawdads Sing", 2018, "Delia Owens"), ("Atomic Habits", 2018, "James Clear"),
        ("The Name of the Wind", 2007, "Patrick Rothfuss"), ("The Martian", 2011, "Andy Weir"),
        ("A Court of Thorns and Roses", 2015, "Sarah J. Maas"), ("Lessons in Chemistry", 2022, "Bonnie Garmus"),
    ),
    "album": (
        ("Rumours", 1977, "Fleetwood Mac"), ("Thriller", 1982, "Michael Jackson"), ("Abbey Road", 1969, "The Beatles"),
        ("The Dark Side of the Moon", 1973, "Pink Floyd"), ("Nevermind", 1991, "Nirvana"), ("21", 2011, "Adele"),
        ("Random Access Memories", 2013, "Daft Punk"), ("To Pimp a Butterfly", 2015, "Kendrick Lamar"),
        ("Blonde", 2016, "Frank Ocean"), ("1989", 2014, "Taylor Swift"), ("Lemonade", 2016, "Beyoncé"),
        ("good kid, m.A.A.d city", 2012, "Kendrick Lamar"), ("Currents", 2015, "Tame Impala"), ("SOS", 2022, "SZA"),
        ("Future Nostalgia", 2020, "Dua Lipa"), ("OK Computer", 1997, "Radiohead"), ("Back in Black", 1980, "AC/DC"),
        ("Short n' Sweet", 2024, "Sabrina Carpenter"),
    ),
    "manga": (
        ("One Piece", 1997, "Eiichiro Oda"), ("Naruto", 1999, "Masashi Kishimoto"), ("Attack on Titan", 2009, "Hajime Isayama"),
        ("Berserk", 1989, "Kentaro Miura"), ("Chainsaw Man", 2018, "Tatsuki Fujimoto"), ("Jujutsu Kaisen", 2018, "Gege Akutami"),
        ("Demon Slayer: Kimetsu no Yaiba", 2016, "Koyoharu Gotouge"), ("Death Note", 2003, "Tsugumi Ohba, Takeshi Obata"),
        ("Fullmetal Alchemist", 2001, "Hiromu Arakawa"), ("Vagabond", 1998, "Takehiko Inoue"),
        ("Dragon Ball", 1984, "Akira Toriyama"), ("Spy x Family", 2019, "Tatsuya Endo"),
        ("My Hero Academia", 2014, "Kohei Horikoshi"), ("Vinland Saga", 2005, "Makoto Yukimura"),
        ("Frieren: Beyond Journey's End", 2020, "Kanehito Yamada, Tsukasa Abe"), ("Bleach", 2001, "Tite Kubo"),
        ("Tokyo Ghoul", 2011, "Sui Ishida"), ("Monster", 1994, "Naoki Urasawa"),
    ),
    "podcast": (
        ("The Joe Rogan Experience", 2009, "Joe Rogan"), ("Serial", 2014, "Sarah Koenig"),
        ("This American Life", 1995, "Ira Glass"), ("The Daily", 2017, "Michael Barbaro"),
        ("Crime Junkie", 2017, "Ashley Flowers"), ("Dan Carlin's Hardcore History", 2006, "Dan Carlin"),
        ("SmartLess", 2020, "Jason Bateman, Sean Hayes, Will Arnett"), ("Call Her Daddy", 2018, "Alex Cooper"),
        ("Stuff You Should Know", 2008, "Josh Clark, Chuck Bryant"), ("Huberman Lab", 2021, "Andrew Huberman"),
        ("Armchair Expert", 2018, "Dax Shepard"), ("My Favorite Murder", 2016, "Karen Kilgariff, Georgia Hardstark"),
        ("Freakonomics Radio", 2010, "Stephen J. Dubner"), ("Conan O'Brien Needs a Friend", 2018, "Conan O'Brien"),
        ("99% Invisible", 2010, "Roman Mars"), ("Hidden Brain", 2015, "Shankar Vedantam"),
    ),
    "audiobook": (
        ("Project Hail Mary", 2021, "Andy Weir", "Ray Porter"), ("Atomic Habits", 2018, "James Clear", "James Clear"),
        ("Born a Crime", 2016, "Trevor Noah", "Trevor Noah"), ("Becoming", 2018, "Michelle Obama", "Michelle Obama"),
        ("Greenlights", 2020, "Matthew McConaughey", "Matthew McConaughey"), ("The Martian", 2013, "Andy Weir", "R.C. Bray"),
        ("Harry Potter and the Sorcerer's Stone", 1999, "J.K. Rowling", "Jim Dale"),
        ("The Hobbit", 2020, "J.R.R. Tolkien", "Andy Serkis"), ("Sapiens", 2015, "Yuval Noah Harari", "Derek Perkins"),
        ("Educated", 2018, "Tara Westover", "Julia Whelan"), ("Dungeon Crawler Carl", 2020, "Matt Dinniman", "Jeff Hays"),
        ("Shoe Dog", 2016, "Phil Knight", "Norbert Leo Butz"), ("The Way of Kings", 2010, "Brandon Sanderson", "Michael Kramer, Kate Reading"),
        ("Red Rising", 2014, "Pierce Brown", "Tim Gerard Reynolds"), ("I'm Glad My Mom Died", 2022, "Jennette McCurdy", "Jennette McCurdy"),
        ("Fourth Wing", 2023, "Rebecca Yarros", "Rebecca Soler, Teddy Hamilton"),
    ),
}

# Steps counted on Site stats: MemberStart column -> funnel event.
STEPS = {
    "opened": ("opened_at", "start_opened"),
    "quick_add": ("quick_add_at", "start_quick_add"),
    "search": ("search_at", "start_search"),
    "import": ("import_at", "start_import"),
    "quiz": ("quiz_at", "start_quiz"),
    "first_saved": ("first_saved_at", "start_first_saved"),
    "reached_five": ("reached_five_at", "start_reached_five"),
    "next_step": ("next_step_at", "start_next_step"),
    "skipped": ("skipped_at", "start_skipped"),
}
# Steps the page reports itself (saving and opening are recorded by the server).
CLIENT_STEPS = ("import", "quiz", "next_step", "skipped")


def _well_known_entry(kind: str, row: tuple) -> dict:
    title, year, creator = row[0], row[1], row[2]
    entry = {"kind": kind, "title": title, "year": year, "creator": creator,
             "slug": title_pages.title_slug(title, year)}
    if kind == "audiobook" and len(row) > 3:
        entry["narrator"] = row[3]
    return entry


_WELL_KNOWN_BY_ID = {f"{kind}/{entry['slug']}": entry
                     for kind, rows in WELL_KNOWN.items() for entry in (_well_known_entry(kind, row) for row in rows)}


def well_known(kind: str, slug: str) -> Optional[dict]:
    return _WELL_KNOWN_BY_ID.get(f"{kind}/{slug}")


# ---------------------------------------------------------------- who sees it

def wants_start(user) -> bool:
    """True at a new account's first log-in (call before login_count goes up)."""
    created = getattr(user, "created_at", None)
    return not user.login_count and created is not None and created >= LAUNCH


def set_cookie(response, secure: bool) -> None:
    """Tell the next plain dashboard load to open /start instead (see main.read_root)."""
    response.set_cookie(key=COOKIE, value="1", max_age=COOKIE_MAX_AGE, httponly=True,
                        secure=secure, samesite="lax", path="/")


def clear_cookie(response, secure: bool) -> None:
    response.delete_cookie(key=COOKIE, path="/", samesite="lax", secure=secure, httponly=True)


# ---------------------------------------------------------------- library

def library_total(db: Session, user_id: int) -> int:
    total = 0
    for model, _ in LIBRARY.values():
        total += int(db.query(func.count(model.id)).filter(model.user_id == user_id).scalar() or 0)
    return total


def recent_titles(db: Session, user_id: int, limit: int = GOAL) -> list[dict]:
    """The member's newest titles across formats, for the shelf at the top of the page."""
    rows = []
    for kind, (model, _, category, label, _) in title_pages.KINDS.items():
        image = getattr(model, title_pages.IMAGE_FIELD[kind])
        done = getattr(model, title_pages.COMPLETE_FIELD[kind])
        for item_id, title, art, finished in (db.query(model.id, model.title, image, done)
                                              .filter(model.user_id == user_id)
                                              .order_by(model.id.desc()).limit(limit).all()):
            rows.append({"kind": kind, "category": category, "label": label, "item_id": item_id,
                         "title": title or "", "image": title_pages._safe_image(art), "seen": bool(finished),
                         "_order": item_id})
    # Ids grow per table, not across tables; newest per table first is close enough for five slots.
    rows.sort(key=lambda row: -row.pop("_order"))
    return rows[:limit]


def owned_slugs(db: Session, user_id: int) -> dict[str, set[str]]:
    """{kind: {title slug}} for the member's library, so the deck skips what they already have."""
    owned = {}
    for kind, (model, *_rest) in title_pages.KINDS.items():
        owned[kind] = {title_pages.slugify(title) for title, in db.query(model.title).filter(model.user_id == user_id).all() if title}
    return owned


# ---------------------------------------------------------------- the deck

def _card(kind: str, title: str, year, slug: str, *, creator=None, image=None, members: int = 0) -> dict:
    return {"id": f"{kind}/{slug}", "kind": kind, "slug": slug, "label": FORMATS[kind][1], "title": title,
            "year": year, "creator": creator or None, "image": image, "members": members}


def deck(index: list[dict], owned: dict[str, set[str]], kinds: Iterable[str], skip: Iterable[str] = (),
         limit: int = DECK_SIZE) -> list[dict]:
    """Cards for the chosen formats, most saved first, mixed so no format runs long."""
    kinds = [kind for kind in dict.fromkeys(kinds) if kind in FORMATS] or list(DEFAULT_KINDS)
    skipped = set(skip)
    art: dict[tuple[str, str], dict] = {}
    popular: dict[str, list[dict]] = {kind: [] for kind in kinds}
    for entry in index:
        if entry["kind"] not in popular:
            continue
        key = (entry["kind"], entry["base"])
        if entry.get("image") and (key not in art or entry["members"] > art[key]["members"]):
            art[key] = entry
        if entry["members"] >= POPULAR_MIN_MEMBERS:
            popular[entry["kind"]].append(entry)
    per_kind: dict[str, list[dict]] = {}
    for kind in kinds:
        seen = set(owned.get(kind, set()))
        cards = []
        for entry in sorted(popular[kind], key=lambda e: (-e["members"], e["title"].casefold())):
            if entry["base"] in seen or f"{kind}/{entry['slug']}" in skipped:
                continue
            seen.add(entry["base"])
            cards.append(_card(kind, entry["title"], entry["year"], entry["slug"], image=entry.get("image"),
                               members=entry["members"]))
        for row in WELL_KNOWN.get(kind, ()):
            known = _well_known_entry(kind, row)
            base = title_pages.slugify(known["title"])
            if base in seen or f"{kind}/{known['slug']}" in skipped:
                continue
            seen.add(base)
            match = art.get((kind, base))
            cards.append(_card(kind, known["title"], known["year"], known["slug"], creator=known["creator"],
                               image=match.get("image") if match else None))
        per_kind[kind] = cards
    mixed = []
    while len(mixed) < limit and any(per_kind.values()):
        for kind in kinds:
            if per_kind[kind] and len(mixed) < limit:
                mixed.append(per_kind[kind].pop(0))
    return mixed


# ---------------------------------------------------------------- saving

def _creator_fields(kind: str, creator, narrator=None) -> dict:
    field_name = title_pages.KINDS[kind][4]
    fields = {}
    if field_name:
        fields[field_name] = creator or ""
    if kind == "audiobook" and narrator:
        fields["narrator"] = narrator
    return fields


def add_known(db: Session, user, kind: str, entry: dict, image: Optional[str] = None) -> tuple[str, object]:
    """Add a well-known title nobody tracks yet, as pick.add_to_library does. Does not commit."""
    model = title_pages.KINDS[kind][0]
    existing = (db.query(model).filter(model.user_id == user.id,
                                       func.lower(func.trim(model.title)) == title_pages.normalize(entry["title"])).first())
    if existing is not None:
        return "existing", existing
    fields = {"user_id": user.id, "title": entry["title"], **_creator_fields(kind, entry.get("creator"), entry.get("narrator"))}
    if kind == "game":
        fields["release_date"] = datetime(entry["year"], 1, 1) if entry.get("year") else None
    else:
        fields["year"] = entry.get("year")
    safe = title_pages._safe_image(image)
    if safe:
        fields[title_pages.IMAGE_FIELD[kind]] = safe
    record = model(**fields)
    db.add(record)
    db.flush()
    return "created", record


def resolve(db: Session, kind: str, slug: str):
    """("group", TitleGroup) for a title members track, ("known", entry) for one of WELL_KNOWN,
    or None. Nothing else can be saved through the page."""
    if kind not in FORMATS:
        return None
    group = title_pages.find(db, kind, slug)
    if group is not None:
        return "group", group
    entry = well_known(kind, slug)
    if entry is not None:
        return "known", entry
    return None


def mark_seen(record, kind: str) -> None:
    """A title saved with "Seen it" counts as finished. Only ever called on a record just created."""
    setattr(record, title_pages.COMPLETE_FIELD[kind], True)


# ---------------------------------------------------------------- steps

def row_for(db: Session, user_id: int, create: bool = True) -> Optional[models.MemberStart]:
    row = db.query(models.MemberStart).filter(models.MemberStart.user_id == user_id).first()
    if row is None and create:
        row = models.MemberStart(user_id=user_id, opened_at=datetime.utcnow())
        db.add(row)
        db.flush()
        funnel.record(STEPS["opened"][1])
    return row


def mark(db: Session, user_id: int, step: str, request=None) -> bool:
    """Record a step the first time it happens for this member. Does not commit."""
    column, event = STEPS[step]
    row = row_for(db, user_id)
    if getattr(row, column) is not None:
        return False
    setattr(row, column, datetime.utcnow())
    funnel.record(event, request)
    return True
