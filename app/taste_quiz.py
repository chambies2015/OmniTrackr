"""Taste quiz (/taste-quiz): a one-minute deck of well-known titles for new members.

A new member (or a visitor) taps through the deck, marking each title Loved it,
Liked it, Not for me, Want to, or Haven't seen. Their answers become library
entries, and the deck's links to the editors' "If you liked" guides and the
Pick for me pool turn them into a handful of suggestions with a reason each.

Nothing here reads anyone else's library. Visitors keep their answers in their
browser (taste-quiz.js) until their first log-in, when POST /api/taste-quiz/save
moves them into the new library. A title the member already has is never changed.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from . import if_you_liked, pick, title_metadata, title_pages

KINDS = ("movie", "tv", "anime", "game")
FORMAT_LABELS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games"}
# answer -> (finished, rating out of 10). Want to is saved as not started, with no rating.
ANSWERS = {"loved": (True, 9.0), "liked": (True, 7.0), "meh": (True, 4.0), "want": (False, None)}
ANSWER_WEIGHT = {"loved": 3.0, "liked": 2.0, "want": 1.0, "meh": -2.0}
SUGGESTION_LIMIT = 6

# Interleaved so the first few cards cover every format. "guide" is the slug of an
# "If you liked" guide about the title; "next" lists Pick for me pool ids for titles
# without a guide (tests check that every id exists).
DECK = (
    {"kind": "movie", "title": "Interstellar", "year": 2014, "creator": "Christopher Nolan", "guide": "interstellar"},
    {"kind": "tv", "title": "Stranger Things", "year": 2016, "guide": "stranger-things"},
    {"kind": "anime", "title": "Attack on Titan", "year": 2013, "guide": "attack-on-titan"},
    {"kind": "game", "title": "Minecraft", "year": 2011,
     "next": ("game/stardew-valley-2016", "game/animal-crossing-new-horizons-2020", "game/dorfromantik-2022", "game/unpacking-2021")},
    {"kind": "movie", "title": "The Dark Knight", "year": 2008, "creator": "Christopher Nolan", "guide": "the-dark-knight"},
    {"kind": "tv", "title": "Breaking Bad", "year": 2008, "guide": "breaking-bad"},
    {"kind": "anime", "title": "Spirited Away", "year": 2001,
     "next": ("anime/kiki-s-delivery-service-1989", "anime/the-tale-of-the-princess-kaguya-2013", "anime/wolf-children-2012", "game/spiritfarer-2020")},
    {"kind": "game", "title": "The Legend of Zelda: Breath of the Wild", "year": 2017,
     "next": ("game/the-legend-of-zelda-the-wind-waker-2002", "game/a-short-hike-2019", "game/outer-wilds-2019", "anime/frieren-beyond-journey-s-end-2023")},
    {"kind": "movie", "title": "Spider-Man: Into the Spider-Verse", "year": 2018, "creator": "Bob Persichetti, Peter Ramsey, Rodney Rothman",
     "next": ("anime/cyberpunk-edgerunners-2022", "tv/the-legend-of-korra-2012", "movie/everything-everywhere-all-at-once-2022", "tv/avatar-the-last-airbender-2005")},
    {"kind": "tv", "title": "The Last of Us", "year": 2023, "guide": "the-last-of-us"},
    {"kind": "anime", "title": "Jujutsu Kaisen", "year": 2020, "guide": "jujutsu-kaisen"},
    {"kind": "game", "title": "Stardew Valley", "year": 2016,
     "next": ("game/animal-crossing-new-horizons-2020", "game/spiritfarer-2020", "anime/laid-back-camp-2018", "game/a-short-hike-2019")},
    {"kind": "movie", "title": "Dune", "year": 2021, "creator": "Denis Villeneuve", "guide": "dune"},
    {"kind": "tv", "title": "Arcane", "year": 2021, "guide": "arcane"},
    {"kind": "anime", "title": "One Piece", "year": 1999, "guide": "one-piece"},
    {"kind": "game", "title": "Elden Ring", "year": 2022,
     "next": ("game/shadow-of-the-colossus-2005", "anime/vinland-saga-2019", "game/celeste-2018", "game/outer-wilds-2019")},
    {"kind": "movie", "title": "Inception", "year": 2010, "creator": "Christopher Nolan",
     "next": ("movie/primer-2004", "movie/eternal-sunshine-of-the-spotless-mind-2004", "game/control-2019", "tv/dark-2017")},
    {"kind": "tv", "title": "Severance", "year": 2022, "guide": "severance"},
    {"kind": "anime", "title": "Death Note", "year": 2006,
     "next": ("anime/monster-2004", "anime/code-geass-lelouch-of-the-rebellion-2006", "anime/the-promised-neverland-2019", "movie/zodiac-2007")},
    {"kind": "game", "title": "Hades", "year": 2020,
     "next": ("game/celeste-2018", "game/inscryption-2021", "game/devil-may-cry-5-2019", "game/dishonored-2012")},
    {"kind": "movie", "title": "Everything Everywhere All at Once", "year": 2022, "creator": "Daniel Kwan, Daniel Scheinert",
     "next": ("movie/hunt-for-the-wilderpeople-2016", "tv/the-good-place-2016", "anime/mob-psycho-100-2016", "movie/spider-man-into-the-spider-verse-2018")},
    {"kind": "tv", "title": "Avatar: The Last Airbender", "year": 2005,
     "next": ("tv/the-legend-of-korra-2012", "anime/fullmetal-alchemist-brotherhood-2009", "tv/over-the-garden-wall-2014", "game/the-legend-of-zelda-the-wind-waker-2002")},
    {"kind": "anime", "title": "Frieren: Beyond Journey's End", "year": 2023, "guide": "frieren"},
    {"kind": "game", "title": "Red Dead Redemption 2", "year": 2018,
     "next": ("movie/hell-or-high-water-2016", "movie/no-country-for-old-men-2007", "tv/fargo-2014", "game/the-last-of-us-2013")},
)


def card_id(card: dict) -> str:
    return f"{card['kind']}/{title_pages.title_slug(card['title'], card['year'])}"


def _cards() -> dict[str, dict]:
    return {card_id(card): card for card in DECK}


CARDS = _cards()


def find(card_id_value: str) -> Optional[dict]:
    return CARDS.get(card_id_value)


def _identity(kind: str, title: str) -> tuple[str, str]:
    return kind, title_pages.slugify(title)


# ---------------------------------------------------------------- artwork

def _art_index(index: list[dict]) -> dict[tuple[str, str], dict]:
    best: dict[tuple[str, str], dict] = {}
    for entry in index:
        if not entry.get("image"):
            continue
        key = (entry["kind"], entry["base"])
        current = best.get(key)
        if current is None or entry["members"] > current["members"]:
            best[key] = entry
    return best


def cached_art(db: Session, card: dict, art: Optional[dict] = None) -> Optional[str]:
    """Artwork already on the site: a member's cover for the title, then cached title metadata. Never fetches."""
    match = (art or {}).get(_identity(card["kind"], card["title"]))
    if match:
        return match["image"]
    try:
        data, _ = title_metadata.cached(db, title_metadata.cache_key(card["kind"], title_pages.normalize(card["title"]), card["year"]))
    except Exception:
        db.rollback()
        return None
    return title_pages._safe_image((data or {}).get("poster"))


def deck(db: Session, index: list[dict]) -> list[dict]:
    """The quiz cards with whatever artwork is already cached."""
    art = _art_index(index)
    cards = []
    for card in DECK:
        guide = if_you_liked.guide(card["guide"]) if card.get("guide") else None
        cards.append({
            "id": card_id(card), "kind": card["kind"], "label": title_pages.KINDS[card["kind"]][3],
            "title": card["title"], "year": card["year"], "creator": card.get("creator"),
            "image": cached_art(db, card, art),
            "guide": if_you_liked.path(card["guide"]) if guide else None,
        })
    return cards


# ---------------------------------------------------------------- suggestions

def _sources(card: dict) -> list[dict]:
    """Pick for me entries the card leads to, best match first."""
    entries = []
    if card.get("guide"):
        guide = if_you_liked.guide(card["guide"])
        for item in (guide or {}).get("picks", []):
            entry = if_you_liked.pool_entry(item)
            if entry is not None:
                entries.append(entry)
    for pick_id in card.get("next", ()):
        entry = pick.find_id(pick_id)
        if entry is not None:
            entries.append(entry)
    return entries


def suggestions(answers: Iterable[tuple[str, str]], owned: Iterable[tuple[str, str]] = (),
                kinds: Optional[Iterable[str]] = None, limit: int = SUGGESTION_LIMIT) -> list[dict]:
    """Ranked picks from (card id, answer) pairs.

    owned holds (kind, slugified title) pairs the person already has or answered;
    those are never suggested. Loved and liked titles pull their picks up, a "Not
    for me" pushes its picks down, and picks in formats the person rated well get a
    small lift. Only picks with a positive score are returned.
    """
    answered = [(CARDS[cid], answer) for cid, answer in answers if cid in CARDS and answer in ANSWER_WEIGHT]
    skip = set(owned) | {_identity(card["kind"], card["title"]) for card, _ in answered}
    allowed = set(kinds) if kinds else None
    format_lift: dict[str, float] = defaultdict(float)
    for card, answer in answered:
        if answer in ("loved", "liked"):
            format_lift[card["kind"]] += 0.25
    scores: dict[str, float] = defaultdict(float)
    because: dict[str, tuple[float, dict]] = {}
    entries: dict[str, dict] = {}
    for card, answer in answered:
        weight = ANSWER_WEIGHT[answer]
        for rank, entry in enumerate(_sources(card)):
            if _identity(entry["kind"], entry["title"]) in skip:
                continue
            # The guide's first picks are its closest matches.
            share = weight * (1.0 - min(rank, 6) * 0.06)
            scores[entry["id"]] += share
            entries[entry["id"]] = entry
            if share > 0 and (entry["id"] not in because or share > because[entry["id"]][0]):
                because[entry["id"]] = (share, card)
    ranked = []
    for entry_id, score in scores.items():
        entry = entries[entry_id]
        if entry_id not in because or score <= 0:
            continue
        if allowed is not None and entry["kind"] not in allowed and entry["kind"] in KINDS:
            score -= 0.5
        score += min(format_lift.get(entry["kind"], 0.0), 1.0)
        ranked.append((score, entry, because[entry_id][1]))
    ranked.sort(key=lambda row: (-row[0], row[1]["title"].casefold()))
    # Keep the list varied: at most two picks inspired by the same title and half the list from one format.
    chosen, per_source, per_kind = [], defaultdict(int), defaultdict(int)
    for score, entry, source in ranked:
        if per_source[card_id(source)] >= 2 or per_kind[entry["kind"]] >= max(2, limit // 2):
            continue
        per_source[card_id(source)] += 1
        per_kind[entry["kind"]] += 1
        chosen.append({
            "id": entry["id"], "kind": entry["kind"], "slug": entry["slug"], "label": entry["label"],
            "title": entry["title"], "year": entry["year"], "creator": entry["creator"],
            "why": entry["why"], "caveat": entry["caveat"],
            "because": source["title"],
            "because_answer": next(answer for card, answer in answered if card is source),
            "guide": if_you_liked.path(source["guide"]) if source.get("guide") else None,
        })
        if len(chosen) >= limit:
            break
    return chosen


def owned_identities(db: Session, user_id: int) -> set[tuple[str, str]]:
    """(kind, slugified title) for everything in the member's library, all six formats."""
    owned = set()
    for kind, (model, *_rest) in title_pages.KINDS.items():
        for title, in db.query(model.title).filter(model.user_id == user_id).all():
            if title:
                owned.add(_identity(kind, title))
    return owned


# ---------------------------------------------------------------- saving

def save_answers(db: Session, user, answers: Iterable[tuple[str, str]], art: Optional[dict] = None) -> dict:
    """Add answered titles to the member's library. Does not commit.

    A title the member already has (same name, any case) is left exactly as it is,
    rating and status included. Haven't seen answers are never sent here.
    """
    added, existing = [], []
    seen = set()
    for cid, answer in answers:
        card = CARDS.get(cid)
        if card is None or answer not in ANSWERS or cid in seen:
            continue
        seen.add(cid)
        image = cached_art(db, card, art)
        state, record = pick.add_to_library(db, user, card, image)
        entry = {"id": cid, "title": record.title, "category": title_pages.KINDS[card["kind"]][2], "answer": answer}
        if state == "created":
            finished, rating = ANSWERS[answer]
            setattr(record, title_pages.COMPLETE_FIELD[card["kind"]], finished)
            record.rating = rating
            added.append(entry)
        else:
            existing.append(entry)
    return {"added": added, "existing": existing}
