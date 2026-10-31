"""People and studio pages: everything members track by one director, actor, author or studio.

A person or company is identified by the slug of their name, e.g. /people/christopher-nolan
or /studios/madhouse. Their titles come from two places:

* The creator field members fill in themselves (a movie's director, a book's author,
  a manga's author, a podcast's host, an album's artist).
* Credits in a title's cached public facts (title_metadata): cast, writers, studios,
  developers, publishers and networks. These are copied into title_credits whenever
  facts are stored, so a page never re-reads every cached blob.

Each title then gets the same member numbers its title page shows (title_pages.summarize):
who tracks it, the average rating once enough members rated it, and public reviews.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import models, title_pages
from .review_quality import AD_MIN_REVIEW_WORDS, word_count

PERSON, STUDIO = "person", "studio"
PREFIX = {PERSON: "/people", STUDIO: "/studios"}

# Fact label on a title page -> (entity, role). Labels not listed (country, platforms...) are not credits.
FACT_ROLES = {
    "movie": {"Director": (PERSON, "Director"), "Screenplay": (PERSON, "Writer"), "Starring": (PERSON, "Cast"),
              "Studio": (STUDIO, "Studio")},
    "tv": {"Created by": (PERSON, "Creator"), "Starring": (PERSON, "Cast"),
           "Original network": (STUDIO, "Network"), "Network": (STUDIO, "Network")},
    "anime": {"Director": (PERSON, "Director"), "Studio": (STUDIO, "Studio")},
    "game": {"Developer": (STUDIO, "Developer"), "Publisher": (STUDIO, "Publisher")},
    "book": {"Author": (PERSON, "Author")},
    "manga": {"Author": (PERSON, "Mangaka")},
    "podcast": {"Presented by": (PERSON, "Host"), "Host": (PERSON, "Host")},
    "album": {"Artist": (PERSON, "Artist")},
}
# The creator field members type in, and the role it stands for.
LIBRARY_ROLES = {"movie": "Director", "book": "Author", "manga": "Mangaka", "podcast": "Host", "album": "Artist"}
# Band names ("Earth, Wind & Fire") keep their commas; other credits are comma-separated lists.
UNSPLIT_ROLES = {"Artist"}
ROLE_ORDER = ("Director", "Creator", "Writer", "Cast", "Author", "Mangaka", "Host", "Artist",
              "Studio", "Developer", "Publisher", "Network")
ROLE_PLURALS = {"Director": "Directors", "Creator": "TV creators", "Writer": "Screenwriters", "Cast": "Actors",
                "Author": "Authors", "Mangaka": "Mangaka", "Host": "Podcast hosts", "Artist": "Musicians and bands",
                "Studio": "Studios", "Developer": "Game developers", "Publisher": "Game publishers",
                "Network": "TV networks"}
# How a work is described next to the role: "Directed", "Starred in"...
ROLE_VERBS = {"Director": "directed", "Creator": "created", "Writer": "wrote", "Cast": "appeared in",
              "Author": "wrote", "Mangaka": "wrote", "Host": "hosts", "Artist": "recorded",
              "Studio": "made", "Developer": "developed", "Publisher": "published", "Network": "aired"}
COMPANY_SUFFIX = re.compile(r"^(inc|ltd|llc|llp|co|corp|plc|gmbh|s\.?a|l\.?p|k\.?k)\.?$", re.IGNORECASE)
SLUG = re.compile(r"[a-z0-9-]{1,130}")
# What members type when they don't know or there isn't one name. A page for "Various" or
# "Unknown" would lump unrelated titles together under a name that isn't anyone's.
PLACEHOLDER_SLUGS = frozenset({
    "title", "various", "various-artists", "various-authors", "various-directors", "va", "v-a", "unknown",
    "unknown-artist", "unknown-author", "unknown-director", "unknown-host", "anonymous", "anon", "n-a", "na",
    "none", "null", "tbd", "tba", "multiple", "multiple-artists", "multiple-authors", "others", "other", "misc",
    "self", "me", "idk", "not-sure", "untitled", "no-one", "nobody",
})
MAX_WORKS = 60
MIN_LINKED_WORKS = 2  # A page about one title says nothing its title page doesn't.
INDEX_MIN_WORKS = 3
INDEX_MIN_RATED_WORKS = 2
INDEX_MIN_REVIEWS = 2
MIN_OVERALL_RATINGS = 5


def name_slug(name: str) -> str:
    return title_pages.slugify(" ".join((name or "").split()))


def is_real_name(name: str) -> bool:
    slug = name_slug(name)
    return bool(slug) and slug not in PLACEHOLDER_SLUGS


def path(entity: str, name: str) -> str:
    return f"{PREFIX[entity]}/{name_slug(name)}"


def split_names(value: str, role: str) -> list[str]:
    """The names in one fact value: "Phil Lord, Christopher Miller" is two people, "Square Enix Co., Ltd." one company."""
    value = " ".join((value or "").split())
    if not value:
        return []
    if role in UNSPLIT_ROLES:
        return [value[:200]] if is_real_name(value) else []
    names: list[str] = []
    for part in value.split(", "):
        part = part.strip()
        if not part:
            continue
        if names and COMPANY_SUFFIX.match(part):
            names[-1] = f"{names[-1]}, {part}"
        else:
            names.append(part)
    return [name[:200] for name in dict.fromkeys(names) if is_real_name(name)]


def credits_in(kind: str, data: Optional[dict]) -> list[tuple[str, str, str]]:
    """(entity, role, name) for every credit in a title's cached facts."""
    roles = FACT_ROLES.get(kind) or {}
    found = []
    for fact in (data or {}).get("facts") or []:
        if not isinstance(fact, dict) or fact.get("label") not in roles:
            continue
        entity, role = roles[fact["label"]]
        for name in split_names(str(fact.get("value") or ""), role):
            found.append((entity, role, name))
    return found


def index_title(db: Session, key: str, data: Optional[dict]) -> None:
    """Replace the stored credits for one cached title. The caller commits."""
    kind = key.split(":", 1)[0]
    rows, seen = [], set()
    for entity, role, name in credits_in(kind, data):
        slug = name_slug(name)
        if (entity, role, slug) in seen:
            continue
        seen.add((entity, role, slug))
        rows.append(models.TitleCredit(metadata_key=key[:300], kind=kind, entity=entity, role=role, name=name, slug=slug))
    db.query(models.TitleCredit).filter(models.TitleCredit.metadata_key == key[:300]).delete(synchronize_session=False)
    db.add_all(rows)


_backfilled: set[int] = set()


def backfill(db: Session, batch: int = 2000) -> int:
    """Index cached titles that have no credits yet (facts stored before this table existed)."""
    known = db.query(models.TitleCredit.metadata_key).distinct()
    rows = (db.query(models.TitleMetadata.id, models.TitleMetadata.key, models.TitleMetadata.data)
            .filter(models.TitleMetadata.status == "ok", models.TitleMetadata.data.isnot(None),
                    ~models.TitleMetadata.key.in_(known))
            .order_by(models.TitleMetadata.id).limit(batch + len(_backfilled)).all())
    done = 0
    for row_id, key, payload in rows:
        if row_id in _backfilled or done >= batch:
            continue
        _backfilled.add(row_id)  # Titles with no credits at all would otherwise be read every run.
        try:
            data = json.loads(payload)
        except ValueError:
            continue
        index_title(db, key, data)
        done += 1
    db.commit()
    return done


# ---------------------------------------------------------------- one page

@dataclass
class Work:
    kind: str
    title: str
    year: Optional[int]
    url: str
    image: Optional[str]
    roles: set = field(default_factory=set)
    members: int = 0
    finished: int = 0
    rated: int = 0
    average: Optional[float] = None
    reviews: list = field(default_factory=list)
    member_ids: set = field(default_factory=set)
    ratings: list = field(default_factory=list)


@dataclass
class Page:
    entity: str
    slug: str
    name: str
    works: list
    roles: Counter
    collaborators: list = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"{PREFIX[self.entity]}/{self.slug}"


def _key_parts(key: str) -> Optional[tuple[str, str, Optional[int]]]:
    kind, _, rest = key.partition(":")
    normalized, _, year = rest.rpartition(":")
    if kind not in title_pages.KINDS or not normalized:
        return None
    return kind, normalized, int(year) if year.isdigit() else None


def _library_credits(db: Session, slug: str, memo: Optional[dict] = None) -> list[tuple[str, str, str, str]]:
    """(kind, title slug, role, name as typed) from the creator field members fill in.

    The sitemap builds a couple of hundred pages in a row; with a memo it reads each
    kind's (creator, title, year) list once instead of once per page.
    """
    words = [w for w in slug.split("-") if w]
    longest = max(words, key=len) if words else ""
    found = []
    for kind, role in LIBRARY_ROLES.items():
        model, creator_field = title_pages.KINDS[kind][0], title_pages.KINDS[kind][4]
        column = getattr(model, creator_field)
        query = (title_pages._visible_rows(db, kind, model)
                 .filter(~model.user_id.in_(title_pages._editor_ids(db)))
                 .with_entities(column, model.title, model.year))
        if memo is not None:
            if kind not in memo:
                memo[kind] = query.distinct().all()
            rows = [row for row in memo[kind] if len(longest) < 2 or longest in (row[0] or "").lower()]
        else:
            if len(longest) >= 2:
                query = query.filter(func.lower(column).contains(longest))
            rows = query.distinct().limit(3000)
        for creator, title, year in rows:
            if not (title or "").strip():
                continue
            for name in split_names(creator or "", role):
                if name_slug(name) == slug:
                    found.append((kind, title_pages.title_slug(title, year or None), role, name))
    return found


def _collaborators(db: Session, entity: str, slug: str, keys: list[str], limit: int = 12) -> list[dict]:
    """People and companies credited on the most of the same titles."""
    if not keys:
        return []
    shared = func.count(func.distinct(models.TitleCredit.metadata_key))
    rows = (db.query(models.TitleCredit.entity, models.TitleCredit.slug, func.min(models.TitleCredit.name), shared)
            .filter(models.TitleCredit.metadata_key.in_(keys[:400]))
            .filter(~((models.TitleCredit.entity == entity) & (models.TitleCredit.slug == slug)))
            .filter(~models.TitleCredit.slug.in_(PLACEHOLDER_SLUGS))
            .group_by(models.TitleCredit.entity, models.TitleCredit.slug)
            .order_by(shared.desc(), models.TitleCredit.slug).limit(limit * 3).all())
    people = [{"entity": e, "name": n, "url": f"{PREFIX[e]}/{s}", "shared": int(c)} for e, s, n, c in rows]
    # One shared title is just a cast list; prefer repeat collaborations when there are any.
    repeat = [p for p in people if p["shared"] >= 2]
    return (repeat or people)[:limit]


def _decorate_reviews(db: Session, reviews: list) -> None:
    """Spoiler flags, helpful counts and profile links, as the title pages show them."""
    if not reviews:
        return
    from . import review_spoilers
    from .public_profiles import enabled_profile_paths
    from .routers.reviews import review_helpful_counts
    review_spoilers.attach(db, reviews)
    counts = review_helpful_counts(db, [(r["category"], r["id"]) for r in reviews])
    profiles = enabled_profile_paths(db, [r["user_id"] for r in reviews])
    for review in reviews:
        review["helpful"] = counts.get((review["category"], review["id"]), 0)
        review["profile_url"] = profiles.get(review["user_id"])


def build(db: Session, entity: str, slug: str, memo: Optional[dict] = None) -> Optional[Page]:
    """One person's or studio's page. ``memo`` (a dict the caller keeps) shares title lookups across pages."""
    if entity not in PREFIX or not SLUG.fullmatch(slug or "") or slug in PLACEHOLDER_SLUGS:
        return None
    credits = (db.query(models.TitleCredit).filter(models.TitleCredit.entity == entity, models.TitleCredit.slug == slug)
               .limit(400).all())
    names: Counter = Counter()
    wanted: dict[tuple[str, str], set] = defaultdict(set)
    keys_by_title: dict[tuple[str, str], str] = {}
    for credit in credits:
        parts = _key_parts(credit.metadata_key)
        if parts is None:
            continue
        kind, normalized, year = parts
        title_slug = title_pages.title_slug(normalized, year)
        wanted[(kind, title_slug)].add(credit.role)
        keys_by_title[(kind, title_slug)] = credit.metadata_key
        names[credit.name] += 1
    if entity == PERSON:
        library_memo = memo.setdefault("library", {}) if memo is not None else None
        for kind, title_slug, role, name in _library_credits(db, slug, library_memo):
            wanted[(kind, title_slug)].add(role)
            names[name] += 3  # Members' own spelling wins over a database's.
    if not wanted:
        return None
    groups = {}
    found = memo.setdefault("groups", {}) if memo is not None else {}
    for kind in title_pages.KINDS:
        slugs = [s for k, s in wanted if k == kind and (k, s) not in found]
        if slugs:
            matched = title_pages.find_many(db, kind, slugs)
            for title_slug in slugs:
                found[(kind, title_slug)] = matched.get(title_slug)
    for kind in title_pages.KINDS:
        for key in wanted:
            if key[0] == kind and found.get(key) is not None:
                groups[key] = found[key]
    summaries = memo.setdefault("summaries", {}) if memo is not None else {}
    editors = {uid for uid, in title_pages._editor_ids(db).all()}
    works, seen = [], set()
    for key, group in groups.items():
        if group.path in seen:
            continue
        seen.add(group.path)
        summary = summaries.get(group.path)
        if summary is None:
            summary = summaries[group.path] = title_pages.summarize(db, group, page_sections=False)
        per_member = {}
        for item in sorted(group.items, key=lambda entry: entry.id):
            if item.user_id not in editors and item.rating is not None:
                per_member[item.user_id] = item.rating
        works.append(Work(
            kind=group.kind, title=group.title, year=group.year, url=group.path, image=summary["image"],
            roles=wanted[key], members=summary["members"], finished=summary["finished"], rated=summary["rated"],
            average=summary["average_rating"], reviews=[r for r in summary["reviews"] if r["search_ready"]],
            member_ids={item.user_id for item in group.items if item.user_id not in editors},
            ratings=list(per_member.values())))
    if not works:
        return None
    works.sort(key=lambda w: (-w.members, -(w.average or 0), w.title.casefold()))
    works = works[:MAX_WORKS]
    roles: Counter = Counter()
    for work in works:
        roles.update(work.roles)
    _decorate_reviews(db, [review for work in works for review in work.reviews])
    page = Page(entity=entity, slug=slug, name=names.most_common(1)[0][0], works=works, roles=roles)
    keys = [keys_by_title[(w.kind, w.url.rsplit("/", 1)[1])] for w in works if (w.kind, w.url.rsplit("/", 1)[1]) in keys_by_title]
    page.collaborators = _collaborators(db, entity, slug, keys)
    return page


def stats(page: Page) -> dict:
    """Numbers for the page header and summary paragraph."""
    members = set()
    ratings = []
    for work in page.works:
        members |= work.member_ids
        ratings += work.ratings
    rated_works = [w for w in page.works if w.average is not None]
    best = max(rated_works, key=lambda w: (w.average, w.rated)) if rated_works else None
    lowest = min(rated_works, key=lambda w: (w.average, -w.rated)) if len(rated_works) >= 3 else None
    most_tracked = max(page.works, key=lambda w: (w.members, w.rated)) if page.works else None
    reviews = sorted((dict(review, work=work) for work in page.works for review in work.reviews),
                     key=lambda r: (-r.get("helpful", 0), -len(r["review"])))
    return {
        "titles": len(page.works),
        "members": len(members),
        "ratings": len(ratings),
        "average": round(sum(ratings) / len(ratings), 1) if len(ratings) >= MIN_OVERALL_RATINGS else None,
        "rated_works": rated_works,
        "best": best,
        "lowest": lowest if lowest is not best else None,
        "most_tracked": most_tracked,
        "reviews": reviews,
        "kinds": Counter(w.kind for w in page.works),
    }


def is_indexable(page: Page, numbers: Optional[dict] = None) -> bool:
    """Search engines (and ads) get the page only when members have said enough about the work.

    A list of credits is the same everywhere on the web. What makes this page ours is
    member ratings across several titles and enough review writing to read.
    """
    numbers = numbers or stats(page)
    reviews = numbers["reviews"]
    return (numbers["titles"] >= INDEX_MIN_WORKS and len(numbers["rated_works"]) >= INDEX_MIN_RATED_WORKS
            and len(reviews) >= INDEX_MIN_REVIEWS
            and sum(word_count(r["review"]) for r in reviews) >= AD_MIN_REVIEW_WORDS)


# ---------------------------------------------------------------- links from title pages

def title_links(db: Session, kind: str, metadata: Optional[dict], creator: Optional[str], creator_has_more: bool) -> dict:
    """{name: page path} for the credits on a title page that have a page worth opening."""
    candidates: dict[tuple[str, str], str] = {}
    for entity, _, name in credits_in(kind, metadata):
        candidates.setdefault((entity, name_slug(name)), name)
    if not candidates and not creator:
        return {}
    links = {}
    try:
        counts = dict(((e, s), c) for e, s, c in db.query(
            models.TitleCredit.entity, models.TitleCredit.slug, func.count(func.distinct(models.TitleCredit.metadata_key)))
            .filter(models.TitleCredit.slug.in_([slug for _, slug in candidates] or [""]))
            .group_by(models.TitleCredit.entity, models.TitleCredit.slug).all())
    except Exception:
        db.rollback()
        counts = {}
    for (entity, slug), name in candidates.items():
        if counts.get((entity, slug), 0) >= MIN_LINKED_WORKS:
            links[name] = f"{PREFIX[entity]}/{slug}"
    if creator and kind in LIBRARY_ROLES and is_real_name(creator):
        slug = name_slug(creator)
        if creator_has_more or counts.get((PERSON, slug), 0) >= MIN_LINKED_WORKS:
            for name in split_names(creator, LIBRARY_ROLES[kind]) or [creator]:
                links.setdefault(name, path(PERSON, name))
    return links


# ---------------------------------------------------------------- directory

def directory(db: Session, entity: str, per_role: int = 18) -> dict[str, list[dict]]:
    """The most-credited names for each role, for /people and /studios."""
    by_role: dict[str, Counter] = defaultdict(Counter)
    spelled: dict[str, Counter] = defaultdict(Counter)
    titles = func.count(func.distinct(models.TitleCredit.metadata_key))
    for role, slug, name, count in (db.query(models.TitleCredit.role, models.TitleCredit.slug,
                                             func.min(models.TitleCredit.name), titles)
                                    .filter(models.TitleCredit.entity == entity)
                                    .group_by(models.TitleCredit.role, models.TitleCredit.slug)
                                    .having(titles >= MIN_LINKED_WORKS).all()):
        if slug in PLACEHOLDER_SLUGS:  # Credits indexed before the placeholder list existed.
            continue
        by_role[role][slug] = int(count)
        spelled[slug][name] += 1
    if entity == PERSON:
        for kind, role in LIBRARY_ROLES.items():
            model, creator_field = title_pages.KINDS[kind][0], title_pages.KINDS[kind][4]
            column = func.lower(func.trim(getattr(model, creator_field)))
            distinct_titles = func.count(func.distinct(func.lower(func.trim(model.title))))
            rows = (db.query(column, func.min(getattr(model, creator_field)), distinct_titles)
                    .filter(model.user_id.in_(title_pages._shareable_ids(db, kind)),
                            ~model.user_id.in_(title_pages._editor_ids(db)),
                            getattr(model, creator_field).isnot(None))
                    .group_by(column).having(distinct_titles >= MIN_LINKED_WORKS)
                    .order_by(distinct_titles.desc()).limit(300).all())
            for _, name, count in rows:
                for one in split_names(name or "", role):
                    slug = name_slug(one)
                    by_role[role][slug] = max(by_role[role][slug], int(count))
                    spelled[slug][one.strip()] += 3
    result = {}
    for role in ROLE_ORDER:
        if role not in by_role:
            continue
        entries = [{"slug": slug, "name": spelled[slug].most_common(1)[0][0], "titles": count,
                    "url": f"{PREFIX[entity]}/{slug}"}
                   for slug, count in by_role[role].most_common(per_role)]
        if entries:
            result[role] = entries
    return result


def sitemap_paths(db: Session, limit: int = 200) -> list[str]:
    paths = []
    memo: dict = {}  # Pages share most of their titles; look each one up once.
    for entity in PREFIX:
        seen = set()
        for entries in directory(db, entity, per_role=40).values():
            for entry in entries:
                if entry["slug"] in seen or entry["titles"] < INDEX_MIN_WORKS or len(paths) >= limit:
                    continue
                seen.add(entry["slug"])
                page = build(db, entity, entry["slug"], memo)
                if page is not None and is_indexable(page):
                    paths.append(page.path)
    return paths
