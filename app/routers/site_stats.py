"""Owner-only Site stats: growth, traffic, engagement and system health.

The page shell at /site-stats contains no data; the numbers come from
/api/site-stats/overview, which requires a signed-in admin (see admin_access).
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from .. import editorial_collections, funnel, google_signin, models, release_radar, supporters
from ..admin_access import is_site_admin
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from ..site_traffic import RECORDER
from .collections import _moderator_site_insights

router = APIRouter(tags=["site-stats"])

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "site_stats.html"
LIBRARY_MODELS = (
    ("movies", "Movies", models.Movie),
    ("tv_shows", "TV shows", models.TVShow),
    ("anime", "Anime", models.Anime),
    ("video_games", "Video games", models.VideoGame),
    ("music", "Music", models.Music),
    ("books", "Books", models.Book),
    ("manga", "Manga", models.Manga),
    ("podcasts", "Podcasts", models.Podcast),
    ("audiobooks", "Audiobooks", models.Audiobook),
)
RADAR_LABELS = {"movies": "Movies", "tv": "TV", "anime": "Anime", "games": "Games"}


def _require_admin(user: models.User) -> None:
    if not is_site_admin(user):
        raise HTTPException(status_code=403, detail="Site stats are only available to the site owner")


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"


@router.get("/site-stats", include_in_schema=False)
async def site_stats_page():
    response = strict_html_response(TEMPLATE.read_text(encoding="utf-8"))
    _no_store(response)
    return response


@router.get("/api/site-stats/access")
async def site_stats_access(response: Response, current_user: models.User = Depends(get_current_user)):
    """Lets the dashboard decide whether to show the Site stats link."""
    _no_store(response)
    return {"admin": is_site_admin(current_user)}


def _counts_between(db: Session, column, start: datetime, end: datetime | None = None) -> int:
    query = db.query(func.count()).filter(column >= start)
    if end is not None:
        query = query.filter(column < end)
    return int(query.scalar() or 0)


def _active_since(db: Session, start: datetime) -> int:
    """Members who logged in or opened OmniTrackr on a still-open session since `start`."""
    return int(db.query(func.count(models.User.id)).filter(or_(
        models.User.last_login_at >= start, models.User.last_seen_on >= start.date())).scalar() or 0)


def _traffic(db: Session, days: int, today: date) -> dict:
    table = models.SiteTrafficDaily
    start = today - timedelta(days=days - 1)
    previous_start = start - timedelta(days=days)
    rows = db.query(table.day, table.kind, table.key, table.count).filter(table.day >= previous_start).all()
    first_day = db.query(func.min(table.day)).scalar()

    series = {start + timedelta(days=offset): {"views": 0, "visitors": 0} for offset in range(days)}
    current_totals = {"views": 0, "visitors": 0}
    previous_totals = {"views": 0, "visitors": 0}
    breakdowns: dict[str, dict[str, int]] = {"page": {}, "source": {}, "device": {}, "audience": {}}
    for day, kind, key, count in rows:
        in_current = day >= start
        if kind == "total" and key in current_totals:
            if in_current:
                current_totals[key] += count
                if day in series:
                    series[day][key] += count
            else:
                previous_totals[key] += count
        elif kind in breakdowns and in_current:
            breakdowns[kind][key] = breakdowns[kind].get(key, 0) + count

    def top(kind: str, limit: int) -> list[dict]:
        ordered = sorted(breakdowns[kind].items(), key=lambda pair: (-pair[1], pair[0]))
        return [{"key": key, "count": count} for key, count in ordered[:limit]]

    today_row = series.get(today, {"views": 0, "visitors": 0})
    return {
        "tracking_since": first_day.isoformat() if first_day else None,
        "enabled": RECORDER.enabled,
        "today": today_row,
        "totals": current_totals,
        "previous_totals": previous_totals,
        "series": [{"date": day.isoformat(), **values} for day, values in sorted(series.items())],
        "top_pages": top("page", 15),
        "sources": top("source", 12),
        "devices": top("device", 5),
        "audience": top("audience", 3),
    }


def _popular_titles(db: Session, limit: int = 12) -> list[dict]:
    """Titles saved by the most distinct members (only titles in 2+ libraries)."""
    rows = []
    editors = db.query(models.User.id).filter(models.User.username == editorial_collections.EDITOR_USERNAME)
    for key, label, model in LIBRARY_MODELS:
        title = func.lower(func.trim(model.title))
        for normalized, display, members in db.query(
            title, func.min(model.title), func.count(func.distinct(model.user_id))
        ).filter(~model.user_id.in_(editors)).group_by(title).having(func.count(func.distinct(model.user_id)) >= 2).order_by(
            func.count(func.distinct(model.user_id)).desc()
        ).limit(limit).all():
            rows.append({"category": label, "title": display, "members": int(members)})
    rows.sort(key=lambda row: (-row["members"], row["title"].lower()))
    return rows[:limit]


def _signups(db: Session, days: int, today: date) -> list[dict]:
    start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
    counts: dict[str, int] = {}
    for created_at, in db.query(models.User.created_at).filter(models.User.created_at >= start).all():
        if created_at:
            counts[created_at.date().isoformat()] = counts.get(created_at.date().isoformat(), 0) + 1
    return [
        {"date": (today - timedelta(days=offset)).isoformat(),
         "signups": counts.get((today - timedelta(days=offset)).isoformat(), 0)}
        for offset in range(days - 1, -1, -1)
    ]


def _library_additions(db: Session, days: int, today: date) -> list[dict]:
    """Journal entries logged per day (library items themselves carry no created date)."""
    start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
    counts: dict[str, int] = {}
    for occurred_at, in db.query(models.ActivityEntry.created_at).filter(models.ActivityEntry.created_at >= start).all():
        if occurred_at:
            counts[occurred_at.date().isoformat()] = counts.get(occurred_at.date().isoformat(), 0) + 1
    return [
        {"date": (today - timedelta(days=offset)).isoformat(),
         "entries": counts.get((today - timedelta(days=offset)).isoformat(), 0)}
        for offset in range(days - 1, -1, -1)
    ]


def _funnel(db: Session, days: int, today: date) -> dict:
    """Sign-up funnel counters for the range (see app/funnel.py)."""
    table = models.SiteTrafficDaily
    start = today - timedelta(days=days - 1)
    counts = dict(db.query(table.key, func.sum(table.count)).filter(
        table.kind == "funnel", table.day >= start).group_by(table.key).all())
    return funnel.summary({key: int(value or 0) for key, value in counts.items()})


def _retention(db: Session) -> dict:
    """Opt-in counts for features that bring members back."""
    return {
        "weekly_email_subscribers": int(db.query(func.count(models.EmailDigestSubscription.id)).scalar() or 0),
        "public_profiles": int(db.query(func.count(models.PublicProfile.id)).filter(models.PublicProfile.enabled == True).scalar() or 0),
    }


def _count(query) -> int:
    return int(query.scalar() or 0)


def _growth(db: Session, days: int, now: datetime) -> dict:
    """This month's growth features: invite links, Ko-fi supporters, weekly email, release calendars and "ask a friend"."""
    start = now - timedelta(days=days)
    signup = models.FriendInviteSignup
    supporter = models.Supporter
    payment = models.KofiPayment
    return {
        "invites": {
            "links": _count(db.query(func.count(models.FriendInvite.id))),
            "new_links": _counts_between(db, models.FriendInvite.created_at, start),
            "signups": _counts_between(db, signup.created_at, start),
            "friends_made": _counts_between(db, signup.completed_at, start),
            "awaiting_verification": _count(db.query(func.count(signup.id)).filter(signup.completed_at.is_(None))),
        },
        "supporters": {
            "active": _count(db.query(func.count(supporter.id)).filter(supporter.active_until > now)),
            "monthly": _count(db.query(func.count(supporter.id)).filter(supporter.active_until > now, supporter.monthly == True)),
            "all_time": _count(db.query(func.count(supporter.id))),
            "new": _counts_between(db, supporter.since, start),
            "payments": _count(db.query(func.count(payment.id)).filter(payment.received_at >= start, ~supporters.is_test_payment())),
            # Ko-fi test pings and payments the owner set aside don't need linking.
            "unlinked_payments": supporters.waiting_count(db),
        },
        "weekly_email": {
            "subscribers": _count(db.query(func.count(models.EmailDigestSubscription.id))),
            "new": _counts_between(db, models.EmailDigestSubscription.created_at, start),
        },
        "calendar": {
            "feeds": _count(db.query(func.count(models.CalendarFeed.id))),
            "new": _counts_between(db, models.CalendarFeed.created_at, start),
            "refreshed_7d": _count(db.query(func.count(models.CalendarFeed.id))
                                   .filter(models.CalendarFeed.last_fetched_at >= now - timedelta(days=7))),
        },
        "takes": {
            "asked": _counts_between(db, models.TakeRequest.created_at, start),
            "answered": _counts_between(db, models.TakeResponse.created_at, start),
        },
    }


def _announcement_status(db: Session) -> dict | None:
    try:
        from .. import announcements
        return announcements.status(db)
    except Exception:
        db.rollback()
        return None


def _comeback_status(db: Session) -> dict | None:
    try:
        from .. import comeback
        return comeback.status(db)
    except Exception:
        db.rollback()
        return None


def _welcome_status(db: Session) -> dict | None:
    try:
        from .. import welcome_emails
        return welcome_emails.status(db)
    except Exception:
        db.rollback()
        return None


def _title_details(db: Session) -> dict:
    """How many title pages have their public facts cached (filled in by a background job)."""
    counts = dict(db.query(models.TitleMetadata.status, func.count(models.TitleMetadata.id))
                  .group_by(models.TitleMetadata.status).all())
    return {"found": int(counts.get("ok", 0)), "not_found": int(counts.get("miss", 0)), "errors": int(counts.get("error", 0))}


def _system() -> dict:
    database_url = os.getenv("DATABASE_URL", "")
    radar = []
    now = time.time()
    for category in release_radar.CATEGORY_ORDER:
        try:
            window = release_radar.current_window(category)
            entry = release_radar.CACHE.entries.get(window.cache_key) or release_radar.CACHE.peek(window)
        except Exception:
            entry, window = None, None
        fetched = (entry or {}).get("fetched_at") or 0
        radar.append({
            "category": RADAR_LABELS.get(category, category),
            "window": window.slug if window else None,
            "items": len((entry or {}).get("items") or []),
            "age_hours": round((now - fetched) / 3600, 1) if fetched else None,
            "error": (entry or {}).get("error"),
        })
    return {
        "database": "PostgreSQL" if database_url.startswith(("postgres", "postgresql")) else "SQLite",
        "environment": os.getenv("ENVIRONMENT", "development"),
        "integrations": [
            {"name": "OMDb (movie/TV posters)", "configured": bool(os.getenv("OMDB_API_KEY"))},
            {"name": "RAWG (games + Release Radar games)", "configured": bool(os.getenv("RAWG_API_KEY"))},
            {"name": "Email (verification + resets)", "configured": bool(os.getenv("MAIL_USERNAME") and os.getenv("MAIL_PASSWORD"))},
            {"name": "Google sign-in", "configured": google_signin.configured()},
            {"name": "Amazon Associates tag", "configured": bool(os.getenv("AMAZON_ASSOCIATES_TAG"))},
            {"name": "AdSense publisher id", "configured": bool(os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719"))},
            {"name": "Traffic counting", "configured": RECORDER.enabled},
        ],
        "release_radar": radar,
    }


@router.get("/api/site-stats/overview")
def site_stats_overview(
    response: Response,
    days: int = Query(30, ge=7, le=90),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _require_admin(current_user)
    _no_store(response)
    # Include the counts still waiting in memory so the page is current.
    try:
        RECORDER.flush()
    except Exception:
        pass
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date()
    insights = _moderator_site_insights(db)
    members = {
        "active_24_hours": _active_since(db, now - timedelta(hours=24)),
        "active_7_days": _active_since(db, now - timedelta(days=7)),
        "active_30_days": _active_since(db, now - timedelta(days=30)),
        "new_today": _counts_between(db, models.User.created_at, datetime.combine(today, datetime.min.time())),
        "new_in_range": _counts_between(db, models.User.created_at, now - timedelta(days=days)),
        "new_previous_range": _counts_between(
            db, models.User.created_at, now - timedelta(days=days * 2), now - timedelta(days=days)
        ),
    }
    return {
        "generated_at": now.isoformat() + "Z",
        "days": days,
        "viewer": current_user.username,
        "members": members,
        "signups": _signups(db, days, today),
        "journal_activity": _library_additions(db, days, today),
        "traffic": _traffic(db, days, today),
        "funnel": _funnel(db, days, today),
        "retention": _retention(db),
        "growth": _growth(db, days, now),
        "popular_titles": _popular_titles(db),
        "insights": insights,
        "system": {**_system(), "title_details": _title_details(db)},
        "editor_collections": editorial_collections.status(db),
        "announcement": _announcement_status(db),
        "comeback": _comeback_status(db),
        "welcome": _welcome_status(db),
    }


@router.post("/api/site-stats/editor-collections")
async def publish_editor_collections(
    request: Request,
    response: Response,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish the starter public collections (idempotent; existing ones are left alone)."""
    _require_admin(current_user)
    _no_store(response)
    client = getattr(request.app.state, "external_api_client", None)
    try:
        return await editorial_collections.publish(db, client)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(error))


class FunnelEvent(BaseModel):
    event: str = Field(..., max_length=40)


@router.post("/api/funnel", status_code=204, include_in_schema=False)
async def record_funnel_event(payload: FunnelEvent, request: Request):
    """Browser-side sign-up moments (whitelisted names only; nothing about the visitor is stored)."""
    if payload.event in funnel.CLIENT_EVENTS:
        funnel.record(payload.event, request)
    return Response(status_code=204)


# ---------------------------------------------------------------- "What's new" email

class AnnouncementAction(BaseModel):
    action: str = Field(..., pattern="^(start|pause|test)$")


@router.get("/site-stats/announcement-preview", include_in_schema=False)
def announcement_preview(request: Request, current_user: models.User = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    """The update email exactly as the owner would receive it (nothing is sent)."""
    from fastapi.responses import HTMLResponse
    from .. import announcements
    from ..for_you import radar_pool
    _require_admin(current_user)
    try:
        pool = radar_pool(None, getattr(request.app.state, "external_api_client", None))
    except Exception:
        pool = None
    subject, html, _text, _url = announcements.email_for(db, current_user, pool)
    banner = (f'<div style="font:14px Arial,sans-serif;background:#fef3c7;color:#78350f;padding:10px 16px">'
              f'Preview only. Subject: <strong>{subject.replace("<", "&lt;")}</strong></div>')
    response = HTMLResponse(html.replace(
        '<div style="max-width:560px', banner + '<div style="max-width:560px', 1))
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; frame-ancestors 'none'"
    _no_store(response)
    return response


@router.post("/api/site-stats/announcement")
async def announcement_action(payload: AnnouncementAction, request: Request, response: Response,
                              current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from .. import announcements
    _require_admin(current_user)
    _no_store(response)
    if payload.action == "test":
        if not announcements.mail_configured():
            raise HTTPException(status_code=409, detail="Email isn't configured on this server.")
        try:
            await announcements.send_test(db, current_user, getattr(request.app.state, "external_api_client", None))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"The test email couldn't be sent: {error}")
        return {**announcements.status(db), "message": f"Test sent to {current_user.email}."}
    announcements.set_status(db, "sending" if payload.action == "start" else "paused")
    return announcements.status(db)


# ---------------------------------------------------------------- come-back email

class ComebackAction(BaseModel):
    action: str = Field(..., pattern="^(start|pause|test)$")


@router.get("/site-stats/comeback-preview", include_in_schema=False)
def comeback_preview(request: Request, current_user: models.User = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    """The come-back email as the owner would receive it (nothing is sent)."""
    from fastapi.responses import HTMLResponse
    from .. import comeback
    from ..for_you import radar_pool
    _require_admin(current_user)
    try:
        pool = radar_pool(None, getattr(request.app.state, "external_api_client", None))
    except Exception:
        pool = None
    subject, html, _text, _url = comeback.email_for(db, current_user, pool)
    banner = (f'<div style="font:14px Arial,sans-serif;background:#fef3c7;color:#78350f;padding:10px 16px">'
              f'Preview only, filled in from your own library. Subject: <strong>{subject.replace("&", "&amp;").replace("<", "&lt;")}</strong></div>')
    response = HTMLResponse(html.replace(
        '<div style="max-width:560px', banner + '<div style="max-width:560px', 1))
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; frame-ancestors 'none'"
    _no_store(response)
    return response


@router.post("/api/site-stats/comeback")
async def comeback_action(payload: ComebackAction, request: Request, response: Response,
                          current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from .. import comeback
    _require_admin(current_user)
    _no_store(response)
    if payload.action == "test":
        if not comeback.mail_configured():
            raise HTTPException(status_code=409, detail="Email isn't configured on this server.")
        try:
            await comeback.send_test(db, current_user, getattr(request.app.state, "external_api_client", None))
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"The test email couldn't be sent: {error}")
        return {**comeback.status(db), "message": f"Test sent to {current_user.email}."}
    comeback.set_status(db, "sending" if payload.action == "start" else "paused")
    return comeback.status(db)


# ---------------------------------------------------------------- welcome emails

class WelcomeAction(BaseModel):
    action: str = Field(..., pattern="^(start|pause|test)$")


@router.get("/site-stats/welcome-preview", include_in_schema=False)
def welcome_preview(step: int = Query(1, ge=1, le=3), current_user: models.User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    """One welcome email as the owner would receive it (nothing is sent)."""
    from fastapi.responses import HTMLResponse
    from .. import welcome_emails
    _require_admin(current_user)
    chosen = welcome_emails.step_for(step)
    subject, html, _text, _url = welcome_emails.email_for(db, current_user, chosen)
    others = " · ".join(
        f'<a href="/site-stats/welcome-preview?step={other.number}" style="color:#78350f">{other.label}</a>'
        if other.number != step else f"<strong>{other.label}</strong>" for other in welcome_emails.STEPS)
    banner = (f'<div style="font:14px Arial,sans-serif;background:#fef3c7;color:#78350f;padding:10px 16px">'
              f'Preview only, filled in from your own library. Subject: <strong>{subject.replace("&", "&amp;").replace("<", "&lt;")}</strong>'
              f'<div style="margin-top:6px">{others}</div></div>')
    response = HTMLResponse(html.replace(
        '<div style="max-width:560px', banner + '<div style="max-width:560px', 1))
    response.headers["Content-Security-Policy"] = "default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; frame-ancestors 'none'"
    _no_store(response)
    return response


@router.post("/api/site-stats/welcome")
async def welcome_action(payload: WelcomeAction, response: Response,
                         current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    from .. import welcome_emails
    _require_admin(current_user)
    _no_store(response)
    if payload.action == "test":
        if not welcome_emails.mail_configured():
            raise HTTPException(status_code=409, detail="Email isn't configured on this server.")
        try:
            await welcome_emails.send_test(db, current_user)
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"The test emails couldn't be sent: {error}")
        return {**welcome_emails.status(db), "message": f"All three sent to {current_user.email}."}
    welcome_emails.set_status(db, "sending" if payload.action == "start" else "paused")
    return welcome_emails.status(db)
