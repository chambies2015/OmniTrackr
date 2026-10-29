"""The public binge calculator at /binge-calculator.

Worked examples are hand-checked totals for long series. Episode counts are for
the complete regular run (no specials or films); book lengths are word counts
turned into pages at ``WORDS_PER_PAGE``. A visitor can also look up a title
members track, in which case the lengths come from the shared title cache only
(nothing is fetched from outside on a visitor's request).
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy.orm import Session

from . import episodes, title_metadata, title_pages, time_spent

BASE_PATH = "/binge-calculator"
WORDS_PER_PAGE = 300
PAGES_PER_HOUR = round(60 / time_spent.MINUTES_PER_PAGE)
LOOKUP_KINDS = {"tv": "tv-shows", "anime": "anime", "book": "books"}
EXAMPLE_PACES = (1, 2, 4)  # hours a day shown in the worked examples

# slug -> example. Screen lengths are typical episode lengths without ads.
EXAMPLES = {
    "breaking-bad": {"name": "Breaking Bad", "kind": "tv", "episodes": 62, "minutes": 47,
                     "note": "Five seasons. The final season aired in two halves, both counted here."},
    "better-call-saul": {"name": "Better Call Saul", "kind": "tv", "episodes": 63, "minutes": 46,
                         "note": "Six seasons, set mostly before Breaking Bad."},
    "the-sopranos": {"name": "The Sopranos", "kind": "tv", "episodes": 86, "minutes": 55,
                     "note": "Six seasons, the last one split into two parts."},
    "the-wire": {"name": "The Wire", "kind": "tv", "episodes": 60, "minutes": 58,
                 "note": "Five seasons, each one following a different part of Baltimore."},
    "game-of-thrones": {"name": "Game of Thrones", "kind": "tv", "episodes": 73, "minutes": 57,
                        "note": "Eight seasons. Later episodes run longer, so this is a little on the low side."},
    "mad-men": {"name": "Mad Men", "kind": "tv", "episodes": 92, "minutes": 47, "note": "Seven seasons."},
    "lost": {"name": "Lost", "kind": "tv", "episodes": 121, "minutes": 43,
             "note": "Six seasons. A long one, but the episodes are short without ads."},
    "friends": {"name": "Friends", "kind": "tv", "episodes": 236, "minutes": 22,
                "note": "Ten seasons of half-hour episodes."},
    "the-office": {"name": "The Office (US)", "kind": "tv", "episodes": 201, "minutes": 22,
                   "note": "Nine seasons."},
    "supernatural": {"name": "Supernatural", "kind": "tv", "episodes": 327, "minutes": 42,
                     "note": "Fifteen seasons, one of the longest runs on this list."},
    "fullmetal-alchemist-brotherhood": {"name": "Fullmetal Alchemist: Brotherhood", "kind": "anime", "episodes": 64,
                                        "minutes": 24, "note": "One continuous series, about five cours."},
    "death-note": {"name": "Death Note", "kind": "anime", "episodes": 37, "minutes": 23,
                   "note": "Short enough for a long weekend at four hours a day."},
    "cowboy-bebop": {"name": "Cowboy Bebop", "kind": "anime", "episodes": 26, "minutes": 24,
                     "note": "The film is not counted."},
    "hunter-x-hunter-2011": {"name": "Hunter x Hunter (2011)", "kind": "anime", "episodes": 148, "minutes": 23,
                             "note": "The 2011 adaptation, start to finish."},
    "dragon-ball-z": {"name": "Dragon Ball Z", "kind": "anime", "episodes": 291, "minutes": 24,
                      "note": "The original broadcast run, not Kai."},
    "naruto-and-shippuden": {"name": "Naruto and Naruto Shippuden", "kind": "anime", "episodes": 720, "minutes": 23,
                             "note": "220 plus 500 episodes, filler included. Skipping the filler cuts it down a lot."},
    "harry-potter": {"name": "Harry Potter (all seven books)", "kind": "book", "words": 1084000,
                     "note": "About 1.08 million words across the series."},
    "the-lord-of-the-rings": {"name": "The Lord of the Rings", "kind": "book", "words": 480000,
                              "note": "The three volumes with their appendices, not counting The Hobbit."},
    "a-song-of-ice-and-fire": {"name": "A Song of Ice and Fire (five books)", "kind": "book", "words": 1770000,
                               "note": "The five published novels."},
    "the-wheel-of-time": {"name": "The Wheel of Time", "kind": "book", "words": 4400000,
                          "note": "Fourteen novels and the prequel, about 4.4 million words."},
    "dune": {"name": "Dune", "kind": "book", "words": 188000, "note": "The first novel only."},
}


def example_minutes(example: dict) -> float:
    if example["kind"] == "book":
        return example["words"] / WORDS_PER_PAGE * time_spent.MINUTES_PER_PAGE
    return example["episodes"] * example["minutes"]


def example_pages(example: dict) -> Optional[int]:
    return round(example["words"] / WORDS_PER_PAGE) if example["kind"] == "book" else None


def days_at(minutes: float, hours_per_day: float) -> int:
    return int(-(-minutes // (hours_per_day * 60)))


def lookup(db: Session, kind: str, title: str, year: Optional[int]) -> dict:
    """Lengths for a title from the shared cache. Missing numbers come back as None."""
    category = LOOKUP_KINDS[kind]
    key = title_metadata.cache_key(kind, title_pages.normalize(title), year)
    data, _ = title_metadata.cached(db, key)
    facts = time_spent._facts(data)
    result = {"kind": kind, "title": title, "year": year, "episodes": None, "minutes": None, "pages": None}
    if kind in ("tv", "anime"):
        layout = episodes.cached_layouts(db, [episodes.layout_key(category, title, year)])
        seasons = next(iter(layout.values()), [])
        result["episodes"] = sum(entry["episodes"] for entry in seasons) or time_spent.parse_count(facts.get("Episodes"))
        minutes = time_spent.parse_minutes(facts.get("Episode length"))
        result["minutes"] = round(minutes) if minutes else None
    else:
        result["pages"] = time_spent.parse_count(facts.get("Pages"))
    return result
