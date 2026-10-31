"""Anonymous sign-up funnel counters for the owner's Site stats page.

Each event adds 1 to a daily counter in ``site_traffic_daily`` (kind "funnel"),
through the same in-memory buffer as page views. Nothing identifies a person:
no user id, email, username, IP address or cookie is stored with an event.

Server-side events are recorded where they happen (registration, verification,
login). A few browser-only moments (the sign-up form opening, a guest saving a
title) come in through POST /api/funnel, which accepts only the names below.
"Homepage seen by a person" comes from the page's own visit report (see
site_traffic.record_person), once per person per day.

Each moment fires exactly one event in one place. Steps that can happen two ways
(an account made with the email form or with Google) are added up in summary(),
so the funnel never counts the same person twice for one step.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from .site_traffic import BOT_PATTERN, RECORDER

# Ordered as the Site stats page shows them: (step, label). "signup_sent" and
# "account_confirmed" add two events together (see summary()); the rest are events.
STEPS = (
    ("landing_seen", "Homepage seen by a person"),
    ("signup_form_opened", "Started signing up"),
    ("signup_sent", "Sign-up sent"),
    ("signup_created", "Account created"),
    ("account_confirmed", "Account confirmed"),
    ("first_login", "First log-in"),
)
# The homepage's own path: search, save, then sign up with the saved titles.
HOMEPAGE = (
    ("landing_seen", "Homepage seen by a person"),
    ("title_search_used", "Searched for a title"),
    ("guest_pick_added", "Saved a title"),
    ("guest_list_signup", "Started signing up with titles saved"),
    ("guest_list_imported", "Saved titles moved into a new library"),
)
# Every homepage load the server sent, bots and scanners included (kept for comparison).
RAW = (
    ("landing_viewed", "Homepage loads, all requests"),
)
DERIVED_STEPS = {"signup_sent", "account_confirmed"}
# A first log-in only counts for accounts made recently; older members who never
# logged in since log-ins were counted would otherwise show up as new.
FIRST_LOGIN_MAX_AGE = timedelta(days=30)
REJECTIONS = (
    ("signup_rejected_email_taken", "Email already registered"),
    ("signup_rejected_username_taken", "Username taken"),
    ("signup_rejected_username_invalid", "Username not allowed"),
    ("signup_rejected_email_invalid", "Email address not accepted"),
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
    ("seasonal_saved", "Seasonal hubs (Halloween, Holiday): a pick saved to a list or library"),
    ("guest_list_signup", "Guest with saved titles opened sign-up"),
    ("guest_list_imported", "Saved titles moved into a new library"),
    ("share_clicked", "Share button used on a public page"),
    ("recap_kofi_clicked", "Ko-fi link opened from Year in Review"),
    ("recap_story_played", "Year in Review story opened"),
    ("recap_story_shared", "Year in Review story image saved or shared"),
    ("recap_opened", "Year in Review opened by a member"),
    ("recap_link_created", "Year in Review: share link created"),
    ("recap_link_opened", "Year in Review: shared link opened by a visitor without an account"),
    ("year_so_far_card_opened", "Year so far (November): opened from the dashboard card"),
    ("year_so_far_email_opened", "Year so far (November): opened from the weekly email"),
    ("year_so_far_push_opened", "Year so far (November): opened from the notification"),
    ("supporters_kofi_clicked", "Ko-fi link opened from the supporters page"),
    ("calendar_subscribe_clicked", "Release calendar subscribe button used"),
    ("tier_list_started", "Tier list: a title ranked"),
    ("tier_list_exported", "Tier list: image saved or shared"),
    ("daily_played", "Daily puzzle: a game started"),
    ("daily_solved", "Daily puzzle: solved"),
    ("daily_shared", "Daily puzzle: result shared"),
    ("taste_match_viewed", "Taste Match opened with a friend"),
    ("taste_match_saved", "Taste Match: a friend's favorite saved to the library"),
    ("compare_link_opened", "Compare tastes: a member's link opened by a visitor without an account"),
    ("compare_finished", "Compare tastes: someone rated the deck and saw their score"),
    ("compare_signup_clicked", "Compare tastes: sign-up button pressed after a result"),
    ("compare_imported", "Compare tastes: answers saved before sign-up moved into a new library"),
    ("compare_shared", "Compare tastes: a result or link shared"),
    ("shared_list_created", "Shared list created"),
    ("shared_list_link_opened", "Shared list link opened by a visitor without an account"),
    ("shared_list_joined", "Someone joined a shared list through its link"),
    ("club_pick_started", "Watch club: a club pick started on a shared list"),
    ("club_post", "Watch club: a post in a club pick's discussion"),
    ("tonight_poll_created", "Group poll: a poll made"),
    ("tonight_poll_link_opened", "Group poll: link opened by a visitor without an account"),
    ("tonight_poll_guest_voted", "Group poll: a visitor without an account voted"),
    ("tonight_poll_voted", "Group poll: a member voted"),
    ("tonight_poll_signup_clicked", "Group poll: sign-up button pressed"),
    ("friend_rec_sent", "Recommend to a friend: a title sent to friends"),
    ("friend_rec_link_opened", "Recommend to a friend: link opened by a visitor without an account"),
    ("friend_rec_claimed", "Recommend to a friend: link saved into someone's inbox"),
    ("friend_rec_added", "Recommend to a friend: a recommendation added to a library"),
    ("quiz_started", "Taste quiz started"),
    ("quiz_finished", "Taste quiz finished"),
    ("quiz_imported", "Taste quiz answers saved before sign-up moved into a new library"),
    ("quiz_saved", "Taste quiz: a suggested pick saved to a list or library"),
    ("profile_link_opened", "Public profile opened by a visitor without an account"),
    ("profile_signup_clicked", "Public profile: sign-up button pressed"),
)
# The start page new members land on after their first log-in (app/start_flow.py).
# Each counts a member once: the first time it happens.
START = (
    ("start_opened", "Opened the start page"),
    ("start_first_saved", "Saved a title there"),
    ("start_reached_five", "Reached five titles"),
    ("start_next_step", "Went on to a first-week step"),
)
START_PATHS = (
    ("start_quick_add", "Used quick add"),
    ("start_search", "Used search"),
    ("start_import", "Opened the importer"),
    ("start_quiz", "Opened the taste quiz"),
    ("start_skipped", "Skipped to the library"),
)
GOOGLE = (
    ("google_signin_started", "Google button pressed (clicks in a browser)"),
    ("google_account_created", "New accounts made with Google"),
    ("google_account_linked", "Existing accounts linked to Google"),
    ("google_signin", "Log-ins with Google"),
    ("google_signin_failed", "Google sign-in that didn't finish"),
)
SERVER_EVENTS = {name for name, _ in STEPS + HOMEPAGE + RAW + REJECTIONS + GUEST + GOOGLE + START + START_PATHS} - DERIVED_STEPS | {"signup_submitted", "email_verified"}
# Events a browser may report; everything else is recorded on the server only.
CLIENT_EVENTS = {"signup_form_opened", "hero_signup_clicked", "signup_rejected_invalid", "guest_pick_added", "guest_list_signup", "share_clicked",
                 "recap_kofi_clicked", "supporters_kofi_clicked", "title_search_used", "pick_used", "pick_saved", "liked_saved",
                 "order_saved", "seasonal_saved",
                 "calendar_subscribe_clicked", "tier_list_started", "tier_list_exported",
                 "daily_shared", "recap_story_played", "recap_story_shared", "quiz_started", "quiz_saved",
                 "profile_signup_clicked", "tonight_poll_signup_clicked", "compare_signup_clicked", "compare_shared"}


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


def record_first_login(user, request=None) -> bool:
    """Count a member's first log-in, if their account is new (see FIRST_LOGIN_MAX_AGE)."""
    if user.login_count:
        return False
    created = getattr(user, "created_at", None)
    if created is not None:
        if created.tzinfo is not None:
            created = created.astimezone(timezone.utc).replace(tzinfo=None)
        if datetime.now(timezone.utc).replace(tzinfo=None) - created > FIRST_LOGIN_MAX_AGE:
            return False
    return record("first_login", request)


def _plural(count: int, one: str, many: str) -> str:
    return f"{count:,} {one if count == 1 else many}"


def summary(counts: dict[str, int]) -> dict:
    """Shape raw {event: count} for the Site stats page."""
    count = lambda name: int(counts.get(name, 0))  # noqa: E731
    google = count("google_account_created")
    email_created = max(count("signup_created") - google, 0)
    values = {name: count(name) for name, _ in STEPS if name not in DERIVED_STEPS}
    values["signup_sent"] = count("signup_submitted") + google
    values["account_confirmed"] = count("email_verified") + google
    details = {
        "landing_seen": f"{count('landing_viewed'):,} homepage loads in all requests, bots included",
        "signup_form_opened": "Email form opened or Google button pressed, once per visit",
        "signup_sent": f"{_plural(count('signup_submitted'), 'email form', 'email forms')}, {google:,} with Google",
        "signup_created": f"{email_created:,} by email, {google:,} with Google",
        "account_confirmed": f"{_plural(count('email_verified'), 'email link', 'email links')} opened, {google:,} confirmed by Google",
        "first_login": "Accounts made in the last 30 days",
    }
    return {
        "steps": [{"event": name, "label": label, "count": values[name], "detail": details.get(name, "")}
                  for name, label in STEPS],
        "homepage": [{"event": name, "label": label, "count": count(name)} for name, label in HOMEPAGE],
        "raw": [{"event": name, "label": label, "count": count(name)} for name, label in RAW],
        "issues": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in REJECTIONS],
        "guest": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in GUEST],
        "google": [{"event": name, "label": label, "count": int(counts.get(name, 0))} for name, label in GOOGLE],
        "start": [{"event": name, "label": label, "count": count(name)} for name, label in START],
        "start_paths": [{"event": name, "label": label, "count": count(name)} for name, label in START_PATHS],
    }
