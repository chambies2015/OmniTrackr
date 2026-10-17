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
    ("hero_signup_clicked", "Sign-up button at the top of the homepage pressed"),
    ("title_search_used", "Guest searched for a title on the homepage"),
    ("guest_pick_added", "Guest saved a title"),
    ("pick_used", "Pick for me suggestion asked for"),
    ("pick_saved", "Pick for me suggestion saved to a list or library"),
    ("liked_saved", "If you liked guide: a pick saved to a list or library"),
    ("order_saved", "In order guide: entries saved to a list or library"),
    ("guest_list_signup", "Guest with saved titles opened sign-up"),
    ("guest_list_imported", "Saved titles moved into a new library"),
    ("share_clicked", "Share button used on a public page"),
    ("recap_kofi_clicked", "Ko-fi link opened from Year in Review"),
    ("calendar_subscribe_clicked", "Release calendar subscribe button used"),
    ("tier_list_started", "Tier list: a title ranked"),
    ("tier_list_exported", "Tier list: image saved or shared"),
    ("daily_played", "Daily puzzle: a game started"),
    ("daily_solved", "Daily puzzle: solved"),
    ("daily_shared", "Daily puzzle: result shared"),
    ("taste_match_viewed", "Taste Match opened with a friend"),
    ("taste_match_saved", "Taste Match: a friend's favorite saved to the library"),
)
GOOGLE = (
    ("google_signin_started", "Google button pressed"),
    ("google_account_created", "New accounts made with Google"),
    ("google_account_linked", "Existing accounts linked to Google"),
    ("google_signin", "Log-ins with Google"),
    ("google_signin_failed", "Google sign-in that didn't finish"),
)
SERVER_EVENTS = {name for name, _ in STEPS + REJECTIONS + GUEST + GOOGLE}
# Events a browser may report; everything else is recorded on the server only.
CLIENT_EVENTS = {"signup_form_opened", "hero_signup_clicked", "signup_rejected_invalid", "guest_pick_added", "guest_list_signup", "share_clicked",
                 "recap_kofi_clicked", "title_search_used", "pick_used", "pick_saved", "liked_saved", "order_saved",
                 "calendar_subscribe_clicked", "tier_list_started", "tier_list_exported",
                 "daily_shared"}


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
        "google": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in GOOGLE],
    }
