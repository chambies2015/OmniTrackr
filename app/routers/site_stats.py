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
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import editorial_collections, models, release_radar
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
            {"name": "Amazon Associates tag", "configured": bool(os.getenv("AMAZON_ASSOCIATES_TAG"))},
            {"name": "AdSense publisher id", "configured": bool(os.getenv("ADSENSE_PUBLISHER_ID", "pub-7271682066779719"))},
            {"name": "Traffic counting", "configured": RECORDER.enabled},
        ],
        "release_radar": radar,
    }


@router.get("/api/site-stats/overview")
async def site_stats_overview(
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
    last_login = models.User.last_login_at
    members = {
        "active_24_hours": _counts_between(db, last_login, now - timedelta(hours=24)),
        "active_7_days": _counts_between(db, last_login, now - timedelta(days=7)),
        "active_30_days": _counts_between(db, last_login, now - timedelta(days=30)),
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
        "popular_titles": _popular_titles(db),
        "insights": insights,
        "system": _system(),
        "editor_collections": editorial_collections.status(db),
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
