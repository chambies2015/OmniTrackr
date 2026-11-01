"""Compare tastes with a member through their link at /u/<name>/match.

Taste Match (taste_match.py) lines up two friends' libraries. This is the open
version a member shares with anyone: "How does your taste compare with mine?"

- Nothing is reachable until the member has a public profile *and* switches
  "Let people compare tastes with me" on (off by default, existing profiles too).
- Categories the member marked private are never read, counted or listed.
- A visitor rates a short deck of the member's rated titles (Loved it, Liked it,
  Not for me, Haven't seen). The deck itself never carries the member's ratings;
  they only come back with the result.
- Visitors' answers are not stored. They stay in the visitor's browser and move
  into their library after sign-up, like the taste quiz. Members' answers go
  straight into their library as finished, rated titles (or "Want to").
- Only titles, years, creators, artwork and ratings are shown; never reviews or notes.
"""
from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Iterable, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, load_only

from . import models, public_profiles
from .for_you import _shareable_ids
from .taste_match import (CREATOR_FIELD, DONE_FIELD, IMAGE_FIELD, ITEM_LABELS, LIBRARY, LOVED, _safe_image, _year,
                          copy_payload, normalize_title, shared_categories, tier)

DECK_SIZE = 12
MIN_DECK = 5              # rated titles the member needs before their link works
MIN_ANSWERS = 3           # titles a visitor rates before a score is shown
CANDIDATES = 400          # rated titles per category looked at when building the deck
PICKS_LIMIT = 6
# A visitor's answer as a rating out of 10 (same scale as the taste quiz).
ANSWER_RATING = {"loved": 9.0, "liked": 7.0, "meh": 4.0}
ANSWER_LABELS = {"loved": "Loved it", "liked": "Liked it", "meh": "Not for me", "want": "Want to"}
FULL_MISS = 5.0
CACHE_SECONDS = 600


def _bucket(rating: float) -> float:
    """The member's rating on the visitor's three-step scale, so "Loved it" against a 9 or a 10 is full agreement."""
    if rating >= LOVED:
        return ANSWER_RATING["loved"]
    if rating >= 6:
        return ANSWER_RATING["liked"]
    return ANSWER_RATING["meh"]


def agreement(answer: str, rating: float) -> float:
    return max(0.0, 1 - abs(ANSWER_RATING[answer] - _bucket(rating)) / FULL_MISS)


# ---------------------------------------------------------------- availability

def link_profile(db: Session, user: Optional[models.User]) -> Optional[models.PublicProfile]:
    """The member's profile when their compare link is switched on, else None."""
    profile = public_profiles.visible_profile(db, user)
    return profile if profile is not None and profile.show_taste_match else None


def link_path(user: models.User) -> str:
    return public_profiles.profile_path(user) + "/match"


# ---------------------------------------------------------------- the deck

class _DeckCache:
    """Recently built decks, so a shared link opened by many people costs one set of queries."""

    def __init__(self, size: int = 256):
        self.size = size
        self._items: OrderedDict = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            hit = self._items.get(key)
            if hit is None or time.monotonic() - hit[0] > CACHE_SECONDS:
                return None
            self._items.move_to_end(key)
            return hit[1]

    def put(self, key, value):
        with self._lock:
            self._items[key] = (time.monotonic(), value)
            self._items.move_to_end(key)
            while len(self._items) > self.size:
                self._items.popitem(last=False)

    def clear(self):
        with self._lock:
            self._items.clear()


DECK_CACHE = _DeckCache()


def _columns(category: str) -> list:
    model = LIBRARY[category][0]
    names = {"id", "user_id", "title", "rating", IMAGE_FIELD[category],
             "release_date" if category == "video-games" else "year"}
    if CREATOR_FIELD.get(category):
        names.add(CREATOR_FIELD[category])
    return [getattr(model, name) for name in sorted(names)]


def _card(category: str, entry) -> dict:
    creator_field = CREATOR_FIELD.get(category)
    return {
        "id": f"{category}:{entry.id}",
        "category": category,
        "label": ITEM_LABELS[category],
        "title": (entry.title or "").strip(),
        "year": _year(category, entry),
        "creator": (getattr(entry, creator_field, None) or None) if creator_field else None,
        "image": _safe_image(getattr(entry, IMAGE_FIELD[category], None)),
    }


def _popularity(db: Session, category: str, titles: list[str], owner_id: int) -> dict[str, int]:
    """How many other members (with the category shared) track each title. Used only to order the deck."""
    model = LIBRARY[category][0]
    column = func.lower(func.trim(model.title))
    counts: dict[str, int] = {}
    keys = sorted({title.strip().lower() for title in titles if title})
    for start in range(0, len(keys), 500):
        chunk = keys[start:start + 500]
        rows = (db.query(column, func.count(func.distinct(model.user_id)))
                .filter(column.in_(chunk), model.user_id != owner_id, model.user_id.in_(_shareable_ids(db, category)))
                .group_by(column).all())
        counts.update({key: count for key, count in rows})
    return counts


def _rated(db: Session, owner: models.User, categories: Iterable[str]) -> list[tuple[str, object]]:
    rows = []
    for category in categories:
        model = LIBRARY[category][0]
        rows.extend((category, entry) for entry in (
            db.query(model).options(load_only(*_columns(category)))
            .filter(model.user_id == owner.id, model.rating.isnot(None))
            .order_by(model.rating.desc(), model.id).limit(CANDIDATES)))
    return rows


def _build_deck(db: Session, owner: models.User) -> list[dict]:
    categories = shared_categories(owner)
    rated = _rated(db, owner, categories)
    popular: dict[str, dict[str, int]] = {}
    for category in categories:
        titles = [entry.title for cat, entry in rated if cat == category]
        if titles:
            popular[category] = _popularity(db, category, titles, owner.id)
    seen, candidates = set(), []
    for category, entry in rated:
        key = (category, normalize_title(entry.title))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        reach = popular.get(category, {}).get((entry.title or "").strip().lower(), 0)
        has_art = bool(_safe_image(getattr(entry, IMAGE_FIELD[category], None)))
        candidates.append((category, entry, reach, has_art))
    # Titles other people know first, then ones with artwork, then the member's own order.
    order = lambda row: (-row[2], not row[3], row[1].title.casefold())
    loved = sorted((row for row in candidates if row[1].rating >= LOVED), key=order)
    rest = sorted((row for row in candidates if row[1].rating < LOVED), key=order)
    # Mostly favorites, with a few lower ratings so a match can disagree too.
    lower = rest[:max(DECK_SIZE // 3, DECK_SIZE - len(loved))]
    chosen = loved[:DECK_SIZE - len(lower)] + lower
    chosen = (chosen + [row for row in rest if row not in chosen])[:DECK_SIZE]
    # Interleave formats so the deck doesn't open with six movies in a row.
    by_category: dict[str, list] = OrderedDict()
    for row in sorted(chosen, key=order):
        by_category.setdefault(row[0], []).append(row)
    deck = []
    while any(by_category.values()):
        for rows in by_category.values():
            if rows:
                deck.append(_card(rows[0][0], rows.pop(0)[1]))
    return deck


def deck(db: Session, owner: models.User) -> list[dict]:
    """Up to DECK_SIZE of the member's rated titles from shared categories, without their ratings."""
    key = (owner.id, tuple(shared_categories(owner)))
    cards = DECK_CACHE.get(key)
    if cards is None:
        cards = _build_deck(db, owner)
        DECK_CACHE.put(key, cards)
    return [dict(card) for card in cards]


def deck_for_member(db: Session, owner: models.User, viewer: models.User) -> list[dict]:
    """The deck without titles the member already has (they're compared from the library instead)."""
    cards = deck(db, owner)
    owned: dict[str, set] = {}
    for category in {card["category"] for card in cards}:
        model = LIBRARY[category][0]
        owned[category] = {normalize_title(title) for (title,) in
                           db.query(model.title).filter(model.user_id == viewer.id)}
    return [card for card in cards if normalize_title(card["title"]) not in owned.get(card["category"], set())]


# ---------------------------------------------------------------- answers

def _entries(db: Session, owner: models.User, ids: Iterable[str]) -> dict[str, tuple[str, object]]:
    """The member's entries for answered card ids, only from categories they share."""
    allowed = set(shared_categories(owner))
    wanted: dict[str, set[int]] = {}
    for card_id in ids:
        category, _, raw = str(card_id).partition(":")
        if category in allowed and raw.isdigit() and len(raw) <= 10:
            wanted.setdefault(category, set()).add(int(raw))
    found = {}
    for category, entry_ids in wanted.items():
        model = LIBRARY[category][0]
        for entry in db.query(model).filter(model.user_id == owner.id, model.id.in_(sorted(entry_ids))):
            found[f"{category}:{entry.id}"] = (category, entry)
    return found


def _public(category: str, entry, **extra) -> dict:
    data = _card(category, entry)
    data.pop("id")
    data.update(extra)
    return data


def _their_favorites(db: Session, owner: models.User, skip: set, limit: int) -> list[dict]:
    """The member's highest-rated titles outside the deck, for "try next"."""
    picks = []
    for category, entry in _rated(db, owner, shared_categories(owner)):
        if entry.rating < LOVED or (category, normalize_title(entry.title)) in skip:
            continue
        picks.append((category, entry))
    picks.sort(key=lambda row: (-row[1].rating, row[1].title.casefold()))
    seen, result = set(), []
    for category, entry in picks:
        key = (category, normalize_title(entry.title))
        if key in seen:
            continue
        seen.add(key)
        result.append(_public(category, entry, their_rating=entry.rating))
        if len(result) >= limit:
            break
    return result


def guess(db: Session, owner: models.User, answers: list[tuple[str, str]]) -> dict:
    """Score a visitor's deck answers against the member's ratings. Nothing is stored."""
    entries = _entries(db, owner, [card_id for card_id, _ in answers])
    rated, try_next, seen_keys = [], [], set()
    for card_id, answer in answers:
        hit = entries.get(card_id)
        if hit is None:
            continue
        category, entry = hit
        seen_keys.add((category, normalize_title(entry.title)))
        if answer in ANSWER_RATING and entry.rating is not None:
            rated.append((category, entry, answer))
        elif entry.rating is not None and entry.rating >= LOVED:
            try_next.append(_public(category, entry, their_rating=entry.rating, your_answer=answer))
    score = None
    if len(rated) >= MIN_ANSWERS:
        score = round(sum(agreement(answer, entry.rating) for _, entry, answer in rated) / len(rated) * 100)
    agreed = [(c, e, a) for c, e, a in rated if agreement(a, e.rating) >= 0.99]
    agreed.sort(key=lambda row: (-row[1].rating, row[1].title.casefold()))
    apart = [(c, e, a) for c, e, a in rated if agreement(a, e.rating) <= 0.4]
    apart.sort(key=lambda row: (agreement(row[2], row[1].rating), row[1].title.casefold()))
    row = lambda c, e, a: _public(c, e, their_rating=e.rating, your_answer=a, your_label=ANSWER_LABELS[a])
    try_next.sort(key=lambda item: -item["their_rating"])
    if len(try_next) < PICKS_LIMIT:
        try_next += _their_favorites(db, owner, seen_keys, PICKS_LIMIT - len(try_next))
    return {
        "score": score,
        "tier": tier(score),
        "rated_count": len(rated),
        "needed_for_score": max(0, MIN_ANSWERS - len(rated)),
        "agreed": [row(*item) for item in agreed[:PICKS_LIMIT]],
        "disagreements": [row(*item) for item in apart[:3]],
        "their_picks": try_next[:PICKS_LIMIT],
        "owner": {"id": owner.id, "username": owner.username},
    }


def _owned_keys(db: Session, user_id: int, category: str) -> set[str]:
    model = LIBRARY[category][0]
    return {normalize_title(title) for (title,) in db.query(model.title).filter(model.user_id == user_id)}


def save_answers(db: Session, viewer: models.User, owner: models.User, answers: list[tuple[str, str]]) -> dict:
    """Add a member's deck answers to their library. Titles they already have are never changed.

    Loved/Liked/Not for me become finished titles rated 9/7/4; Want to is saved as not started.
    Only the title's public details are copied, never the other member's rating, review or notes.
    """
    entries = _entries(db, owner, [card_id for card_id, _ in answers])
    owned: dict[str, set] = {}
    added, existing = [], []
    for card_id, answer in answers:
        hit = entries.get(card_id)
        if hit is None or answer not in ANSWER_LABELS:
            continue
        category, entry = hit
        if category not in owned:
            owned[category] = _owned_keys(db, viewer.id, category)
        key = normalize_title(entry.title)
        if key in owned[category]:
            existing.append(entry.title)
            continue
        record = LIBRARY[category][0](user_id=viewer.id, **copy_payload(category, entry))
        done = answer in ANSWER_RATING
        setattr(record, DONE_FIELD[category], done)
        record.rating = ANSWER_RATING[answer] if done else None
        db.add(record)
        owned[category].add(key)
        added.append({"category": category, "title": entry.title, "answer": answer})
    return {"added": added, "existing": existing}
