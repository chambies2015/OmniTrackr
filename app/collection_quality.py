"""Deterministic readiness checks for deliberately public collections.

The checks decide public discovery eligibility only. They never publish, edit,
or delete a member's saved collection.
"""
import re
from dataclasses import dataclass
from typing import Iterable

from .review_quality import WORD_PATTERN, is_public_review_safe


SENTENCE_END_PATTERN = re.compile(r"[.!?…](?:\s|$)")
GENERIC_TITLES = {
    "collection",
    "my collection",
    "new collection",
    "test collection",
    "untitled",
    "untitled collection",
}


@dataclass(frozen=True)
class CollectionQuality:
    """One readiness result shared by the editor, gallery, SEO, and reports."""

    character_count: int
    word_count: int
    sentence_count: int
    item_count: int
    safe: bool
    share_ready: bool
    discover_ready: bool
    checks: dict[str, bool]


def evaluate_public_collection(
    name: str | None,
    description: str | None,
    item_count: int,
    curator_notes: Iterable[str | None] = (),
    min_description_chars: int = 300,
    min_items: int = 3,
    max_items: int = 50,
) -> CollectionQuality:
    """Evaluate a collection without changing the owner's saved content."""
    title = str(name or "").strip()
    introduction = str(description or "").strip()
    notes = [str(note).strip() for note in curator_notes if str(note or "").strip()]
    words = WORD_PATTERN.findall(introduction)
    sentence_count = len(SENTENCE_END_PATTERN.findall(introduction))
    combined_text = " ".join((title, introduction, *notes))
    safe = is_public_review_safe(combined_text)
    varied_language = len(words) < 24 or (
        len({word.casefold() for word in words}) / len(words)
    ) >= 0.18
    normalized_title = " ".join(title.casefold().split())
    checks = {
        "meaningful_title": len(title) >= 4 and normalized_title not in GENERIC_TITLES,
        "description_length": len(introduction) >= min_description_chars,
        "enough_words": len(words) >= 45,
        "structured_thought": sentence_count >= 2 or len(words) >= 60,
        "varied_language": varied_language,
        "minimum_items": item_count >= min_items,
        "within_item_limit": item_count <= max_items,
        "safe_to_share": safe,
    }
    share_ready = all((checks["description_length"], checks["minimum_items"], checks["within_item_limit"]))
    return CollectionQuality(
        character_count=len(introduction),
        word_count=len(words),
        sentence_count=sentence_count,
        item_count=item_count,
        safe=safe,
        share_ready=share_ready,
        discover_ready=share_ready and all((
            checks["meaningful_title"],
            checks["enough_words"],
            checks["structured_thought"],
            checks["varied_language"],
            checks["safe_to_share"],
        )),
        checks=checks,
    )
