"""
Public review quality checks.

These checks only control public discovery surfaces. They do not mutate or delete
stored user reviews.
"""
import re


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


def is_public_review_safe(review_text: str | None) -> bool:
    """Return whether review text is suitable for public discovery and indexing."""
    if not review_text:
        return False

    normalized = " ".join(str(review_text).lower().split())
    if URL_PATTERN.search(review_text) or EMAIL_PATTERN.search(review_text) or PHONE_PATTERN.search(review_text):
        return False

    return not any(phrase in normalized for phrase in PROMOTIONAL_PHRASES)
