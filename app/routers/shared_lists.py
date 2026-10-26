"""Shared lists (/lists): build a watchlist or reading queue together with friends."""
from __future__ import annotations

from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from .. import funnel, models, shared_lists
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from ..progress import lock_progress_owner
from .discover import page

router = APIRouter(tags=["shared-lists"])
CSS_VERSION = "20261026-clubs-1"
JS_VERSION = "20261026-clubs-1"
DESCRIPTION = ("Build a watchlist, reading queue or backlog together with friends, or run it as a watch club: "
               "pick one title, finish it by a date and talk it over.")


def _e(value) -> str:
    # Braces too, so text from a member can never look like a page template placeholder.
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _fail(error: shared_lists.ListError):
    raise HTTPException(error.status, str(error))


def _clean(value: Optional[str]) -> Optional[str]:
    return " ".join(value.split()) if isinstance(value, str) else value


class ListCreate(BaseModel):
    name: str = Field(..., max_length=80)
    description: Optional[str] = Field(None, max_length=300)

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = _clean(value)
        if not value:
            raise ValueError("Give the list a name")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value):
        return _clean(value)


class ListUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=300)

    @field_validator("name")
    @classmethod
    def _name(cls, value):
        value = _clean(value)
        if value is not None and not value:
            raise ValueError("Give the list a name")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value):
        return _clean(value)


class LinkOptions(BaseModel):
    reset: bool = False


class MemberAdd(BaseModel):
    user_id: PositiveDatabaseId


class ItemAdd(BaseModel):
    kind: str = Field(..., max_length=10)
    title: str = Field("", max_length=200)
    year: Optional[int] = Field(None, ge=1800, le=2100)
    slug: Optional[str] = Field(None, max_length=140)
    note: Optional[str] = Field(None, max_length=200)

    @field_validator("note")
    @classmethod
    def _note(cls, value):
        return _clean(value)


class ItemUpdate(BaseModel):
    done: Optional[bool] = None
    note: Optional[str] = Field(None, max_length=200)

    @field_validator("note")
    @classmethod
    def _note(cls, value):
        return _clean(value)


class Vote(BaseModel):
    wanted: bool


# ------------------------------------------------------------------ pages

def _sign_in_page(path: str):
    """A page asking signed-out visitors to log in; its links bring them back to `path` afterwards."""
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    back = quote(path, safe="")
    response = strict_html_response(message_page(
        "Log in to see your shared lists", "Log in to see your shared lists",
        "Shared lists are lists you build with friends. Log in and you'll come straight back here.",
        actions=(("Log in", f"/?next={back}#login"), ("Create a free account", f"/?next={back}#signup"))))
    _private(response)
    response.headers["Vary"] = "Cookie"
    return response


def _shell(title: str, path: str, content: str, member: bool = True):
    head = (f'<link rel="stylesheet" href="/static/shared-lists.css?v={CSS_VERSION}">'
            f'<script src="/static/shared-lists.js?v={JS_VERSION}" defer></script>')
    # The shell fills {{...}} placeholders after the title goes in, so a member's braces stay out of it.
    title = title.replace("{", "(").replace("}", ")")
    response = page(title, DESCRIPTION, path, content, indexable=False, head=head, member=member)
    _private(response)
    response.headers["Vary"] = "Cookie"
    return response


@router.get("/lists", include_in_schema=False)
def lists_page(user=Depends(get_optional_current_user)):
    if user is None:
        return _sign_in_page("/lists")
    content = (
        '<header class="hero sl-hero"><p class="eyebrow">SHARED LISTS AND WATCH CLUBS</p>'
        '<h1>Lists you build together</h1>'
        '<p>A watchlist for the two of you, an anime queue for the group chat, a book club shortlist. Everyone adds '
        'titles, says which ones they\'re in for, and marks them done when you get to them.</p>'
        '<p class="sl-hero__club">Want a club? Pick one title from any list, set a finish-by date, and everyone '
        'checks in and talks it over once they\'re done. Spoilers stay hidden until you finish.</p></header>'
        '<section class="sl-app" id="sharedLists" data-view="index" aria-live="polite">'
        '<form class="sl-create" data-list-create>'
        '<h2>Start a list</h2>'
        '<label for="slName">Name</label>'
        '<input id="slName" name="name" type="text" maxlength="80" required autocomplete="off" '
        'placeholder="Friday movie night">'
        '<label for="slDescription">What it\'s for <span class="sl-optional">(optional)</span></label>'
        '<input id="slDescription" name="description" type="text" maxlength="300" autocomplete="off" '
        'placeholder="Stuff we both want to watch">'
        '<button type="submit" class="button">Create list</button>'
        '<p class="sl-status" data-list-status role="status"></p></form>'
        '<div class="sl-index" data-list-index><p class="sl-loading">Loading your lists…</p></div>'
        '<noscript><p>Shared lists need JavaScript.</p></noscript></section>'
    )
    return _shell("Shared lists", "/lists", content)


@router.get("/lists/{list_id}", include_in_schema=False)
def list_page(list_id: PositiveDatabaseId, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if user is None:
        return _sign_in_page(f"/lists/{list_id}")
    try:
        shared, _ = shared_lists.get_for_member(db, list_id, user)
    except shared_lists.ListError:
        from ..csp import strict_html_response
        from ..site_chrome import message_page
        response = strict_html_response(message_page(
            "List not found", "This list isn't here",
            "It may have been deleted, or you're not in it. Ask whoever made it for the list's link.",
            actions=(("My shared lists", "/lists"), ("Go to my library", "/"))), status_code=404)
        _private(response)
        return response
    content = (
        f'<section class="sl-app" id="sharedLists" data-view="list" data-list-id="{shared.id}" aria-live="polite">'
        f'<header class="sl-head"><h1 data-list-name>{_e(shared.name)}</h1></header>'
        '<p class="sl-loading">Loading the list…</p>'
        '<noscript><p>Shared lists need JavaScript.</p></noscript></section>'
    )
    return _shell(shared.name, f"/lists/{shared.id}", content)


def _preview_html(info: dict) -> str:
    covers = "".join(
        '<li class="sl-preview__item">'
        + (f'<img src="{_e(item["image"])}" alt="" loading="lazy" referrerpolicy="no-referrer">' if item["image"]
           else f'<span class="sl-poster-fallback" aria-hidden="true">{_e(item["title"][:1].upper())}</span>')
        + f'<strong>{_e(item["title"])}</strong>'
        f'<small>{_e(item["label"])}{" · " + _e(item["year"]) if item["year"] else ""}</small></li>'
        for item in info["items"])
    more = info["count"] - len(info["items"])
    titles = (f'<ul class="sl-preview__grid">{covers}</ul>'
              + (f'<p class="sl-muted">and {more} more.</p>' if more > 0 else '')) if covers else (
        '<p class="sl-muted">Nothing on it yet, so you can add the first title.</p>')
    people = ", ".join(_e(name) for name in info["members"])
    club = info.get("club")
    club_html = (f'<p class="sl-preview__club"><span>Club pick right now</span> <strong>{_e(club["title"])}</strong> '
                 f'<small>{_e(club["label"])} · finish by {_e(club["ends_label"])}</small></p>') if club else ''
    return (f'<div class="sl-preview">{club_html}<p class="sl-preview__who">In it so far: {people}</p>'
            + (f'<p class="sl-preview__about">{_e(info["description"])}</p>' if info["description"] else '')
            + titles + '</div>')


@router.get("/lists/join/{token}", include_in_schema=False)
def join_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    shared = shared_lists.by_token(db, token)
    if shared is None:
        from ..csp import strict_html_response
        from ..site_chrome import message_page
        response = strict_html_response(message_page(
            "List link expired", "This list link doesn't work anymore",
            "Whoever shared it may have made a new link. Ask them for the latest one.",
            actions=(("Start tracking for free", "/#signup"), ("See what OmniTrackr does", "/about"))), status_code=404)
        _private(response)
        response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response
    info = shared_lists.preview(db, shared)
    owner = info["owner"] or "A friend"
    member = user is not None and db.query(models.SharedListMember.id).filter_by(
        list_id=shared.id, user_id=user.id).first() is not None
    path = f"/lists/join/{shared.token}"
    if member:
        actions = f'<a class="button" href="/lists/{shared.id}">Open the list</a>'
    elif user is not None and info["full"]:
        actions = '<p class="sl-muted">This list is full. Ask whoever runs it to make room.</p>'
    elif user is not None:
        actions = (f'<button type="button" class="button" data-list-join data-token="{_e(shared.token)}">'
                   'Join this list</button><p class="sl-status" data-list-status role="status"></p>')
    else:
        funnel.record("shared_list_link_opened", request)
        next_path = quote(path, safe="")
        actions = (f'<a class="button" href="/?next={next_path}#signup">Sign up free to join</a>'
                   f'<a class="button button--ghost" href="/?next={next_path}#login">I have an account</a>'
                   '<p class="sl-muted sl-join__small">OmniTrackr is a free tracker for movies, shows, anime, games, '
                   'books and music. Once you\'re in, this link brings you straight back here.</p>')
    lead = (f'{_e(owner)} is building this list on OmniTrackr and wants you in on it. '
            'Add what you\'d like to watch, read or play, say which titles you\'re in for, and see what everyone '
            'else picked.')
    if info.get("club"):
        lead = (f'{_e(owner)} runs this as a watch club on OmniTrackr. Right now everyone is on '
                f'{_e(info["club"]["title"])}. Join, say how far you\'ve got, and talk it over when you finish. '
                'Spoilers stay hidden until you\'re done.')
    content = (
        '<section class="sl-join" id="sharedLists" data-view="join">'
        f'<p class="eyebrow">{_e(owner)} INVITED YOU</p>'
        f'<h1>Join “{_e(info["name"])}”</h1>'
        f'<p class="sl-join__lead">{lead}</p>'
        f'<div class="sl-join__actions">{actions}</div>'
        f'{_preview_html(info)}</section>'
    )
    response = _shell(f"Join {info['name']}", path, content, member=user is not None)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


# ------------------------------------------------------------------ API

@router.get("/api/lists")
def my_lists(response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return {"lists": shared_lists.overview(db, user), "owned_max": shared_lists.OWNED_MAX}


@router.post("/api/lists", status_code=201)
def create_list(payload: ListCreate, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    try:
        shared = shared_lists.create(db, user, payload.name, payload.description)
    except shared_lists.ListError as error:
        _fail(error)
    funnel.record("shared_list_created", request)
    return {"id": shared.id, "url": f"/lists/{shared.id}"}


def _member_list(db, list_id, user):
    try:
        return shared_lists.get_for_member(db, list_id, user)
    except shared_lists.ListError as error:
        _fail(error)


@router.get("/api/lists/{list_id}")
def get_list(list_id: PositiveDatabaseId, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, member = _member_list(db, list_id, user)
    return shared_lists.detail(db, shared, member, user)


@router.patch("/api/lists/{list_id}")
def update_list(list_id: PositiveDatabaseId, payload: ListUpdate, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, _ = _member_list(db, list_id, user)
    try:
        shared_lists.update(db, shared, user, payload.name, payload.description)
    except shared_lists.ListError as error:
        _fail(error)
    return {"name": shared.name, "description": shared.description or ""}


@router.delete("/api/lists/{list_id}", status_code=204)
def delete_list(list_id: PositiveDatabaseId, user=Depends(get_current_user), db: Session = Depends(get_db)):
    shared, _ = _member_list(db, list_id, user)
    try:
        shared_lists.delete(db, shared, user)
    except shared_lists.ListError as error:
        _fail(error)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.post("/api/lists/{list_id}/link")
def list_link(list_id: PositiveDatabaseId, response: Response, options: LinkOptions | None = None,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The list's join link. Anyone in the list can share it; only the owner can swap it for a new one."""
    _private(response)
    shared, _ = _member_list(db, list_id, user)
    if options and options.reset:
        try:
            shared_lists.reset_link(db, shared, user)
        except shared_lists.ListError as error:
            _fail(error)
    from .. import clubs
    club = clubs.summary(db, shared.id)
    if club:
        return {"url": shared_lists.join_url(shared),
                "text": f'Join our watch club "{shared.name}" on OmniTrackr. We\'re all on {club["title"]} '
                        f'until {club["ends_label"]}, then we talk it over.'}
    return {"url": shared_lists.join_url(shared),
            "text": f'Join our list "{shared.name}" on OmniTrackr. Add what you want to watch, read or play, '
                    "and we'll pick from it together."}


@router.get("/api/lists/{list_id}/friends")
def list_friends(list_id: PositiveDatabaseId, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """The member's friends who aren't in the list yet."""
    _private(response)
    shared, _ = _member_list(db, list_id, user)
    return {"friends": shared_lists.invitable_friends(db, shared, user)}


@router.post("/api/lists/{list_id}/members", status_code=201)
def add_member(list_id: PositiveDatabaseId, payload: MemberAdd, request: Request, response: Response,
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, _ = _member_list(db, list_id, user)
    try:
        friend = shared_lists.invite_friend(db, shared, user, payload.user_id)
    except shared_lists.ListError as error:
        _fail(error)
    return {"username": friend.username}


@router.delete("/api/lists/{list_id}/members/{member_id}", status_code=204)
def remove_member(list_id: PositiveDatabaseId, member_id: PositiveDatabaseId,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    shared, _ = _member_list(db, list_id, user)
    try:
        shared_lists.remove_member(db, shared, user, member_id)
    except shared_lists.ListError as error:
        _fail(error)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.post("/api/lists/join/{token}")
def join_list(token: str, request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared = shared_lists.by_token(db, token)
    if shared is None:
        raise HTTPException(404, "This list link doesn't work anymore. Ask for a new one.")
    try:
        joined = shared_lists.join(db, shared, user)
    except shared_lists.ListError as error:
        _fail(error)
    if joined:
        funnel.record("shared_list_joined", request)
    return {"id": shared.id, "url": f"/lists/{shared.id}", "joined": joined}


@router.post("/api/lists/{list_id}/items", status_code=201)
def add_item(list_id: PositiveDatabaseId, payload: ItemAdd, request: Request, response: Response,
             user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, _ = _member_list(db, list_id, user)
    try:
        state, item = shared_lists.add_item(db, shared, user, payload.kind, payload.title, payload.year,
                                            payload.slug, payload.note)
    except shared_lists.ListError as error:
        _fail(error)
    return {"state": state, "id": item.id, "title": item.title}


def _member_item(db, list_id, item_id, user):
    shared, _ = _member_list(db, list_id, user)
    try:
        return shared, shared_lists.get_item(db, shared, item_id)
    except shared_lists.ListError as error:
        _fail(error)


@router.patch("/api/lists/{list_id}/items/{item_id}")
def update_item(list_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: ItemUpdate, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    shared, item = _member_item(db, list_id, item_id, user)
    try:
        shared_lists.update_item(db, shared, user, item, payload.done, payload.note)
    except shared_lists.ListError as error:
        _fail(error)
    return {"done": item.done_at is not None, "note": item.note or ""}


@router.delete("/api/lists/{list_id}/items/{item_id}", status_code=204)
def remove_item(list_id: PositiveDatabaseId, item_id: PositiveDatabaseId,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    shared, item = _member_item(db, list_id, item_id, user)
    try:
        shared_lists.remove_item(db, shared, user, item)
    except shared_lists.ListError as error:
        _fail(error)
    return Response(status_code=204, headers={"Cache-Control": "private, no-store"})


@router.put("/api/lists/{list_id}/items/{item_id}/vote")
def vote_item(list_id: PositiveDatabaseId, item_id: PositiveDatabaseId, payload: Vote, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    _, item = _member_item(db, list_id, item_id, user)
    shared_lists.vote(db, item, user, payload.wanted)
    return {"wanted": payload.wanted}


@router.post("/api/lists/{list_id}/items/{item_id}/library")
def item_to_library(list_id: PositiveDatabaseId, item_id: PositiveDatabaseId, response: Response,
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Copy a title from the list into the member's own library (title, year and art only)."""
    _private(response)
    _, item = _member_item(db, list_id, item_id, user)
    lock_progress_owner(db, user.id)
    state, record = shared_lists.add_to_library(db, user, item)
    title = record.title
    db.commit()
    return {"state": state, "title": title}
