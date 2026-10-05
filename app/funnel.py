"""Anonymous sign-up funnel counters for the owner's Site stats page.

Each event adds 1 to a daily counter in ``site_traffic_daily`` (kind "funnel"),
through the same in-memory buffer as page views. Nothing identifies a person:
no user id, email, username, IP address or cookie is stored with an event.

Server-side events are recorded where they happen (registration, verification,
login). A few browser-only moments (the sign-up form opening, a guest saving a
title) come in through POST /api/funnel, which accepts only the names below.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from .site_traffic import BOT_PATTERN, RECORDER

# Ordered as the Site stats page shows them: (event, label)
STEPS = (
    ("landing_viewed", "Homepage seen by a visitor"),
    ("signup_form_opened", "Sign-up form opened"),
    ("signup_submitted", "Sign-up submitted"),
    ("signup_created", "Account created"),
    ("email_verified", "Email verified"),
    ("first_login", "First log-in"),
)
REJECTIONS = (
    ("signup_rejected_email_taken", "Email already registered"),
    ("signup_rejected_username_taken", "Username taken"),
    ("signup_rejected_username_invalid", "Username not allowed"),
    ("signup_rejected_password", "Password too weak"),
    ("signup_rejected_invalid", "Caught by form checks before sending"),
    ("signup_email_failed", "Verification email failed to send"),
    ("login_blocked_unverified", "Log-in before verifying"),
    ("verification_resent", "Verification email resent"),
    ("verification_link_expired", "Expired or invalid verification link"),
)
GUEST = (
    ("guest_pick_added", "Guest saved a title"),
    ("guest_list_signup", "Guest with saved titles opened sign-up"),
    ("guest_list_imported", "Saved titles moved into a new library"),
    ("share_clicked", "Share button used on a public page"),
)
SERVER_EVENTS = {name for name, _ in STEPS + REJECTIONS + GUEST}
# Events a browser may report; everything else is recorded on the server only.
CLIENT_EVENTS = {"signup_form_opened", "signup_rejected_invalid", "guest_pick_added", "guest_list_signup", "share_clicked"}


def record(event: str, request=None) -> bool:
    """Count one funnel event; never raises (analytics must not break sign-up)."""
    try:
        if event not in SERVER_EVENTS or not RECORDER.enabled:
            return False
        if request is not None and BOT_PATTERN.search(request.headers.get("user-agent", "") or "x"):
            return False
        day = datetime.now(timezone.utc).date()
        with RECORDER._lock:
            RECORDER._pending[(day, "funnel", event)] += 1
            RECORDER._events += 1
        if RECORDER.flush_due():
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(asyncio.to_thread(RECORDER.flush))
            except RuntimeError:
                pass  # No event loop (sync code path); the next page view flushes.
        return True
    except Exception:
        return False


def summary(counts: dict[str, int]) -> dict:
    """Shape raw {event: count} for the Site stats page."""
    return {
        "steps": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in STEPS],
        "issues": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in REJECTIONS],
        "guest": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in GUEST],
    }
