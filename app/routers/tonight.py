"""Tonight polls (/tonight, /tonight/<token>): let friends vote on what to watch, play or read tonight."""
from __future__ import annotations

import hashlib
import json
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import affiliate, funnel, models, title_metadata, title_pages, tonight_card, tonight_polls, where_to_watch
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from ..visitor_identity import set_visitor_cookie, visitor_identity
from ..site_chrome import view_switch
from .discover import page

router = APIRouter(tags=["tonight"])
CSS_VERSION = "20261112-tonight-2"
JS_VERSION = "20261112-tonight-2"
GUEST_LIST_JS = "/static/guest-list.js?v=20261031-browse-1"
DESCRIPTION = ("Can't agree on what to watch tonight? Make a quick poll from your watchlist, send the link to the "
               "group chat and let everyone vote. Free, and friends don't need an account to vote.")
SITE_URL = tonight_polls.SITE_URL


def _e(value) -> str:
    # Braces too, so text from a member can never look like a page template placeholder.
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _fail(error: tonight_polls.PollError):
    raise HTTPException(error.status, str(error))


class PollOption(BaseModel):
    kind: Optional[str] = Field(None, max_length=10)
    title: Optional[str] = Field(None, max_length=200)
    year: Optional[int] = Field(None, ge=1800, le=2100)
    slug: Optional[str] = Field(None, max_length=140)
    category: Optional[str] = Field(None, max_length=20)
    item_id: Optional[PositiveDatabaseId] = None


class PollCreate(BaseModel):
    question: Optional[str] = Field(None, max_length=200)
    options: list[PollOption] = Field(..., min_length=1, max_length=tonight_polls.OPTIONS_MAX * 2)
    hours: int = Field(tonight_polls.DEFAULT_HOURS, ge=1, le=72)
    friend_ids: list[PositiveDatabaseId] = Field(default_factory=list, max_length=50)


class PollKeep(BaseModel):
    # The winner when left out.
    option_id: Optional[PositiveDatabaseId] = None
    queue: bool = False


class PollAgain(BaseModel):
    keep_winner: bool = False


class PollVote(BaseModel):
    option_id: PositiveDatabaseId
    name: Optional[str] = Field(None, max_length=60)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        return tonight_polls.clean_name(value)


# ------------------------------------------------------------------ pages

def _shell(title: str, path: str, content: str, *, member: bool, indexable: bool = False, structured_data=None,
           description: str = DESCRIPTION, share_image: Optional[str] = None, guest_list: bool = False):
    head = (f'<link rel="stylesheet" href="/static/tonight.css?v={CSS_VERSION}">'
            + (f'<script src="{GUEST_LIST_JS}" defer></script>' if guest_list else '')
            + f'<script src="/static/tonight.js?v={JS_VERSION}" defer></script>')
    title = title.replace("{", "(").replace("}", ")")
    description = description.replace("{", "(").replace("}", ")")
    response = page(title, description, path, content, indexable=indexable, head=head, member=member,
                    structured_data=structured_data, share_image=share_image)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


SAMPLE = (("Dune: Part Two", "Movie · 2024", 4), ("Paddington 2", "Movie · 2017", 2), ("Arrival", "Movie · 2016", 1))

GUIDE = (
    '<section class="tn-guide editorial" aria-labelledby="tnGuideTitle">'
    '<h2 id="tnGuideTitle">How to pick something everyone will actually enjoy</h2>'
    '<p>Group decisions stall for a simple reason: everyone is polite. Nobody wants to be the one who vetoes a '
    'friend\'s favorite, so the conversation goes in circles until it is too late to start anything long. A poll fixes '
    'that by turning "I don\'t mind, what do you want?" into a single tap.</p>'
    '<h3>Keep the shortlist short</h3>'
    '<p>Three or four options is the sweet spot. Two feels like a coin toss and turns into a debate, while eight '
    'brings back the scrolling problem you were trying to escape. Choose titles of a similar length, too: a two-hour '
    'movie and a ten-episode series are not really competing for the same evening.</p>'
    '<h3>Mix safe bets with one wildcard</h3>'
    '<p>Put in a couple of titles you know people like and one they have probably never heard of. The wildcard wins '
    'more often than you\'d think, and when it does, that\'s usually the night people remember. If you are stuck for '
    'one, <a href="/pick">Pick for me</a> suggests a title with a reason to try it.</p>'
    '<h3>Give it a deadline</h3>'
    '<p>An hour is plenty for tonight. For a weekend plan or a book club, give it a day or three so people who '
    'check their phone less often still get a say. When the time runs out, the title with the most votes wins, and a '
    'tie is settled by a random draw so nobody has to argue it out.</p>'
    '<h3>Make the result stick</h3>'
    '<p>When voting closes, the result page shows where the winner is streaming and has a button that puts it in '
    'your <strong>Next Up</strong> queue, so it doesn\'t get lost between the vote and the couch. If your group does '
    'this every week, a <a href="/lists">shared list</a> keeps a running shortlist that anyone can add to. A '
    '<a href="/lists">watch club</a> works better for longer picks like a season of TV or a book, where everyone '
    'finishes by a date and talks it over afterwards.</p>'
    '<h3>Run the losers back next week</h3>'
    '<p>The titles that lost were still good enough to make the shortlist. Whoever made the poll can start another '
    'round from the result page: the winner drops out, the rest go up for a new vote, and the link already sitting in '
    'the group chat points at the new round. After three or four weeks you have worked through the whole list without '
    'anyone having to build it again.</p></section>'
)


def _sample() -> str:
    total = sum(votes for _, _, votes in SAMPLE)
    rows = "".join(
        f'<li class="tn-sample__row{" tn-sample__row--top" if index == 0 else ""}">'
        f'<span class="tn-sample__title"><strong>{_e(title)}</strong><small>{_e(meta)}</small></span>'
        f'<span class="tn-bar" aria-hidden="true"><span style="--tn-share:{round(100 * votes / total)}%"></span></span>'
        f'<span class="tn-sample__votes">{votes} vote{"s" if votes != 1 else ""}</span></li>'
        for index, (title, meta, votes) in enumerate(SAMPLE))
    return ('<figure class="tn-sample" aria-label="An example poll">'
            '<p class="tn-sample__q">What should we watch tonight?</p>'
            f'<ul>{rows}</ul><figcaption>Seven votes in, Dune is winning. Closes in 40 min.</figcaption></figure>')


HOURS_LABELS = ((1, "1 hour"), (3, "3 hours"), (6, "6 hours"), (24, "1 day"), (72, "3 days"))
STEPS = ('<ol class="tn-steps">'
         '<li><strong>Pick a few titles</strong><span>Search for anything, or start from what\'s popular. Members can pull '
         'straight from their Next Up queue and library.</span></li>'
         '<li><strong>Send the link</strong><span>Drop it in the group chat. Friends vote in one tap, no account needed.</span></li>'
         '<li><strong>Press play</strong><span>Most votes wins when the time is up. Ties are settled by a random draw.</span></li></ol>')


def _form(guest: bool) -> str:
    hours = "".join(f'<option value="{value}"{" selected" if value == tonight_polls.DEFAULT_HOURS else ""}>{label}</option>'
                    for value, label in HOURS_LABELS)
    suggest = ('<p class="tn-muted">Loading popular titles…</p>' if guest
               else '<p class="tn-muted">Loading your Next Up and library…</p>')
    back = quote("/tonight", safe="")
    after = ('<button type="submit" class="button tn-make__go" disabled>Get the link</button>'
             '<p class="tn-make__note">Free. The link comes with a free account, which takes about a minute to make, and '
             f'your shortlist will be waiting when you\'re in. <a rel="nofollow" href="/?next={back}#login">I have an account</a></p>'
             if guest else
             '<div class="tn-friends" data-tonight-friends hidden></div>'
             '<button type="submit" class="button tn-make__go" disabled>Make the poll</button>')
    return (
        '<form class="tn-make" data-tonight-make>'
        '<div class="tn-make__head"><h2>New poll</h2>'
        '<p class="tn-muted" data-tonight-count>Pick 2 to 8 titles.</p></div>'
        '<p class="tn-draft" data-tonight-draft hidden></p>'
        '<label for="tnQuestion">Question <span class="tn-optional">(optional)</span></label>'
        '<input id="tnQuestion" name="question" type="text" maxlength="120" autocomplete="off" '
        'placeholder="What should we watch tonight?">'
        '<div class="tn-picked" data-tonight-picked aria-live="polite"></div>'
        '<fieldset class="tn-source"><legend>Add titles</legend>'
        f'<div class="tn-suggest" data-tonight-suggest>{suggest}</div>'
        '<label for="tnSearch">Or search for anything</label>'
        '<input id="tnSearch" type="search" maxlength="80" autocomplete="off" placeholder="Try a movie, show, game or book" '
        'aria-controls="tnResults">'
        '<ul class="tn-results" id="tnResults" data-tonight-results hidden></ul>'
        '<div class="tn-row tn-source__more">'
        '<button type="button" class="tn-link-button" data-tonight-fill>Pick four for me</button>'
        '<button type="button" class="tn-link-button" data-tonight-wildcard>Add a wildcard from Pick for me</button></div>'
        '</fieldset>'
        f'<div class="tn-make__row"><label for="tnHours">Voting closes in</label><select id="tnHours" name="hours">{hours}</select></div>'
        f'{after}<p class="tn-status" data-tonight-status role="status"></p></form>')


@router.get("/tonight", include_in_schema=False)
def tonight_page(user=Depends(get_optional_current_user)):
    if user is None:
        content = (
            '<header class="hero tn-hero">' + view_switch("pick", "tonight") + '<p class="eyebrow">GROUP POLL</p>'
            '<h1>What are we watching tonight?</h1>'
            '<p>Stop scrolling through menus while everyone says "I don\'t mind." Pick a few titles, send one link to '
            'the group chat and let everyone vote. It works for games, books and albums too.</p>'
            '<p class="tn-hero__try">Start below. You don\'t need an account to build the shortlist.</p></header>'
            '<section class="tn-app" id="tonightApp" data-view="make" data-guest="1">' + _form(True) +
            '<aside class="tn-preview" aria-labelledby="tnPreviewTitle">'
            '<h2 id="tnPreviewTitle">What your group sees</h2>'
            f'<div data-tonight-preview>{_sample()}</div>'
            '<p class="tn-muted">They open the link, tap a title and watch the bars move. Nobody has to sign up to vote.</p></aside>'
            '<noscript><p>Making a poll needs JavaScript.</p></noscript></section>'
            f'<section class="tn-intro tn-intro--steps" aria-label="How it works">{STEPS}</section>' + GUIDE)
        return _shell("Group poll: let friends vote on what to watch tonight", "/tonight", content, member=False,
                      indexable=True, structured_data={
                          "@context": "https://schema.org", "@type": "WebPage",
                          "name": "Group poll: what should we watch tonight?", "description": DESCRIPTION,
                          "url": "https://omnitrackr.xyz/tonight", "inLanguage": "en-US",
                          "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
                      })
    content = (
        '<header class="hero tn-hero">' + view_switch("pick", "tonight") + '<p class="eyebrow">GROUP POLL</p>'
        '<h1>What are we watching tonight?</h1>'
        '<p>Pick a few titles, send the link to whoever you\'re watching with, and let them vote. Friends without '
        'an account can vote too.</p></header>'
        '<section class="tn-app" id="tonightApp" data-view="make">' + _form(False) +
        '<section class="tn-mine" aria-labelledby="tnMineTitle"><h2 id="tnMineTitle">Your polls</h2>'
        '<div data-tonight-mine><p class="tn-muted">Loading…</p></div></section>'
        '<noscript><p>Making a poll needs JavaScript.</p></noscript></section>'
        + GUIDE
    )
    return _shell("Group poll", "/tonight", content, member=True, indexable=True)


def _option_html(option: dict, poll: dict) -> str:
    art = (f'<img src="{_e(option["image"])}" alt="" width="64" height="96" loading="lazy" referrerpolicy="no-referrer">'
           if option["image"] else f'<span class="tn-art__empty" aria-hidden="true">{_e(option["title"][:1].upper())}</span>')
    meta = " · ".join(str(part) for part in (option["label"], option["year"]) if part)
    won = poll["winner"] == option["id"]
    return (f'<li class="tn-option{" tn-option--won" if won else ""}" data-option-id="{option["id"]}">'
            f'<span class="tn-art">{art}</span>'
            f'<span class="tn-option__text"><strong>{_e(option["title"])}</strong><small>{_e(meta)}</small>'
            f'<span class="tn-bar" aria-hidden="true"><span style="--tn-share:{option["share"]}%"></span></span></span>'
            f'<span class="tn-option__votes">{option["votes"]} vote{"s" if option["votes"] != 1 else ""}</span></li>')


def _not_found():
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    response = strict_html_response(message_page(
        "Poll not found", "This poll isn't here anymore",
        "Whoever made it may have deleted it. Ask them for a new link, or make your own.",
        actions=(("Make a poll", "/tonight"), ("See what OmniTrackr does", "/about"))), status_code=404)
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


@router.get("/tonight/{token}", include_in_schema=False)
def poll_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    found = tonight_polls.by_token(db, token)
    if found is None:
        return _not_found()
    poll, owner = found
    visitor, new_token, _ = visitor_identity(request)
    data = tonight_polls.state(db, poll, owner, user, visitor)
    if user is not None:
        tonight_polls.mark_seen(db, poll, user)
    else:
        funnel.record("tonight_poll_link_opened", request)
    path = f"/tonight/{poll.token}"
    owner_name = "You" if data["owner"]["you"] else owner.username
    lead = (f'{_e(owner_name)} asked. ' if not data["owner"]["you"] else 'You asked. ') + (
        "Here's what won." if data["closed"] else "Tap the one you'd pick. You can change your mind until voting closes.")
    options = "".join(_option_html(option, data) for option in data["options"])
    nudge = ''
    if user is None:
        invite = db.query(models.FriendInvite).filter(models.FriendInvite.user_id == owner.id).first()
        back = quote(path, safe="")
        join = (f"/?invite={quote(invite.token)}&next={back}#signup" if invite is not None else f"/?next={back}#signup")
        nudge = (
            '<aside class="tn-nudge" data-tonight-nudge aria-labelledby="tnNudgeTitle">'
            '<p class="eyebrow">OMNITRACKR</p>'
            '<h2 id="tnNudgeTitle">Run the next movie night yourself</h2>'
            f'<p>OmniTrackr is a free tracker for the movies, shows, anime, games, books and music you love. Join and '
            f'you and {_e(owner.username)} become friends, your vote here moves to your account, and you can make polls '
            'like this one from your own watchlist.</p>'
            '<ul><li>Free, no credit card</li><li>Keep a Next Up queue so the winner doesn\'t get forgotten</li>'
            '<li>Import from Letterboxd, Goodreads, MyAnimeList and more</li></ul>'
            f'<div class="tn-nudge__actions"><a class="button" rel="nofollow" href="{_e(join)}" data-tonight-signup>Join free</a>'
            '<a class="button button--ghost" href="/tonight" data-tonight-own>Make your own poll</a>'
            f'<a class="tn-nudge__login" rel="nofollow" href="/?next={back}#login">I have an account</a></div></aside>')
    content = (
        f'<section class="tn-poll" id="tonightApp" data-view="poll" data-token="{_e(poll.token)}" '
        f'data-signed-in="{"1" if user is not None else "0"}">'
        f'<header class="tn-poll__head"><p class="eyebrow">GROUP POLL · {_e(data["closes_label"]).upper()}</p>'
        f'<h1 data-tonight-question>{_e(poll.question)}</h1><p class="tn-poll__lead">{lead}</p></header>'
        f'<div class="tn-board" data-tonight-board><ul class="tn-options">{options}</ul>'
        f'<p class="tn-muted">{data["total"]} vote{"s" if data["total"] != 1 else ""} so far.</p></div>'
        '<p class="tn-status" data-tonight-status role="status" aria-live="polite"></p>'
        '<noscript><p>Voting needs JavaScript.</p></noscript>'
        f'</section>{nudge}'
    )
    # The version changes when voting closes, so chat apps that kept the ballot fetch the result card.
    version = f"won{poll.winner_id}" if poll.winner_id else ("closed" if data["closed"] else "open")
    response = _shell(poll.question, path, content, member=user is not None,
                      description=tonight_polls.preview_line(poll, owner),
                      share_image=f"{SITE_URL}{path}/card.png?v={version}", guest_list=user is None)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Cache-Control"] = "private, no-store"
    set_visitor_cookie(response, new_token)
    return response


_CARDS = None


def _card_cache():
    global _CARDS
    if _CARDS is None:
        from .profiles import _CardCache
        _CARDS = _CardCache(size=96)
    return _CARDS


@router.get("/tonight/{token}/card.png", include_in_schema=False)
def poll_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The image chat apps show for the link: the ballot while voting is open, then the winner."""
    found = tonight_polls.by_token(db, token)
    if found is None:
        raise HTTPException(404, "This poll isn't here anymore")
    poll, owner = found
    tonight_polls.refresh(db, poll)
    facts = tonight_polls.card_facts(db, poll, owner)
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    etag = f'"{fingerprint}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _card_cache()
    png = cache.get((poll.id, fingerprint))
    if png is None:
        try:
            png = tonight_card.render(facts)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        cache.put((poll.id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)


# ------------------------------------------------------------------ API

@router.get("/api/tonight")
def my_polls(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return {"polls": tonight_polls.mine(db, user)}


@router.get("/api/tonight/suggestions")
def poll_suggestions(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Titles to start a poll from: Next Up first, then unfinished titles in the library."""
    _private(response)
    from ..crud.friends import get_friends
    friends = [{"id": friend.id, "username": friend.username} for friend in get_friends(db, user.id) if friend.is_active]
    return {"titles": tonight_polls.suggestions(db, user), "friends": friends[:50],
            "options_max": tonight_polls.OPTIONS_MAX, "hours": list(tonight_polls.HOURS)}


@router.get("/api/tonight/starters")
def poll_starters(request: Request, response: Response, db: Session = Depends(get_db)):
    """Popular titles a visitor can start a shortlist from. The same for everyone, so it can be cached."""
    response.headers["Cache-Control"] = "public, max-age=600"
    return {"titles": tonight_polls.starters(db), "options_max": tonight_polls.OPTIONS_MAX}


@router.post("/api/tonight", status_code=201)
def create_poll(payload: PollCreate, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    try:
        poll = tonight_polls.create(db, user, payload.question or "",
                                    [option.model_dump() for option in payload.options], payload.hours)
    except tonight_polls.PollError as error:
        _fail(error)
    asked = tonight_polls.notify_friends(db, poll, user, payload.friend_ids)
    db.commit()
    from .. import friend_invites
    friend_invites.link_for(db, user)  # Visitors who join from the poll become the owner's friend.
    funnel.record("tonight_poll_created", request)
    return {"token": poll.token, "url": tonight_polls.url_for(poll), "path": f"/tonight/{poll.token}",
            "question": poll.question, "asked": asked}


def _poll(db: Session, token: str):
    found = tonight_polls.by_token(db, token)
    if found is None:
        raise HTTPException(404, "This poll isn't here anymore")
    return found


@router.get("/api/tonight/{token}")
def get_poll(token: str, request: Request, response: Response,
             user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    _private(response)
    poll, owner = _poll(db, token)
    visitor, new_token, _ = visitor_identity(request)
    set_visitor_cookie(response, new_token)
    return tonight_polls.state(db, poll, owner, user, visitor)


@router.put("/api/tonight/{token}/vote")
def vote_poll(token: str, payload: PollVote, request: Request, response: Response,
              user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    """Vote, or change a vote. Members vote as themselves; visitors by their browser cookie."""
    _private(response)
    poll, owner = _poll(db, token)
    visitor, new_token, _ = visitor_identity(request)
    set_visitor_cookie(response, new_token)
    try:
        first = tonight_polls.vote(db, poll, user, visitor, payload.option_id, payload.name)
    except tonight_polls.PollError as error:
        _fail(error)
    if first:
        funnel.record("tonight_poll_voted" if user is not None else "tonight_poll_guest_voted", request)
    return tonight_polls.state(db, poll, owner, user, visitor)


@router.delete("/api/tonight/{token}/vote")
def unvote_poll(token: str, request: Request, response: Response,
                user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    _private(response)
    poll, owner = _poll(db, token)
    visitor, _, _ = visitor_identity(request)
    try:
        tonight_polls.unvote(db, poll, user, visitor)
    except tonight_polls.PollError as error:
        _fail(error)
    return tonight_polls.state(db, poll, owner, user, visitor)


@router.post("/api/tonight/{token}/close")
def close_poll(token: str, request: Request, response: Response,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    poll, owner = _poll(db, token)
    try:
        tonight_polls.close(db, poll, user)
    except tonight_polls.PollError as error:
        _fail(error)
    visitor, _, _ = visitor_identity(request)
    return tonight_polls.state(db, poll, owner, user, visitor)


@router.post("/api/tonight/{token}/again", status_code=201)
def another_round(token: str, payload: PollAgain, request: Request, response: Response,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Start the next round from a closed poll: the same titles, without the winner unless asked."""
    _private(response)
    poll, _ = _poll(db, token)
    try:
        fresh, made = tonight_polls.again(db, poll, user, payload.keep_winner)
    except tonight_polls.PollError as error:
        _fail(error)
    if made:
        funnel.record("tonight_poll_created", request)
        funnel.record("tonight_poll_next_round", request)
    else:
        response.status_code = 200
    return {"token": fresh.token, "url": tonight_polls.url_for(fresh), "path": f"/tonight/{fresh.token}",
            "question": fresh.question, "made": made}


@router.post("/api/tonight/{token}/keep")
def keep_title(token: str, payload: PollKeep, request: Request, response: Response,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Add the winner (or another title on the poll) to the member's library, and to Next Up when asked."""
    _private(response)
    poll, _ = _poll(db, token)
    tonight_polls.refresh(db, poll)
    if payload.option_id is None and poll.winner_id is None:
        raise HTTPException(409, "Nothing has won yet")
    try:
        result = tonight_polls.keep(db, poll, user, payload.option_id, payload.queue)
    except tonight_polls.PollError as error:
        _fail(error)
    if result["state"] == "created" or result["queued"]:
        funnel.record("tonight_poll_winner_kept", request)
    return result


@router.get("/api/tonight/{token}/where")
async def where_winner(token: str, request: Request, response: Response, db: Session = Depends(get_db)):
    """Where the winning title streams, sells or lends. Only for a closed poll, and only for its winner."""
    _private(response)
    # Finding the poll (and closing it if its time is up) talks to the database, so it runs off
    # the event loop like the lookups below do; otherwise every request waits behind it.
    kind, display, year = await run_in_threadpool(_winner_to_look_up, db, token)
    normalized = title_pages.normalize(display)
    if not normalized:
        raise HTTPException(404, "Nothing to look up")
    client = getattr(request.app.state, "external_api_client", None)
    metadata = await title_metadata.get_or_fetch(db, client, kind, normalized, display, year)
    where = await where_to_watch.get_or_fetch(db, client, kind, normalized, display, year, metadata, wait=6) or {}
    video = kind in where_to_watch.VIDEO_KINDS
    return {
        "kind": kind, "title": display, "heading": where_to_watch.heading(kind),
        "groups": where.get("groups") or [], "region": where.get("region"), "fetched": where.get("fetched"),
        "credits": where.get("credits") or [], "tmdb_notice": bool(where.get("justwatch")),
        "more": (where.get("link") or where_to_watch.justwatch_search(display)) if video else None,
        "buy": [{"name": link["merchant"], "url": link["url"]} for link in affiliate.links_for(kind, display)],
        "disclosure": affiliate.disclosure_text() if affiliate.affiliate_enabled() else None,
        "searches": where_to_watch.searches(kind, display),
    }


def _winner_to_look_up(db: Session, token: str) -> tuple[str, str, Optional[int]]:
    """(kind, title, year) of a closed poll's winner, or a 404."""
    poll, _ = _poll(db, token)
    tonight_polls.refresh(db, poll)
    winner = next((option for option in poll.options if option.id == poll.winner_id), None)
    if poll.closed_at is None or winner is None or winner.kind not in where_to_watch.KINDS:
        raise HTTPException(404, "Nothing has won yet")
    return winner.kind, " ".join(winner.title.split()), winner.year


@router.delete("/api/tonight/{token}", status_code=204)
def delete_poll(token: str, request: Request, user=Depends(get_current_user), db: Session = Depends(get_db)):
    poll, _ = _poll(db, token)
    try:
        tonight_polls.delete(db, poll, user)
    except tonight_polls.PollError as error:
        _fail(error)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})
