"""Monthly challenges: one small, opt-in challenge a month, e.g. "finish one pick from the October edition".

Progress is never stored. It is counted from the same finishes Year in Review
and yearly goals use (journal "finished" entries and completion moments), only
for the calendar month (UTC), so editing the library keeps it right and
finishes from before a member joined still count.

A member's entry row records only that they took the challenge, when they
completed it, whether they dismissed the celebration, and an optional share
token. Public pages show the editorial guide and aggregate counts, never
anyone's titles.
"""
from __future__ import annotations

import os
import secrets
from calendar import monthrange
from datetime import date, datetime
from typing import Optional

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import diary, models, title_pages, year_in_review
from .discover_catalog import MONTHLY_EDITIONS, published_editions

SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
# Aggregate counts appear on public pages only once they stop pointing at individuals.
MIN_PUBLIC_COUNT = 3
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]
FORMAT_NOUNS = {
    "movies": ("movie", "movies"), "tv-shows": ("TV show", "TV shows"), "anime": ("anime", "anime"),
    "video-games": ("game", "games"), "music": ("album", "albums"), "books": ("book", "books"),
    "manga": ("manga series", "manga series"),
    "podcasts": ("podcast", "podcasts"),
    "audiobooks": ("audiobook", "audiobooks"),
}

# Curated challenges, keyed by month ("YYYY-MM"). Step kinds:
#   total       finish ``count`` titles this month
#   formats     finish titles in ``count`` different formats
#   reflect     rate or write a takeaway/note for ``count`` finishes
#   edition     finish one pick from the Discover monthly edition ``edition``
#   before      finish one title released before ``year``
#   category    finish ``count`` titles of one format (``category``)
#   waiting     finish ``count`` titles that were already in the library before the month began
#   revisit     revisit ``count`` titles: a journal "Revisited" entry, or another finish of a title finished before
# A challenge with ``"revisits_count": True`` also counts a logged revisit as a finish for its other steps.
CHALLENGES: dict[str, dict] = {
    "2026-10": {
        "name": "Stay with the strange",
        "tagline": "Three small steps through a month of quiet ghosts, unexplained signals and stories that refuse to resolve.",
        "published": "2026-10-10",
        "edition": "october-2026",
        "intro": [
            "October tends to arrive with a checklist: the horror marathon, the scariest-ever list, the film everyone says you must see before Halloween. This challenge asks for something gentler. It shares an idea with this month's Discover edition: a story can unsettle you without explaining itself, and the strangeness that stays with you longest is often the low-key kind.",
            "There are three steps. None of them requires you to watch anything frightening, and none of them depends on a particular streaming service. You can finish the whole thing with one film, one album and a sentence you write afterwards, or you can spread it across a book, a game and a long weekend of television. Anything you mark finished in October counts, including things you finished before you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "october-2026",
             "label": "Finish one pick from the October edition",
             "detail": "The October edition picks six works across six formats, from David Lowery's A Ghost Story (one quiet evening) to Shirley Jackson's The Haunting of Hill House (a short novel best read slowly). Choose by the time you have, not by reputation. If you have already finished one of them this month, this step is done."},
            {"kind": "formats", "count": 2,
             "label": "Finish titles in two different formats",
             "detail": "Pair your pick with something in another medium: a film and an album, a book and an anime episode arc, a game and a season of television. Moving between formats is the fastest way to notice what each one does well. Mushi-Shi's self-contained episodes, for example, sit beside Ghosteen's long, unbroken songs in a way that makes both feel slower and stranger."},
            {"kind": "reflect", "count": 1,
             "label": "Rate it or jot a takeaway",
             "detail": "When you mark something finished, OmniTrackr offers a rating and a one-line takeaway. Use either once this month. A takeaway does not need to be clever. \"I kept thinking about the house after I closed the book\" will tell you more next year than a star count, and it stays private unless you choose to publish a review."},
        ],
        "reflection": "When a story leaves something unresolved, notice whether you lean in or reach for an explanation. Neither is wrong, and knowing which one you are this month makes your next pick easier.",
    },
    "2026-11": {
        "name": "The long way round",
        "tagline": "Slow down with something older, something on paper and a short run of titles you choose yourself.",
        "published": "2026-10-10",
        "edition": "november-2026",
        "intro": [
            "November is the month when evenings get long and recommendations get loud. Every service is pushing the newest release, and most best-of-the-year lists are already being drafted. This challenge pulls in the other direction. It asks you to finish something that has been around for a while, to spend some of your time with a book, and to keep a small, honest count of what you actually finished.",
            "Older works are not homework. A film from the 1970s or a game from the 1990s often moves at a different pace, trusts its audience with longer silences or leaves its rough edges in place. Coming back to the present afterwards tends to make newer work easier to judge. Anything you mark finished in November counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "before", "year": 2000,
             "label": "Finish one title released before 2000",
             "detail": "Any format counts: a classic film, an album you know only from samples, a novel from your parents' shelf or a game you never had the console for. Pick something you are curious about, even if it isn't the one you feel you ought to have seen. The release year comes from the title in your library, so check that it is filled in."},
            {"kind": "category", "category": "books", "count": 1,
             "label": "Finish one book",
             "detail": "Short books count as much as long ones. A novella, a graphic novel, a poetry collection or a short essay collection all fit a busy month. If you are between books, the Discover guides include several that can be read in a weekend."},
            {"kind": "total", "count": 3,
             "label": "Finish three titles this month",
             "detail": "Three is a low bar on purpose. It leaves room for one long game or series alongside the two steps above, and most members reach it without changing their habits. Nobody is racing."},
        ],
        "reflection": "Which of this month's finishes felt most like its own time, and which felt like it could have been made last year?",
    },
    "2026-12": {
        "name": "Close the year kindly",
        "tagline": "Finish a few things across formats and leave notes your January self will thank you for.",
        "published": "2026-10-10",
        # The December edition (out December 1) is written around this challenge's four titles in three formats.
        "edition": "december-2026",
        "intro": [
            "December is when Year in Review fills in, and it is tempting to treat the last month as a sprint to pad the numbers. This challenge is designed for the opposite mood. It asks you to finish a handful of things across more than one format and to leave a short note on a couple of them, so that the year ends with a record you will actually want to reread.",
            "Holiday breaks are good for long games and box sets, and short gaps between plans are good for albums and films. Mix them however suits your month. Anything you mark finished in December counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "total", "count": 4,
             "label": "Finish four titles this month",
             "detail": "Four is about one a week. If a long game or a thick book is taking most of your time, keep going with it and fit a couple of albums or films around it."},
            {"kind": "formats", "count": 3,
             "label": "Use at least three formats",
             "detail": "Three of the nine formats OmniTrackr tracks is enough to make your Year in Review show a fuller picture of what you enjoyed, and it is a good excuse to return to a format you drifted away from earlier in the year."},
            {"kind": "reflect", "count": 2,
             "label": "Rate or note two of them",
             "detail": "A rating and a takeaway are the details you will forget first. Add them now and your recap will say why you liked something, and your next recommendations will be better for it."},
        ],
        "reflection": "Which finish this month would you hand to a friend in January, and what would you tell them about it?",
    },
    "2027-01": {
        "name": "First things first",
        "tagline": "Start the year with the first part of something that continues this winter, one title from your backlog and the year's first note.",
        "published": "2027-01-01",
        # The January edition (out January 1) has nine picks, one per format, each the start of a January release.
        "edition": "january-2027",
        "intro": [
            "January is when the new seasons start. In the next few weeks Neuromancer arrives on Apple TV, Children of Blood and Bone opens in cinemas, CHVRCHES release their first album in more than five years and Samus Aran gets a new 2D Metroid game. This challenge, like the January edition it pairs with, asks you to go back to where one of those things started before the new one arrives. It also asks you to finish one title that has been sitting in your library, and to write down what you thought of something, so that the year's record starts with a sentence as well as a number.",
            "If you made a pledge in the 2027 New Year challenge, every finish here counts toward it too. The pledge is the target for the whole year; this is its first month, at a size you can finish by the 31st. Anything you mark finished in January counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "january-2027",
             "label": "Finish one pick from the January edition",
             "detail": "The January edition has nine picks, one in each format OmniTrackr tracks, and each is the start of something that continues this winter: Neuromancer before the Apple TV series on January 22, Metroid Dread before Metroid Ravenous on January 28, the first CHVRCHES album before their fifth on January 22. The shortest is an album of under an hour and the longest an audiobook of almost eighteen. Finish any one of them in January and this step is done."},
            {"kind": "waiting", "count": 1,
             "label": "Finish one title that was already in your library",
             "detail": "Anything that was in your library before January 1 counts, whether you saved it last week or three years ago. Most libraries have a few titles that were saved and never started, or started and left at episode four. Pick the one you feel worst about and finish it. A title you add and finish in January still counts toward the other two steps, just not this one. If one of the edition's picks has been waiting in your library, it can do both."},
            {"kind": "reflect", "count": 1,
             "label": "Leave the year's first rating or takeaway",
             "detail": "Rate a January finish or write a line about it when you mark it finished. Next December your Year in Review will be built from what you record now, and a note written the week you finished something says more than a score added from memory eleven months later. Takeaways stay private unless you publish a review."},
        ],
        "reflection": "If you went back to an original this month, did knowing a new version was coming change how you read, watched or played it?",
    },
    "2027-02": {
        "name": "Love in every form",
        "tagline": "Finish one of February's nine love stories, go back to something you already love and write down why.",
        "published": "2027-02-01",
        # The February edition (out February 1) has nine love stories, one per format, no two of the same kind.
        "edition": "february-2027",
        # A rewatch or reread logged in the journal counts as a finish for every step this month.
        "revisits_count": True,
        "intro": [
            "February has Valentine's Day in the middle of it, and for two weeks every service recommends the same handful of romantic comedies. This challenge, and the February edition it pairs with, take a wider view of what a love story can be. The edition's nine picks include a first love that never happened, a couple who decide to have a baby after six days, two young women who share a name and an apartment, and marriages talked through in a therapist's office. The challenge asks you to finish one of them, to go back to something you have loved for years, and to write a line about why you love something, which is the part most of us skip.",
            "February is also the shortest month, so the steps are small. A rewatch, reread or replay that you log in your Journal counts as a finish for every step this month, so one evening with an old favourite and a sentence afterwards can cover two of the three. Anything you finish or revisit in February counts, whenever you joined.",
        ],
        "steps": [
            {"kind": "edition", "edition": "february-2027",
             "label": "Finish one pick from the February edition",
             "detail": "The February edition has nine love stories, one in each format OmniTrackr tracks. Past Lives is a single evening at 106 minutes, and To the Moon takes most players about four hours. Nana runs to twenty-one volumes and 69 Love Songs to almost three hours, so start those in the first week. If you have seen or read one of the nine before, a rewatch or reread you log this month counts too."},
            {"kind": "revisit", "count": 1,
             "label": "Go back to something you love",
             "detail": "Rewatch a film you know by heart, reread a book you keep lending out, replay a game or put an old album on from the first track. Then log it in your Journal as Revisited: the Log a revisit button on the challenge card opens the Journal with that already chosen. Logging a second finish of something you finished before counts as well, the same way your diary marks it as a rewatch or reread. If the title isn't in your library yet, add it first."},
            {"kind": "reflect", "count": 1,
             "label": "Write down what you love about one",
             "detail": "Rate one of this month's finishes or revisits, or add a line about it. A takeaway on the finish screen counts, and so does a private note when you log a revisit. Most libraries are full of scores with nothing to say what earned them, and next February the sentence is the part you will want to read again. Notes and takeaways stay private unless you publish a review."},
        ],
        "reflection": "Which of this month's love stories would you not have called a love story before you finished it?",
    },
}

# Used for any month without a curated challenge, so the dashboard card never breaks.
FALLBACK = {
    "name": "A month of small finishes",
    "tagline": "Three easy steps that fit around a normal month.",
    "published": None,
    "intro": ["Finish a few titles you are already in the middle of, try more than one format and leave a note on one of them. Anything you mark finished this month counts."],
    "steps": [
        {"kind": "total", "count": 3, "label": "Finish three titles this month",
         "detail": "Anything in your library counts."},
        {"kind": "formats", "count": 2, "label": "Finish titles in two different formats",
         "detail": "A film and an album, a book and a game: any two formats."},
        {"kind": "reflect", "count": 1, "label": "Rate it or jot a takeaway",
         "detail": "Add a rating or a one-line takeaway when you mark something finished."},
    ],
    "reflection": "",
}


# ---------------------------------------------------------------- months

def month_key(today: Optional[date] = None) -> str:
    today = today or datetime.utcnow().date()
    return f"{today.year:04d}-{today.month:02d}"


def slug_for(month: str) -> str:
    year, number = month.split("-")
    return f"{MONTH_NAMES[int(number) - 1].lower()}-{year}"


def month_for_slug(slug: str) -> Optional[str]:
    """'october-2026' -> '2026-10'; None for anything else."""
    if not isinstance(slug, str) or len(slug) > 20 or "-" not in slug:
        return None
    name, _, year = slug.rpartition("-")
    if not year.isdigit() or len(year) != 4 or name.capitalize() not in MONTH_NAMES:
        return None
    return f"{year}-{MONTH_NAMES.index(name.capitalize()) + 1:02d}"


def month_label(month: str) -> str:
    year, number = month.split("-")
    return f"{MONTH_NAMES[int(number) - 1]} {year}"


def month_bounds(month: str) -> tuple[datetime, datetime]:
    year, number = (int(part) for part in month.split("-"))
    start = datetime(year, number, 1)
    end = datetime(year + 1, 1, 1) if number == 12 else datetime(year, number + 1, 1)
    return start, end


def days_left(month: str, today: Optional[date] = None) -> int:
    today = today or datetime.utcnow().date()
    year, number = (int(part) for part in month.split("-"))
    last = date(year, number, monthrange(year, number)[1])
    return max(0, (last - today).days + 1)


def challenge_for(month: str) -> dict:
    """The curated challenge for a month, or the generic fallback."""
    return CHALLENGES.get(month, FALLBACK)


def is_curated(month: str) -> bool:
    return month in CHALLENGES


def public_months(today: Optional[date] = None) -> list[str]:
    """Curated challenges that have started, newest first. Future months stay unpublished."""
    current = month_key(today)
    return sorted((month for month in CHALLENGES if month <= current), reverse=True)


# ---------------------------------------------------------------- progress

def _finishes(db: Session, user_id: int, month: str) -> list[dict]:
    """Titles finished in the month; each title counts once, however many times it was logged."""
    start, end = month_bounds(month)
    actions = diary.DIARY_ACTIONS if challenge_for(month).get("revisits_count") else ("completed",)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(actions),
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
    ).order_by(models.ActivityEntry.occurred_at.asc(), models.ActivityEntry.id.asc()).all()
    moments = db.query(models.CompletionMoment).filter(
        models.CompletionMoment.user_id == user_id,
        models.CompletionMoment.completed_at >= start,
        models.CompletionMoment.completed_at < end,
    ).order_by(models.CompletionMoment.completed_at.asc()).all()
    finished: dict[tuple, dict] = {}
    for row, item_id, reflected in (
        *((entry, entry.item_id, entry.rating is not None or bool((entry.note or "").strip())) for entry in entries),
        *((moment, moment.item_id, moment.rating is not None or bool((moment.takeaway or "").strip())) for moment in moments),
    ):
        if row.category not in FORMAT_NOUNS:
            continue
        key = year_in_review._title_key(row.category, item_id, row.title)
        found = finished.setdefault(key, {"category": row.category, "item_id": item_id,
                                          "title": row.title or "", "reflected": False})
        found["reflected"] = found["reflected"] or reflected
        if found["item_id"] is None:
            found["item_id"] = item_id
    return list(year_in_review.fold_deleted_copies(finished).values())


def _release_years(db: Session, finishes: list[dict]) -> dict[tuple[str, int], Optional[int]]:
    """Release years of the finished titles: one query per format, not one per title.

    The card used to look each title up on its own, so a member with 100 finishes this
    month cost 100 queries on every home screen load. Years follow title_pages.item_year.
    """
    wanted: dict[str, set[int]] = {}
    for finish in finishes:
        kind = title_pages.LIBRARY_TO_KIND.get(finish["category"])
        if kind is not None and finish["item_id"] is not None:
            wanted.setdefault(kind, set()).add(finish["item_id"])
    years: dict[tuple[str, int], Optional[int]] = {}
    for kind, ids in wanted.items():
        model = title_pages.KINDS[kind][0]
        column = model.release_date if kind == "game" else getattr(model, "year", None)
        if column is None:
            continue
        ordered = sorted(ids)
        for start in range(0, len(ordered), 500):
            for item_id, value in db.query(model.id, column).filter(model.id.in_(ordered[start:start + 500])):
                if kind == "game":
                    years[(kind, item_id)] = value.year if value else None
                else:
                    years[(kind, item_id)] = value or None
    return years


def _waiting_count(db: Session, user_id: int, month: str, finishes: list[dict]) -> int:
    """Finishes of titles that were in the library before the month began: one query per format.

    A row without ``added_at`` predates the column, so it was waiting too. A title added and
    finished in the same month does not count, and neither does a finish whose row was deleted.
    """
    start, _ = month_bounds(month)
    wanted: dict[str, set[int]] = {}
    for finish in finishes:
        kind = title_pages.LIBRARY_TO_KIND.get(finish["category"])
        if kind is not None and finish["item_id"] is not None:
            wanted.setdefault(kind, set()).add(finish["item_id"])
    count = 0
    for kind, ids in wanted.items():
        model = title_pages.KINDS[kind][0]
        ordered = sorted(ids)
        for first in range(0, len(ordered), 500):
            count += db.query(func.count(model.id)).filter(
                model.user_id == user_id, model.id.in_(ordered[first:first + 500]),
                (model.added_at.is_(None)) | (model.added_at < start),
            ).scalar() or 0
    return count


def _revisit_count(db: Session, user_id: int, month: str) -> int:
    """Titles revisited in the month, counted the way the diary labels a rewatch, reread, replay or relisten.

    A journal "Revisited" entry counts, and so does a logged finish of a title that already had
    an earlier finish or revisit (diary.visit_numbers). Each title counts once however often it
    was revisited.
    """
    start, end = month_bounds(month)
    entries = db.query(models.ActivityEntry).filter(
        models.ActivityEntry.user_id == user_id,
        models.ActivityEntry.action.in_(diary.DIARY_ACTIONS),
        models.ActivityEntry.category.in_(tuple(FORMAT_NOUNS)),
        models.ActivityEntry.occurred_at >= start,
        models.ActivityEntry.occurred_at < end,
    ).all()
    if not entries:
        return 0
    visits = diary.visit_numbers(db, user_id, entries)
    return len({diary._key(entry.category, entry.title) for entry in entries
                if diary.is_repeat(entry, visits.get(entry.id, 1))})


def _edition_titles(slug: str) -> set[tuple[str, str]]:
    edition = MONTHLY_EDITIONS.get(slug) or {}
    return {(item["category"], title_pages.normalize(item["title"])) for item in edition.get("items", [])}


def _step_count(db: Session, user_id: int, step: dict, finishes: list[dict], month: str) -> tuple[int, int]:
    kind = step["kind"]
    if kind == "total":
        return len(finishes), step["count"]
    if kind == "formats":
        return len({finish["category"] for finish in finishes}), step["count"]
    if kind == "reflect":
        return sum(1 for finish in finishes if finish["reflected"]), step["count"]
    if kind == "category":
        return sum(1 for finish in finishes if finish["category"] == step["category"]), step["count"]
    if kind == "edition":
        picks = _edition_titles(step["edition"])
        return sum(1 for finish in finishes if (finish["category"], title_pages.normalize(finish["title"])) in picks), 1
    if kind == "before":
        years = _release_years(db, finishes)
        count = 0
        for finish in finishes:
            year = years.get((title_pages.LIBRARY_TO_KIND.get(finish["category"]), finish["item_id"]))
            if year and year < step["year"]:
                count += 1
        return count, 1
    if kind == "waiting":
        return _waiting_count(db, user_id, month, finishes), step.get("count", 1)
    if kind == "revisit":
        return _revisit_count(db, user_id, month), step.get("count", 1)
    return 0, 1


def progress(db: Session, user_id: int, month: str) -> list[dict]:
    finishes = _finishes(db, user_id, month)
    steps = []
    for index, step in enumerate(challenge_for(month)["steps"]):
        count, target = _step_count(db, user_id, step, finishes, month)
        steps.append({"key": f"step-{index + 1}", "kind": step["kind"], "label": step["label"],
                      "count": min(count, target), "target": target, "done": count >= target})
    return steps


# ---------------------------------------------------------------- entries

def get_entry(db: Session, user_id: int, month: str) -> Optional[models.MonthlyChallengeEntry]:
    return db.query(models.MonthlyChallengeEntry).filter_by(user_id=user_id, month=month).first()


def join(db: Session, user_id: int, month: str) -> models.MonthlyChallengeEntry:
    entry = get_entry(db, user_id, month)
    if entry is None:
        entry = models.MonthlyChallengeEntry(user_id=user_id, month=month)
        db.add(entry)
        try:
            db.commit()
        except IntegrityError:
            # A double click or second tab joined first.
            db.rollback()
            entry = get_entry(db, user_id, month)
    return entry


def leave(db: Session, user_id: int, month: str) -> bool:
    entry = get_entry(db, user_id, month)
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


def record_completed(db: Session, user: models.User, month: str, entry: models.MonthlyChallengeEntry,
                     steps: list[dict]) -> bool:
    """Mark a joined challenge complete the first time every step is done, and tell the member once."""
    if entry.completed_at is not None or not steps or not all(step["done"] for step in steps):
        return False
    # Claim completion atomically so overlapping dashboard loads notify only once.
    claimed = (db.query(models.MonthlyChallengeEntry)
               .filter(models.MonthlyChallengeEntry.id == entry.id, models.MonthlyChallengeEntry.completed_at.is_(None))
               .update({"completed_at": datetime.utcnow()}, synchronize_session=False))
    if not claimed:
        db.rollback()
        db.refresh(entry)
        return False
    db.refresh(entry)
    name = challenge_for(month)["name"]
    db.add(models.Notification(
        user_id=user.id, type="challenge_complete",
        message=f"Challenge complete: {name} ({month_label(month)}). Nicely done!",
        link="/#challenge",
    ))
    db.commit()
    return True


def completion_payload(entry: Optional[models.MonthlyChallengeEntry]) -> Optional[dict]:
    if entry is None or entry.completed_at is None:
        return None
    return {
        "completed_at": entry.completed_at.isoformat(),
        "celebrate": entry.seen_at is None,
        "shared": bool(entry.share_token),
        "url": SITE_URL + share_path(entry) if entry.share_token else None,
    }


def mark_seen(db: Session, entry: models.MonthlyChallengeEntry) -> None:
    entry.seen_at = entry.seen_at or datetime.utcnow()
    db.commit()


def share(db: Session, entry: models.MonthlyChallengeEntry) -> models.MonthlyChallengeEntry:
    if not entry.share_token:
        entry.share_token = secrets.token_urlsafe(12)
    entry.seen_at = entry.seen_at or datetime.utcnow()
    db.commit()
    return entry


def unshare(db: Session, entry: models.MonthlyChallengeEntry) -> models.MonthlyChallengeEntry:
    entry.share_token = None
    db.commit()
    return entry


def share_path(entry: models.MonthlyChallengeEntry) -> str:
    return f"/challenge/{entry.share_token}"


def find_shared(db: Session, token: str) -> Optional[models.MonthlyChallengeEntry]:
    """A shared, completed entry whose owner is still active; otherwise None."""
    if not token or len(token) > 32:
        return None
    entry = db.query(models.MonthlyChallengeEntry).filter(models.MonthlyChallengeEntry.share_token == token).first()
    if entry is None or entry.completed_at is None:
        return None
    owner = db.get(models.User, entry.user_id)
    if owner is None or not owner.is_active:
        return None
    return entry


def headline(username: str, month: str) -> str:
    """'Sam completed the October 2026 challenge'."""
    return f"{username} completed the {month_label(month)} challenge"


def public_counts(db: Session, month: str) -> dict:
    """Members who took and completed the challenge, or None for counts too small to show."""
    joined, completed = db.query(
        func.count(models.MonthlyChallengeEntry.id),
        func.count(models.MonthlyChallengeEntry.completed_at),
    ).join(models.User, models.User.id == models.MonthlyChallengeEntry.user_id).filter(
        models.MonthlyChallengeEntry.month == month, models.User.is_active == True,  # noqa: E712
    ).one()
    return {
        "joined": int(joined or 0) if (joined or 0) >= MIN_PUBLIC_COUNT else None,
        "completed": int(completed or 0) if (completed or 0) >= MIN_PUBLIC_COUNT else None,
    }


def payload(db: Session, user: models.User, today: Optional[date] = None) -> dict:
    """The current month's challenge for the dashboard card."""
    today = today or datetime.utcnow().date()
    month = month_key(today)
    challenge = challenge_for(month)
    steps = progress(db, user.id, month)
    entry = get_entry(db, user.id, month)
    if entry is not None:
        try:
            record_completed(db, user, month, entry, steps)
        except Exception:
            db.rollback()  # The card never depends on it.
    edition = challenge.get("edition")
    return {
        "month": month,
        "label": month_label(month),
        "month_name": MONTH_NAMES[today.month - 1],
        "name": challenge["name"],
        "tagline": challenge["tagline"],
        "url": f"/challenges/{slug_for(month)}" if is_curated(month) else None,
        "edition_url": f"/discover/monthly/{edition}" if edition in published_editions() else None,
        "days_left": days_left(month, today),
        "joined": entry is not None,
        "steps": steps,
        "done_steps": sum(1 for step in steps if step["done"]),
        "complete": bool(steps) and all(step["done"] for step in steps),
        "completion": completion_payload(entry),
    }
