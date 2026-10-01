"""
Public review quality checks.

These checks only control public discovery surfaces. They do not mutate or delete
stored user reviews.
"""
import re
from dataclasses import dataclass


URL_PATTERN = re.compile(r"(?:https?://|www\.)[^\s<]+", re.IGNORECASE)
EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+?\d[\s().-]*){8,}\b")
PROMOTIONAL_PHRASES = (
    "adult dating",
    "buy followers",
    "casino bonus",
    "click here",
    "contact me at",
    "crypto giveaway",
    "download full movie",
    "free download",
    "loan approval",
    "online casino",
    "promo code",
    "stream full movie",
    "telegram channel",
    "visit my site",
    "watch online free",
    "whatsapp",
    "work from home",
)
PLACEHOLDER_PHRASES = (
    "asdf",
    "lorem ipsum",
    "placeholder review",
    "test review",
)
WORD_PATTERN = re.compile(r"[\w'-]+", re.UNICODE)
SENTENCE_END_PATTERN = re.compile(r"[.!?…](?:\s|$)")


@dataclass(frozen=True)
class ReviewQuality:
    """One authoritative quality result shared by feeds, SEO, ads, and editors."""

    character_count: int
    word_count: int
    sentence_count: int
    safe: bool
    community_ready: bool
    search_ready: bool
    checks: dict[str, bool]


def is_public_review_safe(review_text: str | None) -> bool:
    """Return whether review text is suitable for public discovery and indexing."""
    if not review_text:
        return False

    normalized = " ".join(str(review_text).lower().split())
    if URL_PATTERN.search(review_text) or EMAIL_PATTERN.search(review_text) or PHONE_PATTERN.search(review_text):
        return False

    if any(phrase in normalized for phrase in PROMOTIONAL_PHRASES + PLACEHOLDER_PHRASES):
        return False

    return True


def evaluate_public_review(
    review_text: str | None,
    community_min_chars: int = 80,
    search_min_chars: int = 240,
) -> ReviewQuality:
    """Evaluate public usefulness without changing the user's saved review."""
    text = str(review_text or "").strip()
    words = WORD_PATTERN.findall(text)
    sentence_count = len(SENTENCE_END_PATTERN.findall(text))
    safe = is_public_review_safe(text)
    varied_language = len(words) < 24 or (len(set(word.lower() for word in words)) / len(words)) >= 0.18
    checks = {
        "community_length": len(text) >= community_min_chars,
        "search_length": len(text) >= search_min_chars,
        "enough_words": len(words) >= 35,
        "structured_thought": sentence_count >= 2 or len(words) >= 55,
        "varied_language": varied_language,
        "safe_to_share": safe,
    }
    return ReviewQuality(
        character_count=len(text),
        word_count=len(words),
        sentence_count=sentence_count,
        safe=safe,
        community_ready=checks["community_length"] and varied_language and safe,
        search_ready=all((
            checks["search_length"],
            checks["enough_words"],
            checks["structured_thought"],
            varied_language,
            safe,
        )),
        checks=checks,
    )
