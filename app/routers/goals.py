"""Yearly goals: the member's private targets and their progress."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import goals, models
from ..auth import AUTH_COOKIE_NAME
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db
from .profiles import _CardCache

router = APIRouter(tags=["goals"])
_CARDS = _CardCache(size=64)


class GoalTarget(BaseModel):
    target: int


def _no_store(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


@router.get("/api/goals")
def list_goals(response: Response, year: Optional[int] = None,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    year = year or datetime.utcnow().year
    if not 2000 <= year <= max(goals.allowed_years()):
        raise HTTPException(status_code=422, detail="Goals can be set for this year or next year.")
    return goals.payload(db, user, year)


@router.put("/api/goals/{year}/{category}")
def save_goal(year: int, category: str, body: GoalTarget, request: Request, response: Response,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    try:
        goals.save(db, user.id, year, category, body.target)
    except ValueError as error:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(error))
    return goals.payload(db, user, year)


@router.delete("/api/goals/{year}/{category}")
def delete_goal(year: int, category: str, request: Request, response: Response,
                user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    if not goals.remove(db, user.id, year, category):
        raise HTTPException(status_code=404, detail="No goal to remove.")
    return goals.payload(db, user, year)


# ---------------------------------------------------------------- goal reached

def _reached(db: Session, user: models.User, year: int, category: str) -> models.GoalAchievement:
    row = goals.get_achievement(db, user.id, year, category)
    if row is None:
        raise HTTPException(status_code=404, detail="That goal hasn't been reached yet.")
    return row


@router.post("/api/goals/{year}/{category}/seen")
def goal_seen(year: int, category: str, response: Response,
              user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The member dismissed the dashboard celebration."""
    _no_store(response)
    _reached(db, user, year, category)
    goals.mark_seen(db, user.id, year, category)
    return goals.achievement_payload(goals.get_achievement(db, user.id, year, category))


@router.put("/api/goals/{year}/{category}/share")
def share_goal(year: int, category: str, request: Request, response: Response,
               user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Make a public link for a reached goal. It shows only the headline, never titles."""
    _no_store(response)
    _reached(db, user, year, category)
    return goals.achievement_payload(goals.share(db, user.id, year, category))


@router.delete("/api/goals/{year}/{category}/share")
def unshare_goal(year: int, category: str, response: Response,
                 user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    _no_store(response)
    _reached(db, user, year, category)
    _CARDS.clear_user(user.id)
    return goals.achievement_payload(goals.unshare(db, user.id, year, category))


def _shared_or_404(db: Session, token: str) -> tuple[models.GoalAchievement, models.User]:
    row = goals.find_shared(db, token)
    if row is None:
        raise HTTPException(status_code=404, detail="This goal isn't shared anymore")
    return row, db.get(models.User, row.user_id)


@router.get("/goal/{token}", include_in_schema=False)
def shared_goal_page(token: str, request: Request, db: Session = Depends(get_db)):
    from .year_in_review import _e, _page
    row, owner = _shared_or_404(db, token)
    canonical = goals.SITE_URL + goals.share_path(row)
    title = goals.headline(owner.username, row.category, row.target, row.year)
    signed_in = bool(request.cookies.get(AUTH_COOKIE_NAME))
    singular, plural = goals.NOUNS.get(row.category, goals.NOUNS[goals.ALL])
    noun = singular if row.target == 1 else plural
    body = (f'<section class="title-section goal-reached" aria-label="Goal reached">'
            f'<ol class="recap-goals"><li class="recap-goal recap-goal--done">'
            f'<strong>{_e(row.target)} of {_e(row.target)} {_e(noun)}</strong>'
            f'<span class="recap-goal__track"><span class="recap-goal__fill" style="width: 100%"></span></span>'
            f'<small>Goal reached in {_e(row.reached_at.strftime("%B %Y") if row.reached_at else row.year)}</small>'
            f'</li></ol></section>')
    cta = ('<section class="profile-cta site-card"><div><h2>Set your own goal</h2>'
           f'<p>Pick a number of books, movies, shows, anime, games or albums to finish in {row.year} and watch your progress fill up.</p></div>'
           + ('<a class="site-btn site-btn--primary" href="/#goals">Set a goal</a>' if signed_in
              else '<a class="site-btn site-btn--primary" href="/#signup">Start tracking free</a>')
           + '</section>')
    html = _page(
        title=f"{title} · OmniTrackr",
        description=f"{title} on OmniTrackr, the free tracker for movies, shows, anime, games, music and books.",
        canonical=canonical,
        card_url=f"{canonical}/card.png",
        eyebrow=f"Goal reached · {row.year}",
        heading=title,
        lead="Tracked on OmniTrackr, the free tracker for movies, shows, anime, games, music and books.",
        actions=(f'<button type="button" class="site-btn site-btn--ghost site-btn--sm" data-share '
                 f'data-share-title="{_e(title)}">Share</button>'),
        body=body + cta,
    )
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if signed_in else "public, max-age=300"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def render_goal_card(username: str, category: str, target: int, year: int) -> bytes:
    import io
    from PIL import Image, ImageDraw
    from .profiles import _fit, _font
    width, height = 1200, 630
    base = Image.new("RGB", (width, height), (11, 10, 24))
    glow = Image.new("RGB", (width, height), (11, 10, 24))
    glow_draw = ImageDraw.Draw(glow)
    for step in range(18, 0, -1):
        radius, mix = step * 34, (1 - step / 18) * 0.55
        shade = (int(11 + 20 * mix), int(10 + 160 * mix), int(24 + 140 * mix))
        glow_draw.ellipse((width - 160 - radius, -120 - radius, width - 160 + radius, -120 + radius), fill=shade)
    image = Image.blend(base, glow, 0.85)
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((40, 40, width - 40, height - 40), radius=28, outline=(60, 52, 110), width=2)
    draw.text((84, 78), f"OmniTrackr · {year} goal reached", font=_font(30, bold=True), fill=(94, 234, 212))
    name_font = _font(64, bold=True)
    draw.text((84, 140), _fit(draw, username, name_font, width - 168), font=name_font, fill=(245, 243, 255))
    singular, plural = goals.NOUNS.get(category, goals.NOUNS[goals.ALL])
    big = f"{target} {singular if target == 1 else plural}"
    big_font = _font(96, bold=True)
    draw.text((84, 236), _fit(draw, big, big_font, width - 168), font=big_font, fill=(245, 243, 255))
    draw.text((84, 352), f"{goals.VERBS.get(category, 'finished')} in {year}", font=_font(36), fill=(196, 181, 253))
    draw.rounded_rectangle((84, 420, width - 84, 444), radius=12, fill=(124, 58, 237))
    host = goals.SITE_URL.replace("https://", "").replace("http://", "")
    draw.text((84, height - 100), f"{host} · set your own goal", font=_font(24), fill=(167, 160, 199))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


@router.get("/goal/{token}/card.png", include_in_schema=False)
def shared_goal_card(token: str, request: Request, db: Session = Depends(get_db)):
    row, owner = _shared_or_404(db, token)
    key = (owner.id, f"goal:{row.year}:{row.category}:{row.target}:{owner.username}")
    png = _CARDS.get(key)
    if png is None:
        try:
            png = render_goal_card(owner.username, row.category, row.target, row.year)
        except Exception:
            raise HTTPException(status_code=404, detail="Card unavailable")
        _CARDS.put(key, png)
    return Response(content=png, media_type="image/png", headers={
        "Cache-Control": "public, max-age=3600", "X-Content-Type-Options": "nosniff",
    })
