"""Awards season ballots: pick the winners of a show, save and share the ballot, get a score (Nov 2026).

The shows, their dates and nominees are data (app/awards_data.py). This module
adds what a member does with them:

* a ballot: one pick per category, kept as JSON on an ``AwardBallot`` row and
  checked against the show's data on every read and write, so a renamed or
  removed nominee simply drops out of old ballots,
* the lock: picks close when the ceremony starts (``ceremony_at``, UTC),
* results: a site admin marks winners on the show's page (``AwardResult``), or
  they are written into the data; either way every ballot gets a score,
* a share link and card for a ballot, on request only,
* which nominees a member already tracks, and adding the rest. Matching and
  saving reuse the "In order" guides' code (in_order.library_matches,
  pick.add_to_library), so a nominee lands in the library like any other title.

Public pages show how members voted only after the ballot locks and only once
``MIN_PUBLIC_BALLOTS`` members have filled one in.
"""
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from typing import Optional

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import awards_data, models, title_pages

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
BASE_PATH = "/awards"
MIN_PUBLIC_BALLOTS = 5
# The dashboard card keeps showing a member's score this long after the ceremony.
RESULTS_CARD_DAYS = 14
TRACKABLE_KINDS = ("movie", "tv", "anime", "game", "album", "book")


class BallotLocked(ValueError):
    """Picks can't change once the ceremony has started."""


def _now() -> datetime:
    return datetime.utcnow()


# ---------------------------------------------------------------- shows

def get(slug: str) -> Optional[dict]:
    return awards_data.SHOWS.get(slug)


def ordered() -> list[tuple[str, dict]]:
    """Every show in calendar order."""
    listed = [slug for slug in awards_data.ORDER if slug in awards_data.SHOWS]
    listed += sorted((slug for slug in awards_data.SHOWS if slug not in listed),
                     key=lambda slug: awards_data.SHOWS[slug]["ceremony_at"])
    return [(slug, awards_data.SHOWS[slug]) for slug in listed]


def path(slug: str) -> str:
    return f"{BASE_PATH}/{slug}"


def ceremony_at(show: dict) -> datetime:
    return datetime.fromisoformat(show["ceremony_at"])


def _item(source: dict, name: str) -> Optional[dict]:
    """The title a nominee stands for, shaped for library matching and saving; None for people and teams."""
    kind = source.get("kind")
    if kind not in TRACKABLE_KINDS:
        return None
    title = source.get("title") or name
    year = source.get("year")
    year = year if isinstance(year, int) and not isinstance(year, bool) and 1800 <= year <= 2100 else None
    return {"id": f"{kind}/{title_pages.title_slug(title, year)}", "kind": kind, "title": title, "year": year,
            "creator": source.get("creator") or None, "aka": tuple(source.get("aka", ()))}


def categories(show: dict) -> list[dict]:
    """The ballot: categories with their nominees, keys filled in. Empty until nominees are announced."""
    result = []
    for category in show.get("categories") or ():
        nominees = []
        for nominee in category["nominees"]:
            nominees.append({
                "key": nominee.get("key") or title_pages.slugify(nominee["name"]),
                "name": nominee["name"],
                "detail": nominee.get("detail") or "",
                "item": _item(nominee, nominee["name"]),
            })
        result.append({
            "key": category.get("key") or title_pages.slugify(category["name"]),
            "name": category["name"],
            "blurb": category.get("blurb") or "",
            "nominees": nominees,
            "winner": category.get("winner"),
        })
    return result


def has_nominees(show: dict) -> bool:
    return bool(show.get("categories"))


def is_locked(show: dict, now: Optional[datetime] = None) -> bool:
    return (now or _now()) >= ceremony_at(show)


def is_open(show: dict, now: Optional[datetime] = None) -> bool:
    return has_nominees(show) and not is_locked(show, now)


def days_left(show: dict, now: Optional[datetime] = None) -> int:
    """Whole days until picks lock (0 on the day)."""
    return max(0, (ceremony_at(show) - (now or _now())).days)


def state(show: dict, decided: int, now: Optional[datetime] = None) -> str:
    """coming (no nominees yet), open, locked (show under way or results partly in) or results."""
    if not has_nominees(show):
        return "coming"
    if not is_locked(show, now):
        return "open"
    return "results" if decided and decided >= len(show["categories"]) else "locked"


def last_year_winners(show: dict) -> list[dict]:
    rows = []
    for category, name, detail, source in (show.get("last_year") or {}).get("winners", ()):
        rows.append({"category": category, "name": name, "detail": detail,
                     "item": _item(source, name) if source else None})
    return rows


def linked_items(show: dict) -> list[dict]:
    """Every trackable title on the page (nominees and last year's winners), once each."""
    found: dict[str, dict] = {}
    for category in categories(show):
        for nominee in category["nominees"]:
            if nominee["item"]:
                found.setdefault(nominee["item"]["id"], nominee["item"])
    for row in last_year_winners(show):
        if row["item"]:
            found.setdefault(row["item"]["id"], row["item"])
    return list(found.values())


# ---------------------------------------------------------------- results

def results(db: Session, slug: str) -> dict[str, str]:
    """{category key: winning nominee key}. Winners in the data win over rows an admin entered."""
    show = get(slug)
    if show is None:
        return {}
    valid = {category["key"]: {nominee["key"] for nominee in category["nominees"]} for category in categories(show)}
    found = {}
    for category, nominee in db.query(models.AwardResult.category, models.AwardResult.nominee).filter_by(show=slug):
        if nominee in valid.get(category, ()):
            found[category] = nominee
    for category in categories(show):
        if category["winner"] in valid[category["key"]]:
            found[category["key"]] = category["winner"]
    return found


def set_result(db: Session, slug: str, category: str, nominee: Optional[str]) -> dict[str, str]:
    """Record (or with ``nominee`` None, clear) one category's winner. Returns the results after the change."""
    show = get(slug)
    if show is None:
        raise ValueError("Unknown show.")
    listed = {entry["key"]: entry for entry in categories(show)}
    if category not in listed:
        raise ValueError("Unknown category.")
    row = db.query(models.AwardResult).filter_by(show=slug, category=category).first()
    if nominee is None:
        if row is not None:
            db.delete(row)
            db.commit()
        return results(db, slug)
    if nominee not in {entry["key"] for entry in listed[category]["nominees"]}:
        raise ValueError("Unknown nominee.")
    if row is None:
        db.add(models.AwardResult(show=slug, category=category, nominee=nominee))
    else:
        row.nominee = nominee
        row.updated_at = _now()
    try:
        db.commit()
    except IntegrityError:
        # Two admins marked the same category at once: the second one updates the first one's row.
        db.rollback()
        row = db.query(models.AwardResult).filter_by(show=slug, category=category).first()
        if row is not None:
            row.nominee = nominee
            row.updated_at = _now()
            db.commit()
    return results(db, slug)


# ---------------------------------------------------------------- ballots

def get_ballot(db: Session, user_id: int, slug: str) -> Optional[models.AwardBallot]:
    return db.query(models.AwardBallot).filter_by(user_id=user_id, show=slug).first()


def picks_of(row: Optional[models.AwardBallot], show: dict) -> dict[str, str]:
    """The saved picks that still name a real category and nominee, in ballot order."""
    if row is None:
        return {}
    try:
        saved = json.loads(row.picks or "{}")
    except (TypeError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        return {}
    kept = {}
    for category in categories(show):
        choice = saved.get(category["key"])
        if isinstance(choice, str) and any(nominee["key"] == choice for nominee in category["nominees"]):
            kept[category["key"]] = choice
    return kept


def _row_for(db: Session, user_id: int, slug: str) -> tuple[models.AwardBallot, bool]:
    row = get_ballot(db, user_id, slug)
    if row is not None:
        return row, False
    row = models.AwardBallot(user_id=user_id, show=slug, picks="{}")
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        # Another tab made the row first.
        db.rollback()
        return get_ballot(db, user_id, slug), False
    return row, True


def save_picks(db: Session, user_id: int, slug: str, changes: dict,
               now: Optional[datetime] = None) -> tuple[models.AwardBallot, bool]:
    """Apply ``{category: nominee or None}`` to the member's ballot. Returns (ballot, first pick ever made).

    Categories left out keep their pick, so the page can save one click at a time.
    """
    show = get(slug)
    if show is None or not has_nominees(show):
        raise ValueError("This ballot isn't open yet.")
    if is_locked(show, now):
        raise BallotLocked("The show has started, so picks are locked.")
    if not isinstance(changes, dict) or not changes:
        raise ValueError("Pick a nominee first.")
    listed = {category["key"]: {nominee["key"] for nominee in category["nominees"]} for category in categories(show)}
    for category, nominee in changes.items():
        if category not in listed:
            raise ValueError("Unknown category.")
        if nominee is not None and nominee not in listed[category]:
            raise ValueError("Unknown nominee.")
    row, _ = _row_for(db, user_id, slug)
    current = picks_of(row, show)
    first = not current
    for category, nominee in changes.items():
        if nominee is None:
            current.pop(category, None)
        else:
            current[category] = nominee
    row.picks = json.dumps(current, sort_keys=True)
    row.updated_at = now or _now()
    # Someone who picks has seen that the ballot is open: no "nominees are in" note needed.
    if row.opened_notice_at is None:
        row.opened_notice_at = row.updated_at
    db.commit()
    return row, first and bool(current)


def follow(db: Session, user_id: int, slug: str) -> models.AwardBallot:
    """Ask to hear when the nominees are in: an empty ballot row."""
    show = get(slug)
    if show is None:
        raise ValueError("Unknown show.")
    row, _ = _row_for(db, user_id, slug)
    if has_nominees(show) and row.opened_notice_at is None:
        row.opened_notice_at = _now()
    db.commit()
    return row


def clear(db: Session, user_id: int, slug: str) -> bool:
    """Delete the member's ballot (and with it the share link and any reminder)."""
    row = get_ballot(db, user_id, slug)
    if row is None:
        return False
    db.delete(row)
    db.commit()
    return True


def share(db: Session, row: models.AwardBallot) -> models.AwardBallot:
    if not row.share_token:
        row.share_token = secrets.token_urlsafe(12)
        db.commit()
    return row


def unshare(db: Session, row: models.AwardBallot) -> models.AwardBallot:
    row.share_token = None
    db.commit()
    return row


def share_path(row: models.AwardBallot) -> str:
    return f"/ballot/{row.share_token}"


def find_shared(db: Session, token: str) -> Optional[models.AwardBallot]:
    """A shared ballot for a show that still exists, whose owner is active and who picked something."""
    if not token or len(token) > 32:
        return None
    row = db.query(models.AwardBallot).filter(models.AwardBallot.share_token == token).first()
    if row is None:
        return None
    show = get(row.show)
    owner = db.get(models.User, row.user_id)
    if show is None or owner is None or not owner.is_active or not picks_of(row, show):
        return None
    return row


def score(picks: dict, decided: dict) -> dict:
    """How a ballot did against the winners known so far. Skipped categories never count against it."""
    judged = [category for category in picks if category in decided]
    correct = sum(1 for category in judged if picks[category] == decided[category])
    return {"correct": correct, "judged": len(judged), "decided": len(decided)}


def agreement(mine: dict, theirs: dict) -> dict:
    """How many categories two ballots both filled in, and how many of those match."""
    both = [category for category in mine if category in theirs]
    return {"both": len(both), "same": sum(1 for category in both if mine[category] == theirs[category])}


# ---------------------------------------------------------------- library

def library_states(db: Session, user_id: int, show: dict) -> dict[str, dict]:
    """{item id: {"state": "done" | "tracked", "library_url"}} for the page's titles this member has."""
    from . import in_order
    items = linked_items(show)
    if not items:
        return {}
    return in_order.library_matches(db, user_id, {"entries": items})


def add_title(db: Session, user, show: dict, item_id: str) -> tuple[str, object, dict]:
    """Add one of the page's titles to the member's library as not started. Does not commit.

    Returns ("created" | "existing", record, item). A title the member already has is left as it is.
    """
    from . import in_order, pick
    item = next((entry for entry in linked_items(show) if entry["id"] == item_id), None)
    if item is None:
        raise LookupError("That title isn't on this page.")
    state_, record = pick.add_to_library(db, user, in_order.saveable(item))
    return state_, record, item


def title_details(db: Session, show: dict) -> dict[str, dict]:
    """{item id: {"url", "image"}} for titles with a public title page (never raises).

    Matched the way the guides do it: the exact slug first, then the most-tracked
    title with the same base name.
    """
    from . import title_search
    try:
        index = title_search.index(db)
    except Exception:
        return {}
    by_slug = {(entry["kind"], entry["slug"]): entry for entry in index}
    by_base: dict[tuple[str, str], dict] = {}
    for entry in index:
        current = by_base.get((entry["kind"], entry["base"]))
        if current is None or entry["members"] > current["members"]:
            by_base[(entry["kind"], entry["base"])] = entry
    details = {}
    for item in linked_items(show):
        slug = item["id"].split("/", 1)[1]
        match = by_slug.get((item["kind"], slug)) or by_base.get((item["kind"], title_pages.slugify(item["title"])))
        if match is not None:
            details[item["id"]] = {"url": f"/titles/{match['kind']}/{match['slug']}", "image": match.get("image")}
    return details


# ---------------------------------------------------------------- public numbers

def _active_ballots(db: Session, slug: str):
    return (db.query(models.AwardBallot)
            .join(models.User, models.User.id == models.AwardBallot.user_id)
            .filter(models.AwardBallot.show == slug, models.User.is_active.is_(True)))


def tallies(db: Session, slug: str, now: Optional[datetime] = None) -> dict:
    """How members voted, as whole percentages per nominee.

    Shown only after the ballot locks (so it can't steer anyone's picks) and only
    for categories at least MIN_PUBLIC_BALLOTS members filled in.
    """
    show = get(slug)
    result = {"ballots": 0, "show": False, "categories": {}}
    if show is None or not has_nominees(show):
        return result
    counts: dict[str, dict[str, int]] = {}
    for row in _active_ballots(db, slug):
        chosen = picks_of(row, show)
        if not chosen:
            continue
        result["ballots"] += 1
        for category, nominee in chosen.items():
            counts.setdefault(category, {})
            counts[category][nominee] = counts[category].get(nominee, 0) + 1
    if not is_locked(show, now) or result["ballots"] < MIN_PUBLIC_BALLOTS:
        return result
    nominees = {category["key"]: [nominee["key"] for nominee in category["nominees"]] for category in categories(show)}
    for category, votes in counts.items():
        total = sum(votes.values())
        if total >= MIN_PUBLIC_BALLOTS:
            result["categories"][category] = {nominee: round(100 * votes.get(nominee, 0) / total)
                                              for nominee in nominees[category]}
    result["show"] = bool(result["categories"])
    return result


# ---------------------------------------------------------------- payloads

def payload(db: Session, user, slug: str, now: Optional[datetime] = None) -> dict:
    """The member's side of one show, for the page script."""
    now = now or _now()
    show = get(slug)
    row = get_ballot(db, user.id, slug)
    chosen = picks_of(row, show)
    decided = results(db, slug)
    return {
        "show": slug,
        "name": show["name"],
        "state": state(show, len(decided), now),
        "total": len(show.get("categories") or ()),
        "picks": chosen,
        "picked": len(chosen),
        "following": row is not None,
        "results": decided,
        "score": score(chosen, decided),
        "shared": bool(row and row.share_token),
        "url": SITE_URL + share_path(row) if row is not None and row.share_token else None,
        "days_left": days_left(show, now),
        "page": path(slug),
    }


def card_payload(db: Session, user, now: Optional[datetime] = None) -> dict:
    """The dashboard card: the next open ballot, or the member's score for a show that just finished."""
    now = now or _now()
    for slug, show in ordered():
        if not is_open(show, now):
            continue
        row = get_ballot(db, user.id, slug)
        chosen = picks_of(row, show)
        return {"show": True, "state": "open", "slug": slug, "name": show["name"], "short": show["short"],
                "picked": len(chosen), "total": len(show["categories"]), "days_left": days_left(show, now),
                "lock_label": show["lock_label"], "page": path(slug),
                "shared": bool(row and row.share_token),
                "url": SITE_URL + share_path(row) if row is not None and row.share_token else None}
    for slug, show in reversed(ordered()):
        if not has_nominees(show) or not is_locked(show, now):
            continue
        if (now - ceremony_at(show)).days > RESULTS_CARD_DAYS:
            continue
        row = get_ballot(db, user.id, slug)
        chosen = picks_of(row, show)
        decided = results(db, slug)
        if not chosen or not decided:
            continue
        marks = score(chosen, decided)
        return {"show": True, "state": state(show, len(decided), now), "slug": slug, "name": show["name"],
                "short": show["short"], "picked": len(chosen), "total": len(show["categories"]),
                "correct": marks["correct"], "judged": marks["judged"], "decided": marks["decided"],
                "page": path(slug), "shared": bool(row.share_token),
                "url": SITE_URL + share_path(row) if row.share_token else None}
    return {"show": False}


# ---------------------------------------------------------------- notes to members

def send_notices(db: Session, now: Optional[datetime] = None) -> dict:
    """Bell notes, once each per member and show (they reach phones through web push's own hooks).

    * "nominees are in" for members who asked to hear and haven't picked yet,
    * "winners are in" with the score, once every category has a winner.
    """
    now = now or _now()
    sent = {"opened": 0, "results": 0}
    for slug, show in ordered():
        if not has_nominees(show):
            continue
        if is_open(show, now):
            waiting = _active_ballots(db, slug).filter(models.AwardBallot.opened_notice_at.is_(None)).all()
            for row in waiting:
                row.opened_notice_at = now
                if not picks_of(row, show):
                    db.add(models.Notification(
                        user_id=row.user_id, type="awards_ballot_open", link=f"{path(slug)}#ballot",
                        message=f"{show['name']} nominees are in. Your ballot is open until {show['lock_label']}."[:250]))
                    sent["opened"] += 1
            db.commit()
            continue
        decided = results(db, slug)
        if state(show, len(decided), now) != "results":
            continue
        waiting = _active_ballots(db, slug).filter(models.AwardBallot.results_notice_at.is_(None)).all()
        for row in waiting:
            row.results_notice_at = now
            chosen = picks_of(row, show)
            if chosen:
                marks = score(chosen, decided)
                db.add(models.Notification(
                    user_id=row.user_id, type="awards_results", link=f"{path(slug)}#ballot",
                    message=(f"{show['name']} winners are in. You called {marks['correct']} of "
                             f"{marks['judged']} on your ballot.")[:250]))
                sent["results"] += 1
        db.commit()
    return sent


def headline(username: str, show: dict) -> str:
    return f"{username}'s {show['name']} ballot"
