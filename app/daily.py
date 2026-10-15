"""OmniTrackr Daily (/daily): one title a day to guess from six clues.

Everyone gets the same puzzle on the same day; a new one starts at midnight US
Eastern time. Puzzle #1 is EPOCH. The answer for today's puzzle never appears in
a page or a response until the player has solved it or used all six guesses;
earlier puzzles have public archive pages with the answer and the editors' note.

Nothing about a player is stored on the server. Guesses, streaks and results
live in the player's browser; checking a guess is a stateless request.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional

from . import title_pages
from .daily_puzzles import PUZZLES

EPOCH = date(2026, 10, 15)
MAX_GUESSES = 6
GUESS_MAX_CHARS = 120
KIND_ARTICLE = {"movie": "a movie", "tv": "a TV show", "anime": "an anime", "game": "a video game",
                "book": "a book", "album": "an album"}
KIND_EMOJI = {"movie": "🎬", "tv": "📺", "anime": "🌸", "game": "🎮", "book": "📚", "album": "🎵"}
_LEADING_ARTICLE = re.compile(r"^(the|a|an) ")

try:
    from zoneinfo import ZoneInfo
    _ZONE = ZoneInfo("America/New_York")
except Exception:  # No tz database: fall back to US Eastern standard time.
    _ZONE = timezone(timedelta(hours=-5))


def now_local(now: Optional[datetime] = None) -> datetime:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(_ZONE)


def today_number(now: Optional[datetime] = None) -> int:
    """Today's puzzle number (1 on EPOCH). 0 before launch."""
    return max(0, (now_local(now).date() - EPOCH).days + 1)


def seconds_to_next(now: Optional[datetime] = None) -> int:
    local = now_local(now)
    tomorrow = datetime.combine(local.date() + timedelta(days=1), time(0), tzinfo=_ZONE)
    # Compare in UTC: same-zone subtraction ignores a daylight saving change that night.
    return max(1, int((tomorrow.astimezone(timezone.utc) - local.astimezone(timezone.utc)).total_seconds()))


def date_for(number: int) -> date:
    return EPOCH + timedelta(days=number - 1)


def bank_index(number: int) -> int:
    """The bank repeats once every puzzle has been used; the first use stays the canonical page."""
    return (number - 1) % len(PUZZLES)


def canonical_number(number: int) -> int:
    return bank_index(number) + 1


def puzzle(number: int) -> dict:
    return PUZZLES[bank_index(number)]


def published(number: int, now: Optional[datetime] = None) -> bool:
    return 1 <= number <= today_number(now)


def archive_numbers(now: Optional[datetime] = None) -> list[int]:
    """Finished puzzles with their own archive page, newest first (repeats of the bank are left out)."""
    last = min(today_number(now) - 1, len(PUZZLES))
    return list(range(last, 0, -1))


def answer_id(entry: dict) -> str:
    return f"{entry['kind']}/{title_pages.title_slug(entry['title'], entry['year'])}"


def find_answer(kind: str, slug: str, now: Optional[datetime] = None) -> Optional[dict]:
    """A published puzzle's answer by kind and title slug (for saving it to a library or guest list)."""
    count = min(today_number(now), len(PUZZLES))
    for entry in PUZZLES[:count]:
        if entry["kind"] == kind and title_pages.title_slug(entry["title"], entry["year"]) == slug:
            return entry
    return None


def find_answer_id(value: str, now: Optional[datetime] = None) -> Optional[dict]:
    kind, _, slug = (value or "").partition("/")
    return find_answer(kind, slug, now) if kind in title_pages.KINDS else None


# ---------------------------------------------------------------- guesses

def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode("ascii").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return _LEADING_ARTICLE.sub("", text)


def _forms(text: str) -> set[str]:
    spaced = normalize(text)
    return {spaced, spaced.replace(" ", "")} - {""}


def accepted(entry: dict) -> set[str]:
    forms = set()
    for name in (entry["title"],) + tuple(entry["aliases"]):
        forms |= _forms(name)
    return forms


def is_correct(entry: dict, guess: str) -> bool:
    return bool(_forms(guess) & accepted(entry))


def answer_payload(entry: dict, number: int) -> dict:
    return {
        "id": answer_id(entry), "kind": entry["kind"], "slug": answer_id(entry).split("/", 1)[1],
        "title": entry["title"], "year": entry["year"], "creator": entry["creator"],
        "label": title_pages.KINDS[entry["kind"]][3], "note": entry["note"],
        "clues": list(entry["clues"]), "archive_url": f"/daily/{canonical_number(number)}",
    }


def check(number: int, guess: str, attempt: int) -> dict:
    """Score one guess. `attempt` is how many guesses (or skips) came before this one.

    A wrong guess returns the next clue; the answer is returned only when the
    guess is right or it was the last one. An empty guess is a skip.
    """
    entry = puzzle(number)
    guess = (guess or "").strip()[:GUESS_MAX_CHARS]
    correct = bool(guess) and is_correct(entry, guess)
    done = correct or attempt >= MAX_GUESSES - 1
    result = {"number": number, "correct": correct, "done": done, "attempt": attempt + 1}
    if done:
        result["answer"] = answer_payload(entry, number)
    else:
        result["clue"] = entry["clues"][attempt + 1]
    return result


def public_view(number: int, now: Optional[datetime] = None) -> dict:
    """What a player may see before guessing: everything except the answer and later clues."""
    entry = puzzle(number)
    return {"number": number, "date": date_for(number).isoformat(), "kind": entry["kind"],
            "kind_label": KIND_ARTICLE[entry["kind"]], "emoji": KIND_EMOJI[entry["kind"]],
            "first_clue": entry["clues"][0], "max_guesses": MAX_GUESSES,
            "is_today": number == today_number(now)}
