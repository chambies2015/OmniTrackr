"""Gift supporter memberships: the page for buying one, the gift itself at /gift/<code>, the giver's
private card page, and the site owner's gift tools (see app/gift_memberships.py)."""
from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import gift_memberships as gifts, models, support_asks, supporters
from ..admin_access import is_site_admin
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from ..site_chrome import message_page

router = APIRouter(tags=["gifts"])
CSS_VERSION = "20261123-gift-1"
JS_VERSION = "20261123-gift-1"
SITE = "https://omnitrackr.xyz"
GIVE_PATH = "/supporters/gift"
# Examples of what a gift buys, for the price list on the giving page.
LENGTHS = (1, 3, 6, 12)


def _e(value) -> str:
    return escape(str(value), quote=True)


def _private(response: Response, *, store: bool = False) -> Response:
    response.headers["Cache-Control"] = "private, no-store" if not store else "private, no-cache"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Vary"] = "Cookie"
    return response


def _person(request: Request) -> bool:
    from .tier_list import _person as person
    return person(request)


def _long_date(value: Optional[datetime]) -> str:
    return f"{value:%B} {value.day}, {value.year}" if value else ""


def _head() -> str:
    return (f'<link rel="stylesheet" href="/static/gift-membership.css?v={CSS_VERSION}">'
            '<link rel="stylesheet" href="/static/avatar-frames.css?v=20261104-frames-1">'
            f'<script src="/static/gift-membership.js?v={JS_VERSION}" defer></script>')


def _page(title: str, description: str, path: str, content: str, *, member: bool) -> Response:
    from .discover import page
    return page(title, description, path, content, indexable=False, head=_head(), member=member)


def _message(title: str, heading: str, message: str, *, status: int = 200,
             actions=(("Give one yourself", GIVE_PATH), ("What supporters get", "/supporters"))) -> Response:
    response = strict_html_response(message_page(title, heading, message, eyebrow="OmniTrackr gift", actions=actions),
                                    status_code=status)
    return _private(response)


def _founding_note(paid_at: Optional[datetime], *, you: bool = False) -> str:
    if paid_at is None or not supporters.is_founding(models.Supporter(since=paid_at)):
        return ""
    if you:
        return "It was bought before 2027, so opening it makes you a founding supporter, with the gold color, for good."
    return "Because it was bought before 2027, whoever opens it becomes a founding supporter, with the gold color, for good."


# ---------------------------------------------------------------- pieces shared by the pages

def _card_html(gift: Optional[models.GiftMembership], *, sample: bool = False, heading_tag: str = "h2",
               months: Optional[int] = None) -> str:
    """The gift card itself: who it's for, how long, the note and who it's from."""
    months = gift.months if gift is not None else (months or 3)
    to_name = gift.to_name if gift is not None else ("Sam" if sample else None)
    from_name = gift.from_name if gift is not None else ("Alex" if sample else None)
    note = gift.note if gift is not None else (
        "For all the shows you keep telling me about. Pick a theme you like." if sample else None)
    to_html = f'<p class="gm-card__to">For {_e(to_name)}</p>' if to_name else '<p class="gm-card__to">A gift for you</p>'
    note_html = ""
    if note:
        paragraphs = "".join(f"<p>{_e(part)}</p>" for part in note.split("\n") if part.strip())
        note_html = f'<blockquote class="gm-card__note">{paragraphs}</blockquote>'
    from_html = f'<p class="gm-card__from">From {_e(from_name)}</p>' if from_name else ""
    label = gifts.months_label(months)
    return (f'<div class="gm-card{" gm-card--sample" if sample else ""}">'
            '<span class="gm-card__ribbon" aria-hidden="true"></span><span class="gm-card__bow" aria-hidden="true"></span>'
            '<p class="gm-card__brand">OmniTrackr</p>'
            f'{to_html}<{heading_tag} class="gm-card__title">{_e(label[:1].upper() + label[1:])} of supporter perks</{heading_tag}>'
            f'{note_html}{from_html}</div>')


def _inside_html(db: Session, *, you: bool = False, own: Optional[models.Supporter] = None) -> str:
    """What a gift switches on, with small previews drawn in CSS. ``you`` speaks to the person opening it, and
    ``own`` is their supporter row once they have, so the sample badge shows their real number."""
    their = "your" if you else "their"
    following = own.number if own is not None and own.number else supporters.next_number(db)
    founding = supporters.is_founding(own) if own is not None else supporters.founding_open()
    mark, label = ("★", "Founding supporter") if founding else ("♥", "Supporter")
    themes = "".join(f'<span class="gm-theme gm-theme--{name}"></span>' for name in ("lagoon", "sakura", "sunset", "ocean"))
    frames = "".join(f'<span class="avatar-frame avatar-frame--{name}"><span class="avatar-frame__face">{letter}</span>'
                     '<span class="avatar-frame__art"></span></span>'
                     for name, letter in (("halo", "A"), ("sparkle", "B"), ("pixel", "C")))
    perks = (
        (f'<p class="gm-perk__preview">{themes}</p>', f"Color themes for {their} app",
         "Lagoon, Sunset, Sakura, Ocean, Forest or Crimson, in light and night mode."),
        (f'<p class="gm-perk__preview gm-perk__preview--frames">{frames}</p>', "An avatar frame",
         f"A halo, film reel, sparkle or pixel frame around {their} profile picture."),
        (f'<p class="gm-perk__preview"><span class="gm-sample{" gm-sample--gold" if founding else ""}">{mark} {label} #{following}</span></p>',
         "A supporter number", f"Supporters are numbered in order, and the number stays on {their} badge."),
        ('<p class="gm-perk__preview"><span class="gm-banner"></span></p>', "A profile banner and color",
         f"Six banners and eight accent colors for {their} public profile, plus six showcase spots instead of three."),
    )
    cards = "".join(f'<article class="gm-perk">{preview}<h3>{_e(name)}</h3><p>{_e(text)}</p></article>'
                    for preview, name, text in perks)
    return f'<div class="gm-perks">{cards}</div>'


def _kofi_button(label: str = "Buy a gift on Ko-fi ↗", ghost: bool = False) -> str:
    return (f'<a class="button{" button--ghost" if ghost else ""}" data-kofi data-kofi-place="gift" '
            f'href="{_e(supporters.KOFI_URL)}" target="_blank" rel="noopener noreferrer">{_e(label)}</a>')


def _copy_box(value: str, label: str, button: str = "Copy") -> str:
    return (f'<div class="gm-copy"><span class="gm-copy__label">{_e(label)}</span>'
            f'<code class="gm-copy__value" data-gm-copy-value>{_e(value)}</code>'
            f'<button type="button" class="button button--ghost gm-copy__button" data-gm-copy="{_e(value)}">{_e(button)}</button>'
            '<span class="gm-copy__status" role="status" aria-live="polite"></span></div>')


# ---------------------------------------------------------------- /supporters/gift

FAQ = (
    ("Do they need an account?", "They need a free OmniTrackr account to open it. If they don't have one yet, the gift's "
     "page walks them through signing up and brings them back to open it."),
    ("When do the perks start?", "The day they open the gift, not the day you pay. If they already support OmniTrackr, "
     "the gift adds its time after the perks they have now."),
    ("Does it renew?", "No. A gift is one payment and nothing is charged again. When it runs out, their picks are saved "
     "in case they come back, and nothing else changes."),
    ("What if I forget to write OT-GIFT?", "Then the payment counts as support from you, and the perks go on your own "
     "account if Ko-fi used your OmniTrackr email. Write to us from the Contact page with the name on the payment and "
     "we'll turn it into a gift."),
    ("Will they see how much I paid?", "No. The card says how long the perks last, and whatever you write on it."),
    ("Can I give more than one?", "Yes. Each Ko-fi payment with OT-GIFT is one gift with its own code, so buy one per person."),
)


def _price_list() -> str:
    rows = "".join(
        f'<li><strong>{_e(gifts.months_label(months).capitalize())}</strong>'
        f'<span>{months} coffee{"" if months == 1 else "s"} · ${months * gifts.MONTH_PRICE}</span></li>'
        for months in LENGTHS)
    return (f'<ul class="gm-prices" aria-label="What a gift costs">{rows}</ul>'
            '<p class="gm-muted">Any number of coffees works, from one to twelve. More than twelve still makes a year.</p>')


def _gift_row(gift: models.GiftMembership) -> str:
    item = gifts.view(gift)
    who = f'For {_e(gift.to_name)}' if gift.to_name else "No name on the card yet"
    if item["state"] == "opened":
        status = f'<span class="gm-chip gm-chip--done">Opened {_e(_long_date(gift.redeemed_at))}</span>'
    elif item["state"] == "cancelled":
        status = '<span class="gm-chip gm-chip--off">Turned off</span>'
    else:
        status = '<span class="gm-chip">Not opened yet</span>'
    return (f'<li class="gm-given"><div class="gm-given__main"><p class="gm-given__title">'
            f'{_e(item["months_label"].capitalize())} · {who}</p>'
            f'<p class="gm-muted">Bought {_e(_long_date(gift.paid_at))} · code {_e(item["code"])}</p></div>'
            f'{status}<a class="button button--ghost" href="{_e(item["manage_path"])}">Open the card</a></li>')


def _your_gifts_html(db: Session, user: Optional[models.User]) -> str:
    if user is None:
        return ('<section class="gm-panel" id="your-gifts" aria-labelledby="gm-yours"><h2 id="gm-yours">Your gifts</h2>'
                '<p>Bought one already? We sent its links to the email you paid with on Ko-fi. '
                f'<a href="/?next={quote(GIVE_PATH, safe="")}#login">Log in</a> to see gifts tied to your account, '
                'or ask for the email again below.</p></section>')
    rows = gifts.given_by(db, user.id)
    body = (f'<ul class="gm-given-list">{"".join(_gift_row(gift) for gift in rows)}</ul>' if rows else
            '<p class="gm-muted">Gifts you buy with your code show up here within a minute of paying.</p>')
    return (f'<section class="gm-panel" id="your-gifts" aria-labelledby="gm-yours"><h2 id="gm-yours">Your gifts</h2>{body}</section>')


def _resend_html() -> str:
    return ('<section class="gm-panel" id="lost" aria-labelledby="gm-lost"><h2 id="gm-lost">Lost the email?</h2>'
            '<p>Type the email you paid with on Ko-fi and we\'ll send that inbox its gift links again.</p>'
            '<form class="gm-form gm-form--row" data-gm-resend novalidate>'
            '<label class="gm-sr" for="gmResendEmail">Your Ko-fi email</label>'
            '<input type="email" id="gmResendEmail" name="email" autocomplete="email" maxlength="254" required placeholder="you@example.com">'
            '<button type="submit" class="button button--ghost">Send my gift links</button></form>'
            '<p class="gm-status" data-gm-resend-status role="status" aria-live="polite"></p></section>')


@router.get(GIVE_PATH, include_in_schema=False)
def give_page(request: Request, user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if _person(request):
        support_asks.count("gift_page_seen")
    marker = gifts.marker_for(user.id) if user is not None else "OT-GIFT"
    founding = supporters.founding_deadline()
    founding_html = (f'<p class="gm-founding"><span aria-hidden="true">★</span> Gifts bought before 2027 make a founding '
                     f'supporter, even if they\'re opened in January. {_e(founding)}</p>' if founding else "")
    marker_note = ("This one has your supporter code in it, so the gift shows up on this page even if you pay with "
                   "another email." if user is not None else
                   "Members get a longer code that also puts the gift in their account. "
                   f'<a href="/?next={quote(GIVE_PATH, safe="")}#login">Log in</a> to see yours.')
    faq = "".join(f'<details class="gm-faq__item"><summary>{_e(q)}</summary><p>{_e(a)}</p></details>' for q, a in FAQ)
    content = (
        '<article class="gm" data-gm-page="give">'
        '<header class="gm-hero"><div class="gm-hero__copy">'
        '<p class="eyebrow">For someone who tracks everything</p>'
        '<h1>Give someone OmniTrackr supporter perks</h1>'
        '<p class="gm-lead">Pay on Ko-fi and we send you a gift code to pass on. Whoever opens it gets every supporter perk '
        'for as long as you chose: color themes for their app, an avatar frame, a numbered badge and the rest. '
        'The money pays for hosting, the same as any other support.</p>'
        f'{founding_html}'
        f'<p class="gm-actions">{_kofi_button()}<a class="button button--ghost" href="#how">How it works</a></p></div>'
        f'<div class="gm-hero__card">{_card_html(None, sample=True)}</div></header>'
        '<section class="gm-panel gm-how" id="how" aria-labelledby="gm-how-title"><h2 id="gm-how-title">How it works</h2>'
        '<ol class="gm-steps">'
        '<li><h3>Choose how long</h3><p>Each $3 coffee on Ko-fi is a month of perks. Three coffees is three months, '
        f'twelve is a year.</p>{_price_list()}</li>'
        '<li><h3>Write this in your Ko-fi message</h3>'
        f'<p>It tells us the payment is a gift, not support for your own account.</p>{_copy_box(marker, "Your gift code")}'
        f'<p class="gm-muted">{marker_note}</p></li>'
        '<li><h3>Get the link</h3><p>We email the gift to the address you used on Ko-fi, usually within a minute'
        + (', and it shows up under Your gifts below.' if user is not None else '.') + '</p></li>'
        '<li><h3>Give it</h3><p>Send the link, or write a card and print it with the code and a QR code on it. They open it '
        'with a free account, and the perks start that day.</p></li></ol>'
        f'<p class="gm-actions">{_kofi_button()}</p></section>'
        '<section class="gm-panel" aria-labelledby="gm-inside-title"><h2 id="gm-inside-title">What\'s inside</h2>'
        '<p>Everything a supporter gets. All of it is cosmetic: nothing on OmniTrackr is locked behind support, so the gift '
        'adds a few nice things without taking anything from anyone who doesn\'t have one.</p>'
        f'{_inside_html(db)}'
        '<p><a href="/supporters#perks-heading">See every perk</a> · <a href="/supporters#try-heading">Try them on</a></p></section>'
        f'{_your_gifts_html(db, user)}{_resend_html()}'
        f'<section class="gm-panel gm-faq" aria-labelledby="gm-faq-title"><h2 id="gm-faq-title">Questions</h2>{faq}'
        '<p class="gm-muted">Got a gift code yourself? <a href="/gift">Open it here</a>.</p></section>'
        '</article>'
    )
    response = _page("Give OmniTrackr supporter perks as a gift",
                     "Buy someone OmniTrackr supporter perks on Ko-fi: app themes, an avatar frame and a numbered badge, "
                     "opened with a gift code.", GIVE_PATH, content, member=user is not None)
    return _private(response, store=True)


# ---------------------------------------------------------------- /gift: type a code

def _enter_html(error: str = "") -> str:
    error_html = f'<p class="gm-status gm-status--error" role="alert">{_e(error)}</p>' if error else ""
    return ('<article class="gm gm--narrow" data-gm-page="enter"><header class="gm-hero gm-hero--short"><div class="gm-hero__copy">'
            '<p class="eyebrow">OmniTrackr gift</p><h1>Open a gift</h1>'
            '<p class="gm-lead">Type the code from your card or email. It\'s twelve letters and numbers, like ABCD-EFGH-JKMN.</p>'
            '<form class="gm-form" method="post" action="/gift">'
            '<label for="gmCode">Gift code</label>'
            '<input id="gmCode" name="code" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="40" '
            'required placeholder="ABCD-EFGH-JKMN">'
            f'<button type="submit" class="button">Open it</button></form>{error_html}'
            f'<p class="gm-muted">Want to give one instead? <a href="{GIVE_PATH}">Here\'s how</a>.</p>'
            '</div></header></article>')


@router.get("/gift", include_in_schema=False)
def enter_page(request: Request, user=Depends(get_optional_current_user)):
    return _private(_page("Open an OmniTrackr gift", "Type the code from an OmniTrackr gift card to open it.", "/gift",
                          _enter_html(), member=user is not None))


@router.post("/gift", include_in_schema=False)
def enter_code(request: Request, code: str = Form("", max_length=60), user=Depends(get_optional_current_user)):
    normal = gifts.normalize(code)
    if normal is None:
        response = _page("Open an OmniTrackr gift", "Type the code from an OmniTrackr gift card to open it.", "/gift",
                         _enter_html("That doesn't look like a gift code. It has twelve letters and numbers."),
                         member=user is not None)
        response.status_code = 422
        return _private(response)
    return RedirectResponse(f"/gift/{gifts.pretty(normal)}", status_code=303)


# ---------------------------------------------------------------- /gift/<code>

def _gift_actions(db: Session, gift: models.GiftMembership, user: Optional[models.User], path: str, opened_now: bool) -> str:
    if user is None:
        next_path = quote(path, safe="")
        return ('<section class="gm-panel gm-open" aria-labelledby="gm-open-title"><h2 id="gm-open-title">Open your gift</h2>'
                '<p>OmniTrackr is a free library for films, TV, anime, games, books, albums, manga, podcasts and audiobooks. '
                'Make an account (it takes a minute) and this page brings you back to open the gift.</p>'
                f'<p class="gm-actions"><a class="button" href="/?next={next_path}#signup" data-gm-signup>Make a free account</a>'
                f'<a class="button button--ghost" href="/?next={next_path}#login">I have an account</a></p>'
                f'<p class="gm-muted">The perks last {gifts.days_for(gift.months)} days from the day you open it.</p></section>')
    if gift.redeemed_at is not None and gift.redeemed_by == user.id:
        supporter = supporters.get_supporter(db, user.id)
        until = _long_date(supporter.active_until) if supporter and supporter.active_until else ""
        badge = (supporters.level_label(supporters.is_founding(supporter), 0, supporter.number)
                 if supporter is not None else "")
        head = "It's open. Enjoy!" if opened_now else f"You opened this gift on {_long_date(gift.redeemed_at)}"
        return ('<section class="gm-panel gm-open gm-open--done" aria-labelledby="gm-open-title" data-gm-opened>'
                f'<h2 id="gm-open-title" tabindex="-1">{_e(head)}</h2>'
                + (f'<p>You\'re <strong>{_e(badge)}</strong>. ' if badge else '<p>')
                + 'Your supporter perks are on' + (f' until <strong>{_e(until)}</strong>' if until else '') + '.</p>'
                '<p class="gm-actions"><a class="button" href="/#supporter">Pick your theme and frame</a>'
                '<a class="button button--ghost" href="/supporters">See what you got</a></p></section>')
    if gift.giver_id == user.id:
        return ('<section class="gm-panel gm-open" aria-labelledby="gm-open-title"><h2 id="gm-open-title">This is your gift</h2>'
                '<p>You bought this one, so it can\'t go on your own account. Send this page\'s link to the person it\'s for, '
                'or print the card.</p>'
                f'<p class="gm-actions"><a class="button" href="{_e(gifts.manage_path(gift))}">Write or print the card</a></p></section>')
    until = _long_date(gifts.ends_if_opened_now(db, user, gift))
    return ('<section class="gm-panel gm-open" aria-labelledby="gm-open-title"><h2 id="gm-open-title">Open your gift</h2>'
            f'<p>It goes on your account, <strong>@{_e(user.username)}</strong>, and your supporter perks run until '
            f'<strong>{_e(until)}</strong>.</p>'
            f'<form method="post" action="{_e(path)}/open" class="gm-actions">'
            '<button type="submit" class="button">Open my gift</button></form></section>')


@router.get("/gift/{code}", include_in_schema=False)
def gift_page(code: str, request: Request, opened: int = Query(0, ge=0, le=1), user=Depends(get_optional_current_user),
              db: Session = Depends(get_db)):
    normal = gifts.normalize(code)
    gift = gifts.by_code(db, normal) if normal else None
    if gift is None or gift.cancelled_at is not None:
        return _message("Gift not found", "This gift code doesn't work",
                        "Check it against the card or the email, or ask whoever sent it for the link again. "
                        "You can also type the code in by hand.",
                        status=404, actions=(("Type a code", "/gift"), ("Give one yourself", GIVE_PATH)))
    path = gifts.path_of(gift)
    if code != path.rsplit("/", 1)[1]:
        return RedirectResponse(path + ("?opened=1" if opened else ""), status_code=307)
    mine = user is not None and gift.redeemed_by == user.id
    if gift.redeemed_at is not None and not mine:
        return _message("Gift already opened", "This gift has been opened",
                        "Each gift opens once, and this one already has. If it was meant for you, ask whoever sent it.")
    giver = user is not None and gift.giver_id == user.id
    if not giver and not mine and _person(request):
        gifts.count_open(db, gift)
        support_asks.count("gift_link_opened")
    founding = _founding_note(gift.paid_at, you=not giver) if gift.redeemed_at is None else ""
    founding_html = f'<p class="gm-founding"><span aria-hidden="true">★</span> {_e(founding)}</p>' if founding else ""
    label = gifts.months_label(gift.months)
    who = gift.from_name or "Someone"
    lead = (f"{who} gave you OmniTrackr supporter perks: color themes for your app, an avatar frame, a numbered badge "
            f"and more, for {label}.") if not mine else f"Your {label} of supporter perks, opened."
    if giver:
        lead = f"This is how your gift looks to the person who opens it: {label} of OmniTrackr supporter perks."
    content = (
        f'<article class="gm gm--gift" data-gm-page="gift">'
        f'<div class="gm-gift"><div class="gm-gift__card">{_card_html(gift, heading_tag="h1")}</div>'
        f'<div class="gm-gift__side"><p class="gm-lead">{_e(lead)}</p>{founding_html}'
        f'{_gift_actions(db, gift, user, path, bool(opened) and mine)}</div></div>'
        '<section class="gm-panel" aria-labelledby="gm-inside-title"><h2 id="gm-inside-title">What\'s inside</h2>'
        f'{_inside_html(db, you=not giver, own=supporters.get_supporter(db, user.id) if mine else None)}'
        '<p><a href="/supporters#perks-heading">See every perk</a></p></section>'
        '</article>'
    )
    title = f"A gift for {gift.to_name}" if gift.to_name else "An OmniTrackr gift for you"
    description = (f"{label[:1].upper() + label[1:]} of OmniTrackr supporter perks"
                   + (f" from {gift.from_name}" if gift.from_name else "") + ", waiting to be opened.")
    return _private(_page(title, description, path, content, member=user is not None))


@router.post("/gift/{code}/open", include_in_schema=False)
def open_gift(code: str, request: Request, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        gift = gifts.redeem(db, user, code)
    except gifts.GiftError as error:
        if error.status == 404:
            return _message("Gift not found", "This gift code doesn't work", error.detail, status=404,
                            actions=(("Type a code", "/gift"), ("Give one yourself", GIVE_PATH)))
        normal = gifts.normalize(code)
        back = f"/gift/{gifts.pretty(normal)}" if normal else "/gift"
        return _message("Couldn't open the gift", "This gift can't be opened here", error.detail, status=error.status,
                        actions=(("Back to the gift", back), ("Give one yourself", GIVE_PATH)))
    support_asks.count("gift_opened")
    return RedirectResponse(gifts.path_of(gift) + "?opened=1", status_code=303)


class RedeemGift(BaseModel):
    code: str = Field(..., min_length=1, max_length=60)


@router.post("/api/gift/redeem")
def redeem_api(payload: RedeemGift, request: Request, response: Response, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """The same as the button on the gift's page, for the app."""
    response.headers["Cache-Control"] = "private, no-store"
    try:
        gift = gifts.redeem(db, user, payload.code)
    except gifts.GiftError as error:
        raise HTTPException(status_code=error.status, detail=error.detail)
    support_asks.count("gift_opened")
    return {"opened": True, "months": gift.months, "supporter": supporters.status_payload(db, user)}


# ---------------------------------------------------------------- the giver's card page

def _manage_html(db: Session, gift: models.GiftMembership, saved: bool, error: str = "") -> str:
    item = gifts.view(gift)
    url = f"{SITE}{item['path']}"
    from ..two_factor import qr_data_uri
    if item["state"] == "opened":
        status = f'<span class="gm-chip gm-chip--done">Opened {_e(_long_date(gift.redeemed_at))}</span>'
    elif item["state"] == "cancelled":
        status = '<span class="gm-chip gm-chip--off">Turned off</span>'
    else:
        status = '<span class="gm-chip">Not opened yet</span>'
    seen = item["opened"]
    seen_html = (f'<p class="gm-muted">The link has been opened {seen:,} time{"" if seen == 1 else "s"}.</p>'
                 if seen and item["state"] == "open" else "")
    editable = item["state"] == "open"
    form = ""
    if editable:
        saved_html = '<p class="gm-status gm-status--ok" role="status">Saved. The card below shows it.</p>' if saved else ""
        error_html = f'<p class="gm-status gm-status--error" role="alert">{_e(error)}</p>' if error else ""
        form = (
            '<section class="gm-panel" aria-labelledby="gm-write-title"><h2 id="gm-write-title">Write the card</h2>'
            '<p class="gm-muted">All optional. They see it when they open the link.</p>'
            f'<form class="gm-form" method="post" action="{_e(item["manage_path"])}">'
            f'<label for="gmTo">For</label><input id="gmTo" name="to_name" maxlength="{gifts.TO_LIMIT}" '
            f'value="{_e(gift.to_name or "")}" placeholder="Their name" autocomplete="off">'
            f'<label for="gmFrom">From</label><input id="gmFrom" name="from_name" maxlength="{gifts.FROM_LIMIT}" '
            f'value="{_e(gift.from_name or "")}" placeholder="Your name" autocomplete="off">'
            f'<label for="gmNote">Note</label><textarea id="gmNote" name="note" rows="4" maxlength="{gifts.NOTE_LIMIT}" '
            f'placeholder="A line or two">{_e(gift.note or "")}</textarea>'
            '<button type="submit" class="button">Save the card</button></form>'
            f'{saved_html}{error_html}</section>')
    share = ""
    if item["state"] == "open":
        share = ('<section class="gm-panel" aria-labelledby="gm-send-title"><h2 id="gm-send-title">Send it</h2>'
                 f'{_copy_box(url, "The link", "Copy link")}'
                 '<p class="gm-actions"><button type="button" class="button button--ghost" data-gm-share hidden>Share</button></p>'
                 '<p class="gm-muted">Anyone with the link or the code can open the gift, once. Send it only to the person '
                 'it\'s for.</p></section>')
    printable = ""
    if item["state"] == "open":
        printable = (
            '<section class="gm-panel gm-print-panel" aria-labelledby="gm-print-title"><h2 id="gm-print-title">Print the card</h2>'
            '<p class="gm-muted">The printout has the card on top and the code with a QR code that opens the gift '
            'underneath. Fold it along the dashed line.</p>'
            '<div class="gm-print" data-gm-print>'
            f'<div class="gm-print__front">{_card_html(gift)}</div>'
            '<div class="gm-print__inside">'
            f'<img class="gm-print__qr" src="{qr_data_uri(url)}" alt="QR code that opens the gift" width="148" height="148">'
            '<div><p class="gm-print__how">Open it at</p><p class="gm-print__url">omnitrackr.xyz/gift</p>'
            f'<p class="gm-print__how">with the code</p><p class="gm-print__code">{_e(item["code"])}</p>'
            f'<p class="gm-print__small">{gifts.days_for(gift.months)} days of supporter perks, starting the day it\'s opened.</p></div>'
            '</div></div>'
            '<p class="gm-actions"><button type="button" class="button" data-gm-printit>Print the card</button></p>'
            '</section>')
    founding = _founding_note(gift.paid_at) if item["state"] == "open" else ""
    founding_html = f'<p class="gm-founding"><span aria-hidden="true">★</span> {_e(founding)}</p>' if founding else ""
    kept = ""
    if item["state"] != "open":
        said = ("This is the card they saw when they opened it." if item["state"] == "opened"
                else "This gift was turned off, so the link and the code no longer open it.")
        kept = ('<section class="gm-panel" aria-labelledby="gm-card-title"><h2 id="gm-card-title">The card</h2>'
                f'<p class="gm-muted">{said}</p><div class="gm-kept">{_card_html(gift)}</div></section>')
    private = ('<p class="gm-muted">This page is just for you. Anyone with its address can change the card, so keep it to yourself.</p>'
               if editable else "")
    return (
        '<article class="gm" data-gm-page="manage">'
        '<header class="gm-hero gm-hero--short"><div class="gm-hero__copy">'
        '<p class="eyebrow">Your gift</p>'
        f'<h1>{_e(item["months_label"].capitalize())} of supporter perks</h1>'
        f'<p class="gm-manage__status">{status} <span class="gm-muted">Code {_e(item["code"])} · bought '
        f'{_e(_long_date(gift.paid_at))}</span></p>{seen_html}{founding_html}{private}'
        '</div></header>'
        f'{share}{form}{printable}{kept}'
        f'<p class="gm-muted gm-manage__foot"><a href="{GIVE_PATH}">Give another one</a></p>'
        '</article>'
    )


def _manage_response(db: Session, gift: models.GiftMembership, user, *, saved: bool = False, error: str = "",
                     status: int = 200) -> Response:
    response = _page("Your OmniTrackr gift", "Write, print and send an OmniTrackr gift.", GIVE_PATH,
                     _manage_html(db, gift, saved, error), member=user is not None)
    response.status_code = status
    return _private(response)


@router.get(GIVE_PATH + "/manage/{token}", include_in_schema=False)
def manage_page(token: str, request: Request, saved: int = Query(0, ge=0, le=1), user=Depends(get_optional_current_user),
                db: Session = Depends(get_db)):
    gift = gifts.by_manage_token(db, token)
    if gift is None:
        return _message("Gift not found", "This link doesn't open a gift",
                        "Check that the whole link came through from the email. You can ask for the email again.",
                        status=404, actions=(("Send the email again", GIVE_PATH + "#lost"), ("Give one", GIVE_PATH)))
    return _manage_response(db, gift, user, saved=bool(saved))


@router.post(GIVE_PATH + "/manage/{token}", include_in_schema=False)
def save_card(token: str, request: Request, to_name: str = Form("", max_length=400), from_name: str = Form("", max_length=400),
              note: str = Form("", max_length=3000), user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    gift = gifts.by_manage_token(db, token)
    if gift is None:
        return _message("Gift not found", "This link doesn't open a gift", "Check that the whole link came through.",
                        status=404, actions=(("Give one", GIVE_PATH),))
    try:
        gifts.save_card(db, gift, {"to_name": to_name, "from_name": from_name, "note": note})
    except gifts.GiftError as error:
        db.rollback()
        db.refresh(gift)
        return _manage_response(db, gift, user, error=error.detail, status=error.status)
    return RedirectResponse(gifts.manage_path(gift) + "?saved=1", status_code=303)


# ---------------------------------------------------------------- "Lost the email?"

class ResendGift(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


RESEND_REPLY = ("If a gift was bought from that email, we've sent its links there. Nothing after a few minutes? Check spam, "
                "or write to us from the Contact page with the name on your Ko-fi payment.")


@router.post("/api/gift/resend")
def resend(payload: ResendGift, request: Request, background: BackgroundTasks, response: Response,
           db: Session = Depends(get_db)):
    """Send a payer their gift links again. The reply is the same either way, so nobody can check who bought one."""
    response.headers["Cache-Control"] = "private, no-store"
    email = payload.email.strip()
    if not supporters.looks_like_email(email):
        raise HTTPException(status_code=422, detail="Type a whole email address, like name@example.com")
    found = gifts.for_payer_email(db, email)
    if found:
        background.add_task(gifts.send_links, email, [gifts.email_item(gift) for gift in found], True)
    return {"message": RESEND_REPLY}


# ---------------------------------------------------------------- the site owner

def _require_admin(user: models.User) -> None:
    if not is_site_admin(user):
        raise HTTPException(status_code=403, detail="Only the site owner can manage gifts")


def _owner_item(gift: models.GiftMembership) -> dict:
    item = gifts.view(gift)
    return {"id": gift.id, "months": gift.months, "months_label": item["months_label"], "code": item["code"],
            "url": f"{SITE}{item['path']}", "manage_url": f"{SITE}{item['manage_path']}", "state": item["state"]}


class MakeGift(BaseModel):
    months: int = Field(..., ge=1, le=gifts.MAX_MONTHS)


class GiftFromPayment(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=80)


@router.get("/api/supporters/gifts")
def owner_gifts(response: Response, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _require_admin(user)
    rows = gifts.owner_list(db)
    for row in rows:
        row["url"] = f"{SITE}{row.pop('path')}"
        row["manage_url"] = f"{SITE}{row.pop('manage_path')}"
    return {"gifts": rows}


@router.post("/api/supporters/gifts")
def owner_make(payload: MakeGift, response: Response, user: models.User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """A gift for a giveaway or a prize, with no Ko-fi payment behind it."""
    response.headers["Cache-Control"] = "private, no-store"
    _require_admin(user)
    try:
        gift = gifts.owner_make(db, payload.months)
    except gifts.GiftError as error:
        raise HTTPException(status_code=error.status, detail=error.detail)
    return _owner_item(gift)


@router.post("/api/supporters/gifts/from-payment")
def owner_from_payment(payload: GiftFromPayment, response: Response, user: models.User = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    """A waiting payment whose payer meant it as a gift but left out OT-GIFT."""
    response.headers["Cache-Control"] = "private, no-store"
    _require_admin(user)
    try:
        gift = gifts.owner_from_payment(db, payload.message_id)
    except gifts.GiftError as error:
        db.rollback()
        raise HTTPException(status_code=error.status, detail=error.detail)
    return _owner_item(gift)


@router.post("/api/supporters/gifts/{gift_id}/cancel")
def owner_cancel(gift_id: PositiveDatabaseId, response: Response, user: models.User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    response.headers["Cache-Control"] = "private, no-store"
    _require_admin(user)
    try:
        gift = gifts.owner_cancel(db, gift_id)
    except gifts.GiftError as error:
        raise HTTPException(status_code=error.status, detail=error.detail)
    return _owner_item(gift)
