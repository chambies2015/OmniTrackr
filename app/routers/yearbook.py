"""The yearbook (/yearbook): friends sign your year with a note and a "most likely to" vote."""
from __future__ import annotations

import hashlib
import json
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from html import escape
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import funnel, models, yearbook
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from .discover import page

router = APIRouter(tags=["yearbook"])
CSS_VERSION = "20261125-yearbook-1"
JS_VERSION = "20261125-yearbook-1"
DESCRIPTION = ("Make a yearbook of your year in films, shows, books, games and music, send the link, and friends "
               "sign it with a note and a \"most likely to\" vote. Signing closes after New Year's Day. Free.")


def _e(value) -> str:
    # Braces too, so text from a member can never look like a page template placeholder.
    return escape(str(value if value is not None else ""), quote=True).replace("{", "&#123;").replace("}", "&#125;")


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _fail(error: yearbook.YearbookError):
    raise HTTPException(error.status, str(error))


def _person(request: Request) -> bool:
    from .tier_list import _person as person
    return person(request)


def _image(url) -> Optional[str]:
    from ..tier_list import image_allowed
    return url if url and image_allowed(url) else None


# ------------------------------------------------------------------ payloads

class Pick(BaseModel):
    category: str = Field(..., max_length=20)
    id: PositiveDatabaseId


class BookSave(BaseModel):
    year: Optional[int] = Field(None, ge=2026, le=2100)
    cover_name: str = Field(..., max_length=yearbook.COVER_MAX * 2)
    quote: Optional[str] = Field(None, max_length=yearbook.QUOTE_MAX * 2)
    picks: list[Pick] = Field(default_factory=list, max_length=12)
    show_numbers: bool = True
    listed: bool = False


class Signing(BaseModel):
    name: Optional[str] = Field(None, max_length=yearbook.GUEST_NAME_MAX * 2)
    note: str = Field(..., max_length=yearbook.NOTE_MAX * 2)
    superlative: Optional[str] = Field(None, max_length=24)
    website: Optional[str] = Field(None, max_length=200)  # left empty by people; filled by form bots


class Moderation(BaseModel):
    action: str = Field(..., max_length=10)


# ------------------------------------------------------------------ pages

def _shell(title: str, path: str, content: str, *, member: bool, indexable: bool = False, structured_data=None,
           description: str = DESCRIPTION, share_image: Optional[str] = None):
    head = (f'<link rel="stylesheet" href="/static/yearbook.css?v={CSS_VERSION}">'
            f'<script src="/static/yearbook.js?v={JS_VERSION}" defer></script>')
    title = title.replace("{", "(").replace("}", ")")
    description = description.replace("{", "(").replace("}", ")")
    response = page(title, description, path, content, indexable=indexable, head=head, member=member,
                    structured_data=structured_data, share_image=share_image)
    response.headers["Cache-Control"] = "private, no-cache"
    response.headers["Vary"] = "Cookie"
    return response


def _message(title: str, heading: str, message: str, actions, status: int = 404):
    from ..csp import strict_html_response
    from ..site_chrome import message_page
    response = strict_html_response(message_page(title, heading, message, actions=actions), status_code=status)
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _note_html(note: dict) -> str:
    vote = (f'<p class="yb-note__vote"><span aria-hidden="true">★</span> {_e(note["superlative"])}</p>'
            if note.get("superlative") else "")
    who = _e(note["name"])
    body = "".join(f"<p>{_e(line)}</p>" for line in (note.get("note") or "").split("\n") if line.strip())
    return (f'<li class="yb-note"><div class="yb-note__body">{body}</div>{vote}'
            f'<p class="yb-note__by">{who}<span class="yb-note__when">{_e(note.get("when") or "")}</span></p></li>')


SAMPLE_NOTES = (
    {"name": "Priya", "note": "You made me watch Frieren in March and I still haven't recovered. Same time next year?",
     "superlative": yearbook.SUPERLATIVE_LABEL["best_recs"], "when": "December 3"},
    {"name": "Sam", "note": "Four rewatches of Parks and Rec this year. Four. I counted on your profile.",
     "superlative": yearbook.SUPERLATIVE_LABEL["comfort_rewatch"], "when": "December 9"},
    {"name": "Jo", "note": "Thanks for the book club. Sorry I never finished the Brontë one.",
     "superlative": None, "when": "December 14"},
)


def _sample() -> str:
    """A static picture of a yearbook for visitors: the cover, two votes and three notes."""
    notes = "".join(_note_html(note) for note in SAMPLE_NOTES)
    return (
        '<figure class="yb-sample" aria-label="An example yearbook with three notes">'
        '<div class="yb-cover yb-cover--sample"><p class="yb-cover__class">Class of 2026</p>'
        '<p class="yb-cover__name">Maya</p>'
        '<blockquote class="yb-cover__quote">"I\'ll start it after this episode."</blockquote>'
        '<ul class="yb-tally yb-tally--sample"><li><strong>2 votes</strong> Most likely to recommend something you end '
        'up loving</li><li><strong>1 vote</strong> Most likely to rewatch the same comfort show again</li></ul></div>'
        f'<ul class="yb-notes__wall yb-notes__wall--sample">{notes}</ul>'
        '<figcaption>Three friends signed in the first two weeks of December. Maya let each note in before it showed.'
        '</figcaption></figure>')


STEPS = ('<ol class="yb-steps">'
         '<li><strong>Make your page</strong><span>Put a name on the cover, write a yearbook quote and pick up to four '
         'titles from your year.</span></li>'
         '<li><strong>Send the link</strong><span>Post it in the group chat or on your story. Nobody needs an account '
         'to sign.</span></li>'
         '<li><strong>Friends sign it</strong><span>Each person writes a short note and can vote you "most likely to" '
         'something.</span></li>'
         '<li><strong>Read it on New Year\'s Day</strong><span>Signing closes after January 1. The book stays on your '
         'link to read again next December.</span></li></ol>')


def _votes_html() -> str:
    items = "".join(f"<li>{_e(label)}</li>" for _key, label in yearbook.SUPERLATIVES)
    return f'<ul class="yb-vote-list">{items}</ul>'


def _guide(year: int) -> str:
    closes = yearbook.closes_label(year)
    return (
        '<section class="yb-guide editorial" aria-labelledby="ybGuideTitle">'
        '<h2 id="ybGuideTitle">How an OmniTrackr yearbook works</h2>'
        '<p>School yearbooks got signed in the last week of term: a line from everyone you sat near, a joke only the '
        'two of you got, and a "stay cool" from someone you barely knew. This is the same thing for the year you just '
        'spent watching, reading, playing and listening. Your page shows the titles you picked and, if you like, how '
        'many films, shows, books and games you finished. Everyone you send it to adds a note underneath.</p>'
        '<h3>Who can sign</h3>'
        '<p>Anyone with the link. Friends on OmniTrackr show up as soon as they sign. Notes from anyone else, including '
        'people without an account, wait until you let them in, so a link that gets forwarded around can\'t put '
        'something on your page you haven\'t read. Links, email addresses and phone numbers are never allowed in a '
        'note, and you can hide or delete any note at any time.</p>'
        '<h3>The "most likely to" votes</h3>'
        '<p>Each person who signs can also cast one vote from this list. The top three show near your cover, with how '
        'many people picked each one.</p>'
        + _votes_html() +
        '<p>They\'re all friendly on purpose. The page belongs to the person who gets voted, and it\'s the kind of '
        'thing people send to their family.</p>'
        '<h3>Writing a good note</h3>'
        '<p>The best yearbook notes are specific. "Have a great year" is fine, but "you got me to finish Baldur\'s '
        'Gate 3 and I will never forgive you" is the one they screenshot. Mention something you watched together, a '
        'recommendation that landed, an argument about an ending, or the show they still haven\'t finished. You have '
        f'{yearbook.NOTE_MAX} characters. Two sentences is plenty.</p>'
        '<h3>When it closes</h3>'
        f'<p>Signing stays open until the end of {closes}. After that the notes can\'t change and nobody new can sign, '
        'and the owner gets one email with everything that came in. The page stays up on the same link for as long as '
        'they keep it on, so it\'s still there to read next December.</p>'
        '<h3>Questions people ask</h3>'
        '<dl class="yb-faq">'
        '<dt>Do my friends need an account to sign?</dt><dd>No. They type their name and a note. If they have an '
        'account, signing while logged in puts their username on the note and lets them change it until signing '
        'closes.</dd>'
        '<dt>What from my library shows on the page?</dt><dd>Only what you choose: the titles you pick for the cover '
        'and, if you leave it on, how many titles you finished in the year. Both come only from shelves you show in '
        'your library and haven\'t made private. Scores, notes, reviews and the rest of your library never appear.</dd>'
        '<dt>Can I see who opened my link?</dt><dd>No. The page counts how many times someone other than you opened '
        'it, and that\'s all.</dd>'
        '<dt>Can I turn it off?</dt><dd>Yes. Turning the link off hides the page straight away. Turning it back on '
        'makes a new link, and the notes are still there.</dd></dl>'
        '</section>')


def _year_or_404(year: Optional[int]) -> int:
    year = year or yearbook.current_year() or max(yearbook.EDITIONS)
    if year not in yearbook.EDITIONS:
        raise HTTPException(404, "There's no yearbook for that year.")
    return year


@router.get("/yearbook", include_in_schema=False)
def yearbook_page(request: Request, user=Depends(get_optional_current_user)):
    year = _year_or_404(None)
    current = yearbook.state_of(year)
    title = f"Yearbook {year}: friends sign your year in films, shows, books and games"
    if user is None:
        back = quote("/yearbook", safe="")
        if current == "soon":
            lead_extra = f' Yearbooks open on {_e(yearbook._day(yearbook.opens_on(year)))}.'
        elif current == "closed":
            lead_extra = f' Signing for {year} is closed. Yearbooks come back next December.'
        else:
            lead_extra = f' Signing closes after {_e(yearbook.closes_label(year))}.'
        content = (
            f'<header class="hero yb-hero"><p class="eyebrow">YEARBOOK · CLASS OF {year}</p>'
            '<h1>Get your friends to sign your year</h1>'
            '<p>Make a yearbook page with the films, shows, books and games that made your year, and send the link. '
            'Friends sign it with a short note and vote you "most likely to" something.'
            f'{lead_extra}</p>'
            f'<div class="yb-hero__actions"><a class="button" rel="nofollow" href="/?next={back}#signup" '
            'data-yearbook-signup>Make my yearbook free</a>'
            f'<a class="button button--ghost" rel="nofollow" href="/?next={back}#login">I have an account</a></div>'
            '</header>'
            f'<section class="yb-intro" aria-label="What a yearbook looks like">{_sample()}'
            f'<div class="yb-intro__steps">{STEPS}</div></section>'
            + _guide(year))
        return _shell(title, "/yearbook", content, member=False, indexable=True, structured_data={
            "@context": "https://schema.org", "@type": "WebPage", "name": title, "description": DESCRIPTION,
            "url": "https://omnitrackr.xyz/yearbook", "inLanguage": "en-US",
            "publisher": {"@type": "Organization", "name": "OmniTrackr", "url": "https://omnitrackr.xyz/"},
        })
    if request.query_params.get("utm_campaign") == "yearbook" and request.query_params.get("utm_source") == "email":
        funnel.record("yearbook_back_from_email", request)
    content = (
        f'<header class="hero yb-hero yb-hero--member"><p class="eyebrow">YEARBOOK · CLASS OF {year}</p>'
        f'<h1>Your {year} yearbook</h1>'
        '<p>Put your year on a page, send the link, and read what people write. Friends\' notes show straight away; '
        'everyone else\'s waits for you.</p></header>'
        f'<section class="yb-app" id="yearbookApp" data-view="mine" data-year="{year}">'
        '<div data-yearbook-body><p class="yb-muted" role="status">Loading your yearbook…</p></div>'
        '<noscript><p>The yearbook needs JavaScript.</p></noscript></section>'
        + _guide(year)
    )
    return _shell(f"Your {year} yearbook", "/yearbook", content, member=True, indexable=True)


@router.get("/yearbook/class/{year}", include_in_schema=False)
def class_page(year: int, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if year not in yearbook.EDITIONS:
        return _message("Not found", "There's no class page for that year",
                        "Yearbooks started in 2026.", (("Yearbook", "/yearbook"),))
    path = f"/yearbook/class/{year}"
    if user is None:
        back = quote(path, safe="")
        return _message("Log in to see the class page", "The class page is for members",
                        "Members who list their yearbook show up here so other members can sign it. Log in and you'll "
                        "come straight back.",
                        (("Log in", f"/?next={back}#login"), ("Create a free account", f"/?next={back}#signup")),
                        status=200)
    books = yearbook.class_page(db, year)
    if books:
        items = "".join(
            f'<li class="yb-class__item"><a href="{_e(entry["path"])}"><strong>{_e(entry["cover"])}</strong>'
            + (f'<span class="yb-class__quote">"{_e(entry["quote"])}"</span>' if entry["quote"] else "")
            + f'<span class="yb-class__count">{_e(yearbook._plural(entry["notes"], "note"))}</span></a></li>'
            for entry in books)
        body = f'<ul class="yb-class">{items}</ul>'
    else:
        body = ('<p class="yb-muted">Nobody has listed their yearbook yet. Tick "List it on the class page" on yours '
                'and you\'ll be first.</p>')
    content = (
        f'<section class="yb-app yb-class-page" data-view="class">'
        '<p class="yb-back"><a href="/yearbook">← Your yearbook</a></p>'
        f'<header class="yb-class-page__head"><p class="eyebrow">YEARBOOK · CLASS OF {year}</p>'
        f'<h1>The class of {year}</h1>'
        '<p>Members who chose to list their yearbook here. Sign one and say what you\'ve been watching. Notes from '
        'people who aren\'t their friends wait for them to let in.</p></header>'
        f'{body}</section>')
    response = _shell(f"The class of {year}", path, content, member=True)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    _private(response)
    return response


def _picks_html(picks: list[dict]) -> str:
    if not picks:
        return ""
    tiles = []
    for pick in picks:
        image = _image(pick.get("image"))
        art = (f'<img src="{_e(image)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
               'width="120" height="180">' if image else
               f'<span class="yb-pick__blank" aria-hidden="true">{_e((pick["title"] or "?")[:1].upper())}</span>')
        facts = " · ".join(str(part) for part in (pick.get("format"), pick.get("year")) if part)
        title = _e(pick["title"])
        if pick.get("url"):
            title = f'<a href="{_e(pick["url"])}">{title}</a>'
        tiles.append(f'<li class="yb-pick"><span class="yb-pick__art">{art}</span>'
                     f'<span class="yb-pick__title">{title}</span><span class="yb-pick__facts">{_e(facts)}</span></li>')
    return ('<section class="yb-picks" aria-labelledby="ybPicksTitle"><h2 id="ybPicksTitle">Picks of the year</h2>'
            f'<ul class="yb-picks__grid">{"".join(tiles)}</ul></section>')


def _numbers_html(numbers: Optional[dict], year: int) -> str:
    if not numbers or not numbers.get("total"):
        return ""
    chips = "".join(f'<li>{_e(shelf["label"])}</li>' for shelf in numbers["shelves"][:6])
    return ('<section class="yb-numbers" aria-labelledby="ybNumbersTitle">'
            f'<h2 id="ybNumbersTitle">{_e(yearbook._plural(numbers["total"], "title"))} finished in {year}</h2>'
            f'<ul class="yb-numbers__list">{chips}</ul></section>')


def _tally_html(tally: list[dict]) -> str:
    if not tally:
        return ""
    items = "".join(f'<li><strong>{_e(yearbook._plural(entry["votes"], "vote"))}</strong> {_e(entry["label"])}</li>'
                    for entry in tally)
    return f'<ul class="yb-tally" aria-label="Most likely to, as voted by the people who signed">{items}</ul>'


def _vote_choices(chosen: str = "") -> str:
    options = [('', "No vote")] + list(yearbook.SUPERLATIVES)
    return "".join(
        f'<label class="yb-vote"><input type="radio" name="superlative" value="{_e(key)}"'
        f'{" checked" if key == chosen else ""}><span>{_e(label)}</span></label>'
        for key, label in options)


def _sign_html(book, info: dict, user, path: str) -> str:
    cover = _e(info["cover_name"])
    if info["is_owner"]:
        return ('<section class="yb-sign yb-sign--owner" id="sign"><h2>This is your yearbook</h2>'
                '<p>This is what people see when they open your link. Notes waiting for you, and the ones you hid, '
                'are on your yearbook page.</p>'
                '<p class="yb-row"><a class="button" href="/yearbook#waiting">Manage notes</a>'
                '<a class="button button--ghost" href="/yearbook#share">Share the link</a></p></section>')
    if info["state"] != "open":
        own = ""
        if info["own"]:
            own = '<p class="yb-muted">You signed this one. Thanks for that.</p>'
        return (f'<section class="yb-sign yb-sign--closed" id="sign"><h2>Signing is closed</h2>'
                f'<p>Signing closed after New Year\'s Day. {own}</p>'
                '<p class="yb-row"><a class="button" href="/yearbook" data-yearbook-signup>See how yearbooks work</a>'
                '</p></section>')
    own = info["own"]
    if user is not None:
        who = (f'<p class="yb-sign__who">Signing as <strong>{_e(user.username)}</strong>. Your username shows next to '
               'your note, and you can change it until signing closes.</p>')
        name_field = ""
        heading = "Change your note" if own else f"Sign {cover}'s yearbook"
        state_line = ""
        if own:
            if own["status"] == "shown":
                state_line = '<p class="yb-sign__state">Your note is in the yearbook.</p>'
            elif own["status"] == "waiting":
                state_line = (f'<p class="yb-sign__state">Your note is waiting for {cover} to let it in. '
                              'Friends\' notes show straight away; everyone else\'s waits.</p>')
            else:
                state_line = f'<p class="yb-sign__state">Only you and {cover} can see your note.</p>'
    else:
        back = quote(path, safe="")
        who = (f'<p class="yb-sign__who">No account needed. {cover} reads each note before it shows here. '
               f'<a href="/?next={back}#login" rel="nofollow">Log in</a> to sign with your username instead.</p>')
        name_field = (f'<div class="yb-field"><label for="ybName">Your name</label>'
                      f'<input id="ybName" name="name" type="text" maxlength="{yearbook.GUEST_NAME_MAX}" required '
                      'autocomplete="nickname" placeholder="So they know who wrote it"></div>')
        heading = f"Sign {cover}'s yearbook"
        state_line = ""
    note_value = _e(own["note"]) if own else ""
    remove = ('<button class="yb-link-button" type="button" data-yearbook-unsign>Take my note back</button>'
              if own else "")
    return (
        f'<section class="yb-sign" id="sign" aria-labelledby="ybSignTitle"><h2 id="ybSignTitle">{heading}</h2>'
        f'{who}{state_line}'
        f'<form class="yb-sign__form" data-yearbook-sign data-token="{_e(book.token)}" novalidate>'
        f'{name_field}'
        '<div class="yb-field"><label for="ybNote">Your note</label>'
        f'<textarea id="ybNote" name="note" rows="4" maxlength="{yearbook.NOTE_MAX}" required '
        'placeholder="Something you watched together, a pick that landed, the show they still haven\'t finished">'
        f'{note_value}</textarea>'
        f'<p class="yb-hint"><span data-yearbook-count>0</span>/{yearbook.NOTE_MAX}. Links, email addresses and phone '
        'numbers aren\'t allowed.</p></div>'
        f'<fieldset class="yb-field yb-votes"><legend>Vote {cover} most likely to… <span class="yb-muted">(optional)'
        f'</span></legend><div class="yb-votes__list">{_vote_choices(own["superlative"] if own else "")}</div></fieldset>'
        '<div class="yb-trap" aria-hidden="true"><label for="ybWebsite">Leave this empty</label>'
        '<input id="ybWebsite" name="website" type="text" tabindex="-1" autocomplete="off"></div>'
        f'<div class="yb-row"><button class="button" type="submit">{"Save my note" if own else "Sign the yearbook"}'
        f'</button>{remove}</div>'
        '<p class="yb-status" data-yearbook-status role="status" aria-live="polite"></p>'
        '</form><noscript><p>Signing needs JavaScript.</p></noscript></section>')


@router.get("/yearbook/{token}", include_in_schema=False)
def book_page(token: str, request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    book = yearbook.by_token(db, token)
    if book is None:
        return _message("Link not working", "This yearbook isn't here",
                        "Whoever sent it may have turned the link off or made a new one. Ask them for the latest link, "
                        "or make your own yearbook.",
                        (("Make my yearbook", "/yearbook"), ("See what OmniTrackr does", "/about")))
    info = yearbook.view(db, book, user)
    path = yearbook.path_for(book)
    if not info["is_owner"] and _person(request):
        db.query(models.Yearbook).filter(models.Yearbook.id == book.id).update(
            {models.Yearbook.opened: models.Yearbook.opened + 1}, synchronize_session=False)
        db.commit()
        if user is None:
            funnel.record("yearbook_link_opened", request)
    year = book.year
    cover = _e(info["cover_name"])
    quote_line = f'<blockquote class="yb-cover__quote">"{_e(info["quote"])}"</blockquote>' if info["quote"] else ""
    if info["state"] == "open":
        status = f'{_e(yearbook._plural(info["count"], "note"))} so far · Signing closes after {_e(info["closes"])}'
        go = '' if info["is_owner"] else '<a class="button yb-cover__go" href="#sign">Sign it</a>'
    else:
        status = f'{_e(yearbook._plural(info["count"], "note"))} · Signing closed after New Year\'s Day'
        go = ''
    notes = "".join(_note_html(note) for note in info["notes"])
    if notes:
        wall = f'<ul class="yb-notes__wall">{notes}</ul>'
    else:
        wall = (f'<p class="yb-muted yb-notes__empty">No notes yet. Be the first to sign {cover}\'s yearbook.</p>'
                if info["state"] == "open" else '<p class="yb-muted yb-notes__empty">Nobody signed this one.</p>')
    own_cta = ""
    if not info["is_owner"]:
        back = quote("/yearbook", safe="")
        href = "/yearbook" if user is not None else f"/?next={back}#signup"
        own_cta = ('<section class="yb-own" aria-labelledby="ybOwnTitle"><h2 id="ybOwnTitle">Want one of these?</h2>'
                   '<p>Make your own yearbook from the films, shows, books and games in your year, and send the link to '
                   'the people you\'d want to sign it. OmniTrackr is a free tracker for all of them.</p>'
                   f'<p class="yb-row"><a class="button" href="{_e(href)}" rel="nofollow" data-yearbook-signup>'
                   'Make my yearbook</a></p></section>')
    content = (
        f'<article class="yb-book" id="yearbookApp" data-view="book" data-state="{_e(info["state"])}">'
        f'<header class="yb-cover"><p class="yb-cover__class">Class of {year}</p>'
        f'<h1 class="yb-cover__name">{cover}</h1><p class="yb-cover__kind">Yearbook</p>{quote_line}'
        f'{_tally_html(info["tally"])}'
        f'<p class="yb-cover__status">{status}</p>{go}</header>'
        f'{_picks_html(info["picks"])}{_numbers_html(info["numbers"], year)}'
        f'<section class="yb-notes" id="notes" aria-labelledby="ybNotesTitle"><h2 id="ybNotesTitle">Signed by</h2>'
        f'{wall}</section>'
        f'{_sign_html(book, info, user, path)}{own_cta}</article>')
    facts = yearbook.card_facts(db, book)
    version = hashlib.sha256(json.dumps(facts, sort_keys=True).encode()).hexdigest()[:10]
    from ..digest import app_url
    description = (f"Sign {info['cover_name']}'s {year} yearbook: leave a note about the year and vote them "
                   "\"most likely to\" something.")
    response = _shell(f"Sign {info['cover_name']}'s {year} yearbook", path, content, member=user is not None,
                      description=description, share_image=f"{app_url()}{path}/card.png?v={version}")
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    _private(response)
    return response


_CARDS = None


def _card_cache():
    global _CARDS
    if _CARDS is None:
        from .profiles import _CardCache
        _CARDS = _CardCache(size=96)
    return _CARDS


@router.get("/yearbook/{token}/card.png", include_in_schema=False)
def book_card(token: str, request: Request, db: Session = Depends(get_db)):
    """The image chat apps show for a yearbook link."""
    book = yearbook.by_token(db, token)
    if book is None:
        raise HTTPException(404, "This link doesn't work anymore")
    facts = yearbook.card_facts(db, book)
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    etag = f'"{fingerprint}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _card_cache()
    png = cache.get(("yearbook", book.id, fingerprint))
    if png is None:
        from .. import yearbook_card
        try:
            png = yearbook_card.render(facts)
        except Exception:
            raise HTTPException(404, "Card unavailable")
        cache.put(("yearbook", book.id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)


@router.get("/yearbook/{token}/story.png", include_in_schema=False)
def book_story(token: str, request: Request, db: Session = Depends(get_db)):
    """The 1080x1920 picture an owner saves for a story."""
    book = yearbook.by_token(db, token)
    if book is None:
        raise HTTPException(404, "This link doesn't work anymore")
    facts = yearbook.card_facts(db, book)
    fingerprint = hashlib.sha256(json.dumps(facts, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    etag = f'"s{fingerprint}"'
    headers = {"Cache-Control": "private, max-age=300", "ETag": etag, "X-Content-Type-Options": "nosniff",
               "X-Robots-Tag": "noindex"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    cache = _card_cache()
    png = cache.get(("yearbook-story", book.id, fingerprint))
    if png is None:
        from .. import yearbook_card
        try:
            png = yearbook_card.render_story(facts)
        except Exception:
            raise HTTPException(404, "Picture unavailable")
        cache.put(("yearbook-story", book.id, fingerprint), png)
    return Response(content=png, media_type="image/png", headers=headers)


# ------------------------------------------------------------------ API

def _own_book(db: Session, user, year: int) -> models.Yearbook:
    book = yearbook.get(db, user.id, year)
    if book is None:
        raise HTTPException(404, "You haven't made a yearbook yet.")
    return book


@router.get("/api/yearbook")
def my_yearbook(request: Request, response: Response, year: Optional[int] = Query(None, ge=2026, le=2100),
                seen: bool = False, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    year = _year_or_404(year)
    data = yearbook.mine(db, user, year, seen=seen)
    if seen:
        db.commit()
    return data


@router.put("/api/yearbook")
def save_yearbook(payload: BookSave, request: Request, response: Response, user=Depends(get_current_user),
                  db: Session = Depends(get_db)):
    _private(response)
    year = _year_or_404(payload.year)
    try:
        _book, made = yearbook.save(db, user, year, cover_name=payload.cover_name, quote=payload.quote,
                                    picks=[pick.model_dump() for pick in payload.picks],
                                    show_numbers=payload.show_numbers, listed=payload.listed)
    except yearbook.YearbookError as error:
        db.rollback()
        _fail(error)
    db.commit()
    if made:
        funnel.record("yearbook_started", request)
    return {"made": made, **yearbook.mine(db, user, year)}


@router.post("/api/yearbook/link")
def reset_link(request: Request, response: Response, year: Optional[int] = Query(None, ge=2026, le=2100),
               user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Turn the link on, or swap it for a new one. The old link stops working; notes stay."""
    _private(response)
    year = _year_or_404(year)
    book = _own_book(db, user, year)
    url = yearbook.new_link(db, book)
    db.commit()
    return {"url": url, "path": yearbook.path_for(book)}


@router.delete("/api/yearbook/link")
def turn_off_link(request: Request, response: Response, year: Optional[int] = Query(None, ge=2026, le=2100),
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    year = _year_or_404(year)
    book = _own_book(db, user, year)
    yearbook.link_off(db, book)
    db.commit()
    return {"url": None}


@router.patch("/api/yearbook/notes/{note_id}")
def moderate_note(note_id: PositiveDatabaseId, payload: Moderation, request: Request, response: Response,
                  year: Optional[int] = Query(None, ge=2026, le=2100), user=Depends(get_current_user),
                  db: Session = Depends(get_db)):
    _private(response)
    year = _year_or_404(year)
    book = _own_book(db, user, year)
    if payload.action not in ("show", "hide"):
        raise HTTPException(422, "Unknown action.")
    before = db.query(models.YearbookSignature.status).filter_by(id=note_id, yearbook_id=book.id).scalar()
    try:
        status = yearbook.moderate(db, book, note_id, payload.action)
    except yearbook.YearbookError as error:
        _fail(error)
    db.commit()
    if before == "waiting" and status == "shown":
        funnel.record("yearbook_let_in", request)
    return {"status": status}


@router.delete("/api/yearbook/notes/{note_id}")
def delete_note(note_id: PositiveDatabaseId, request: Request, response: Response,
                year: Optional[int] = Query(None, ge=2026, le=2100), user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    year = _year_or_404(year)
    book = _own_book(db, user, year)
    try:
        yearbook.moderate(db, book, note_id, "delete")
    except yearbook.YearbookError as error:
        _fail(error)
    db.commit()
    return {"deleted": True}


@router.get("/api/yearbook/home")
def home_card(request: Request, response: Response, user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    return yearbook.home(db, user)


@router.post("/api/yearbook/sign/{token}")
def sign_book(token: str, payload: Signing, request: Request, response: Response,
              user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    _private(response)
    book = yearbook.by_token(db, token)
    if book is None:
        raise HTTPException(404, "This yearbook's link doesn't work anymore.")
    if (payload.website or "").strip():
        # Form bots fill every box. Answer like a guest note so they learn nothing, and keep nothing.
        return {"status": "waiting", "new": True}
    from ..visitor_identity import client_address
    try:
        sig, new = yearbook.sign(db, book, user=user, guest_name=payload.name, note=payload.note,
                                 superlative=payload.superlative, address=client_address(request))
    except yearbook.YearbookError as error:
        db.rollback()
        _fail(error)
    status = sig.status
    db.commit()
    if new:
        funnel.record("yearbook_signed" if user is not None else "yearbook_signed_guest", request)
    return {"status": status, "new": new}


@router.delete("/api/yearbook/sign/{token}")
def unsign_book(token: str, request: Request, response: Response, user=Depends(get_current_user),
                db: Session = Depends(get_db)):
    _private(response)
    book = yearbook.by_token(db, token)
    if book is None:
        raise HTTPException(404, "This yearbook's link doesn't work anymore.")
    try:
        removed = yearbook.unsign(db, book, user)
    except yearbook.YearbookError as error:
        _fail(error)
    db.commit()
    return {"removed": removed}
