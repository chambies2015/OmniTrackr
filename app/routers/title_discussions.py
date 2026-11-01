"""Title discussion boards: /titles/<kind>/<slug>/discussions and the API behind them (Oct 2026)."""
from __future__ import annotations

import json
import os
import re
from html import escape
from typing import Literal, Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .. import models, supporters, title_discussions as boards, title_metadata, title_pages
from ..admin_access import is_moderator
from ..csp import strict_html_response
from ..dependencies import get_current_user, get_db, get_optional_current_user
from ..integer_bounds import PositiveDatabaseId
from ..site_chrome import apply_site_chrome

router = APIRouter(tags=["discussions"])
SITE_URL = os.getenv("SITE_URL", "https://omnitrackr.xyz").rstrip("/")
ASSET_VERSION = "20261028-discussions-1"
KIND_PLURALS = {"movie": "Movies", "tv": "TV shows", "anime": "Anime", "game": "Games", "album": "Albums", "book": "Books",
                "manga": "Manga", "podcast": "Podcasts", "audiobook": "Audiobooks"}


def _e(value) -> str:
    return escape(str(value if value is not None else ""), quote=True)


def _script_json(data) -> str:
    return (json.dumps(data, ensure_ascii=False)
            .replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e"))


def _fail(error: boards.DiscussionError):
    raise HTTPException(error.status, error.message)


def _private(response: Response) -> None:
    response.headers["Cache-Control"] = "private, no-store"


def _sign_in(path: str) -> str:
    return "/?next=" + quote(path, safe="") + "#landing-auth"


def _poster(db: Session, group) -> Optional[str]:
    if group is None:
        return None
    metadata, _ = title_metadata.cached(db, title_metadata.cache_key(group.kind, group.normalized, group.year))
    if metadata and title_pages._safe_image(metadata.get("poster")):
        return metadata["poster"]
    field = title_pages.IMAGE_FIELD[group.kind]
    for item in group.items:
        image = title_pages._safe_image(getattr(item, field, None))
        if image:
            return image
    return None


def _author_html(author: Optional[boards.Author]) -> str:
    if author is None:
        return '<span class="disc-author">a member</span>'
    name = (f'<a class="disc-author" href="{_e(author.profile_url)}">{_e(author.username)}</a>' if author.profile_url
            else f'<span class="disc-author">{_e(author.username)}</span>')
    return name + supporters.chip_html(author.supporter)


def _time_html(moment) -> str:
    if moment is None:
        return ""
    return f'<time datetime="{_e(moment.isoformat(timespec="seconds"))}Z">{_e(boards.ago(moment))}</time>'


def _body_html(post) -> str:
    inner = f'<div class="disc-body">{boards.body_html(post.body)}</div>'
    if not post.spoiler:
        return inner
    return ('<details class="disc-spoiler-post"><summary><span class="disc-tag">Spoilers</span> '
            'This post gives away plot details. Show it</summary>' + inner + '</details>')


def _page(*, title: str, description: str, canonical: str, robots: str, body: str, structured: str = "",
          image: Optional[str] = None, signed_in: bool = False) -> str:
    og_image = f'<meta property="og:image" content="{_e(image)}">' if image else ""
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{_e(title)}</title>
  <meta name="description" content="{_e(description)}">
  <meta name="robots" content="{robots}">
  <link rel="canonical" href="{_e(canonical)}">
  <meta property="og:title" content="{_e(title)}">
  <meta property="og:description" content="{_e(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{_e(canonical)}">
  <meta property="og:site_name" content="OmniTrackr">
  {og_image}
  <meta name="twitter:card" content="summary">
  <link rel="icon" type="image/x-icon" href="/omnitrackr_favicon.ico">
  <link rel="preload" href="/static/fonts/poppins-700-latin.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="/static/fonts.css?v=20261009-fonts-1">
  <link rel="stylesheet" href="/static/discussions.css?v={ASSET_VERSION}">
  <script src="/static/discussions.js?v={ASSET_VERSION}" defer></script>
  {structured}
</head>
<body class="site disc-page{' disc-page--member' if signed_in else ''}">
  <!--SITE_NAV:titles-->
  <main>
    {body}
  </main>
  <!--SITE_FOOTER-->
</body>
</html>"""
    return apply_site_chrome(page)


def _crumbs(kind: str, title_path: Optional[str], title: str, board: Optional[str] = None) -> str:
    title_link = f'<a href="{_e(title_path)}">{_e(title)}</a>' if title_path else _e(title)
    tail = f' <span aria-hidden="true">/</span> <a href="{_e(board)}">Discussions</a>' if board else ""
    return (f'<nav class="disc-crumbs" aria-label="Breadcrumb"><a href="/titles">Titles</a> <span aria-hidden="true">/</span> '
            f'<a href="/titles/{_e(kind)}">{_e(KIND_PLURALS[kind])}</a> <span aria-hidden="true">/</span> {title_link}{tail}</nav>')


def _head_html(kind: str, title: str, title_path: Optional[str], poster: Optional[str], heading: str, meta: str,
               board: Optional[str] = None) -> str:
    art = (f'<img class="disc-head__poster" src="{_e(poster)}" alt="" width="72" height="108">' if poster
           else f'<span class="disc-head__poster disc-head__poster--empty" aria-hidden="true">{_e(title[:1].upper())}</span>')
    return (f'<header class="disc-head"><div class="site-wrap disc-head__inner">{art}<div class="disc-head__copy">'
            f'{_crumbs(kind, title_path, title, board)}<h1>{_e(heading)}</h1><p class="disc-head__meta">{meta}</p>'
            '</div></div></header>')


def _composer_tips() -> str:
    return ('<p class="disc-form__tip">Hide a twist inside a sentence with double bars: '
            '<code>||Bruce Willis was dead||</code>. Readers tap it to see it.</p>')


def _start_form(kind: str, slug: str, title: str, open_: bool) -> str:
    return (f'<details class="disc-start" id="start"{" open" if open_ else ""}><summary class="site-btn site-btn--primary">'
            'Start a discussion</summary>'
            f'<form class="disc-form" data-disc-start data-kind="{_e(kind)}" data-slug="{_e(slug)}" novalidate>'
            '<label class="disc-form__label" for="discSubject">Title</label>'
            f'<input id="discSubject" name="subject" type="text" minlength="{boards.SUBJECT_MIN}" maxlength="{boards.SUBJECT_MAX}" required '
            f'placeholder="What do you want to talk about?" autocomplete="off">'
            '<label class="disc-form__label" for="discBody">Your post</label>'
            f'<textarea id="discBody" name="body" rows="6" maxlength="{boards.THREAD_BODY_MAX}" required '
            f'placeholder="A question, a theory, a scene you keep thinking about…"></textarea>'
            f'{_composer_tips()}'
            '<label class="disc-form__check"><input name="spoiler" type="checkbox"> The whole post has spoilers</label>'
            '<div class="disc-form__row"><button type="submit" class="site-btn site-btn--primary">Post discussion</button>'
            '<p class="disc-form__status" role="status" aria-live="polite"></p></div>'
            f'<p class="disc-form__note">Keep it about {_e(title)} and be kind. Posts with three reports are hidden until a moderator checks them.</p>'
            '</form></details>')


def _guest_prompt(path: str, verb: str) -> str:
    return (f'<div class="disc-guest"><p>Sign in to {verb}. It\'s free, and your library stays private.</p>'
            f'<div class="disc-guest__actions"><a class="site-btn site-btn--primary" rel="nofollow" href="{_e(_sign_in(path))}">Sign in</a>'
            '<a class="site-btn site-btn--ghost" href="/#signup">Create a free account</a></div></div>')


def thread_row_html(thread: models.TitleDiscussion, author: Optional[boards.Author]) -> str:
    """One thread in a list (board page and title page)."""
    if thread.deleted_at:
        excerpt = '<p class="disc-row__excerpt disc-muted">The opening post was deleted. The replies are still here.</p>'
    elif thread.spoiler:
        excerpt = '<p class="disc-row__excerpt"><span class="disc-tag">Spoilers</span></p>'
    else:
        excerpt = f'<p class="disc-row__excerpt">{_e(boards.plain_excerpt(thread.body, 160))}</p>'
    replies = thread.reply_count or 0
    flags = '<span class="disc-tag disc-tag--muted">Locked</span> ' if thread.locked_at else ""
    return (f'<li class="disc-row"><a class="disc-row__link" href="{_e(boards.thread_path(thread))}">'
            f'<strong class="disc-row__subject">{flags}{_e(thread.subject)}</strong></a>{excerpt}'
            f'<p class="disc-row__meta">{_author_html(author)} · {_time_html(thread.created_at)}</p>'
            f'<span class="disc-row__count"><strong>{replies}</strong> repl{"y" if replies == 1 else "ies"}</span></li>')


def title_section_html(db: Session, group) -> str:
    """The "Discussions" section on a title page: the latest threads and a way in."""
    slug = group.path.rsplit("/", 1)[1]
    found = boards.summary_for_page(db, group.kind, slug)
    board = boards.board_path(group.kind, slug)
    if found["threads"]:
        people = boards.authors(db, [thread.user_id for thread in found["threads"]])
        rows = "".join(thread_row_html(thread, people.get(thread.user_id)) for thread in found["threads"])
        count = found["count"]
        more = (f'<a class="site-btn site-btn--ghost" href="{_e(board)}">See all {count} discussions</a>'
                if count > len(found["threads"]) else "")
        content = f'<ul class="disc-list">{rows}</ul><div class="disc-section__actions"><a class="site-btn site-btn--primary" href="{_e(board)}#start">Start a discussion</a>{more}</div>'
    else:
        content = (f'<p class="title-empty">Nobody has started a discussion about {_e(group.title)} yet. Ask a question, share a theory, '
                   'or pick a scene to talk about.</p>'
                   f'<div class="disc-section__actions"><a class="site-btn site-btn--primary" href="{_e(board)}#start">Start the first discussion</a></div>')
    return (f'<section class="title-section disc-section" aria-labelledby="discussions-title">'
            f'<h2 id="discussions-title">Discussions</h2>{content}</section>')


# ---------------------------------------------------------------- pages

LOCAL_BOARD_PATH = re.compile(r"/titles/(movie|tv|anime|game|album|book|manga)/[a-z0-9-]{1,140}/discussions(/[1-9][0-9]{0,9})?")


def _moved(path: str) -> RedirectResponse:
    """A permanent redirect to the canonical address, which is only ever one of our own board paths."""
    if not LOCAL_BOARD_PATH.fullmatch(path):
        raise HTTPException(404, "Not found")
    return RedirectResponse(path, status_code=301)


def _group_and_title(db: Session, kind: str, slug: str):
    group = title_pages.find(db, kind, slug)
    if group is not None and group.path.rsplit("/", 1)[1] != slug:
        return group, None  # caller redirects to the canonical slug
    return group, group.title if group else None


@router.get("/titles/{kind}/{slug}/discussions", include_in_schema=False)
def board_page(kind: str, slug: str, page: int = Query(1, ge=1, le=1000),
               user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown title type")
    group, title = _group_and_title(db, kind, slug)
    if group is not None and title is None:
        return _moved(boards.board_path(group.kind, group.path.rsplit("/", 1)[1]))
    count = boards.board_count(db, kind, slug)
    if group is None:
        first = boards.board_threads(db, kind, slug, limit=1)
        if not first:
            raise HTTPException(404, "Title not found")
        title = first[0].title
    pages = max(1, -(-count // boards.BOARD_PAGE_SIZE))
    if page > pages:
        raise HTTPException(404, "Page not found")
    threads = boards.board_threads(db, kind, slug, offset=(page - 1) * boards.BOARD_PAGE_SIZE)
    people = boards.authors(db, [thread.user_id for thread in threads])
    path = boards.board_path(kind, slug)
    title_path = group.path if group else None
    if threads:
        listing = f'<ul class="disc-list">{"".join(thread_row_html(t, people.get(t.user_id)) for t in threads)}</ul>'
    else:
        listing = (f'<div class="disc-empty"><h2>No discussions yet</h2><p>Be the first to start one about {_e(title)}. '
                   'Good openers: a question you had at the end, a character you can\'t make up your mind about, or '
                   'what someone new to it should know going in.</p></div>')
    pager = ""
    if pages > 1:
        links = []
        if page > 1:
            links.append(f'<a class="site-btn site-btn--ghost" rel="prev" href="{_e(path)}{"" if page == 2 else f"?page={page - 1}"}">Newer</a>')
        links.append(f'<span>Page {page} of {pages}</span>')
        if page < pages:
            links.append(f'<a class="site-btn site-btn--ghost" rel="next" href="{_e(path)}?page={page + 1}">Older</a>')
        pager = f'<nav class="disc-pager" aria-label="Pages">{"".join(links)}</nav>'
    composer = (_start_form(kind, slug, title, open_=not threads) if user is not None
                else _guest_prompt(path + "#start", "start a discussion"))
    meta = (f'{count} discussion{"s" if count != 1 else ""} · '
            + (f'<a href="{_e(title_path)}#community-title">Read the reviews</a>' if title_path else "Discussions from members"))
    body = (_head_html(kind, title, title_path, _poster(db, group), f"{title} discussions", meta)
            + f'<div class="site-wrap disc-wrap"><div class="disc-main">{composer}{listing}{pager}</div>'
            + _rules_aside() + '</div>')
    canonical = SITE_URL + path + (f"?page={page}" if page > 1 else "")
    html = _page(title=f"{title} discussions | OmniTrackr",
                 description=f"Talk about {title} with other OmniTrackr members: questions, theories and favourite moments, "
                             "with spoilers folded away.",
                 canonical=canonical, robots="noindex, follow", body=body, image=_poster(db, group),
                 signed_in=user is not None)
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if user is not None else "public, max-age=120"
    response.headers["Vary"] = "Cookie"
    response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


def _rules_aside() -> str:
    return ('<aside class="disc-aside"><h2>House rules</h2><ul>'
            '<li>Keep spoilers folded: tick the spoiler box, or wrap the twist in <code>||double bars||</code>.</li>'
            '<li>Disagree with the take, not the person.</li>'
            '<li>No ads, self-promotion or links to pirated copies.</li>'
            '<li>Three reports hide a post until a moderator looks at it.</li></ul></aside>')


def _post_actions(kind: str, post, viewer, *, is_thread: bool, thread) -> str:
    """Report for other members, edit and delete for the author, moderator tools for moderators."""
    if viewer is None:
        return ""
    target = "" if is_thread else f' data-reply-id="{_e(post.id)}"'
    bits = []
    own = viewer.id == post.user_id
    if own and not (is_thread and thread.deleted_at):
        bits.append(f'<button type="button" class="disc-action" data-disc-edit{target}>Edit</button>')
        bits.append(f'<button type="button" class="disc-action" data-disc-delete{target}>Delete</button>')
    elif not own:
        options = "".join(f'<option value="{_e(key)}">{_e(label)}</option>' for key, label in boards.REPORT_REASONS.items())
        bits.append(f'<details class="disc-report"><summary class="disc-action">Report</summary>'
                    f'<form data-disc-report{target}><label>Why are you reporting this?<select name="reason" required>{options}</select></label>'
                    '<button type="submit" class="disc-action disc-action--solid">Send report</button>'
                    '<p class="disc-report__status" role="status" aria-live="polite"></p></form></details>')
    if is_moderator(viewer):
        hide = "restore" if post.hidden_at else "hide"
        spoil = "unspoiler" if post.spoiler else "spoiler"
        bits.append(f'<button type="button" class="disc-action disc-action--mod" data-disc-mod="{hide}"{target}>'
                    f'{"Restore" if hide == "restore" else "Hide"}</button>')
        bits.append(f'<button type="button" class="disc-action disc-action--mod" data-disc-mod="{spoil}"{target}>'
                    f'{"Unmark spoilers" if post.spoiler else "Mark spoilers"}</button>')
        if is_thread:
            lock = "unlock" if thread.locked_at else "lock"
            bits.append(f'<button type="button" class="disc-action disc-action--mod" data-disc-mod="{lock}">'
                        f'{"Unlock" if thread.locked_at else "Lock"}</button>')
        if not own:
            bits.append(f'<button type="button" class="disc-action disc-action--mod" data-disc-delete{target}>Delete</button>')
    return f'<div class="disc-actions">{"".join(bits)}</div>'


def _hidden_note(post) -> str:
    if not post.hidden_at:
        return ""
    return ('<p class="disc-hidden-note">Hidden from everyone else after reports. A moderator will look at it and '
            'restore or remove it.</p>')


@router.get("/titles/{kind}/{slug}/discussions/{thread_id}", include_in_schema=False)
def thread_page(kind: str, slug: str, thread_id: PositiveDatabaseId,
                user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown title type")
    try:
        thread = boards.get_thread(db, thread_id, user, kind=kind)
    except boards.DiscussionError as error:
        _fail(error)
    if thread.slug != slug:
        return _moved(boards.thread_path(thread))
    group = title_pages.find(db, kind, slug)
    title_path = group.path if group is not None and group.path.rsplit("/", 1)[1] == slug else None
    replies = boards.visible_replies(db, thread, user)
    people = boards.authors(db, [thread.user_id] + [reply.user_id for reply in replies])
    starter = people.get(thread.user_id)
    path = boards.thread_path(thread)
    board = boards.board_path(kind, slug)
    edited = ' <span class="disc-muted">(edited)</span>' if thread.edited_at else ""
    if thread.deleted_at:
        opening = ('<article class="disc-post disc-post--op" id="post"><p class="disc-muted">The person who started this '
                   'discussion deleted their post. The replies below are still here.</p></article>')
    else:
        opening = (f'<article class="disc-post disc-post--op" id="post"><header class="disc-post__head">{_author_html(starter)}'
                   f'<span class="disc-post__when">{_time_html(thread.created_at)}{edited}</span></header>'
                   f'{_hidden_note(thread)}<div class="disc-post__content" data-raw="{_e(thread.body)}" data-spoiler="{str(thread.spoiler).lower()}">'
                   f'{_body_html(thread)}</div>{_post_actions(kind, thread, user, is_thread=True, thread=thread)}</article>')
    reply_cards = []
    for number, post in enumerate(replies, start=1):
        post_edited = ' <span class="disc-muted">(edited)</span>' if post.edited_at else ""
        mine = " disc-post--mine" if user is not None and user.id == post.user_id else ""
        starter_tag = ' <span class="disc-tag disc-tag--op">Started it</span>' if post.user_id == thread.user_id else ""
        reply_cards.append(
            f'<article class="disc-post{mine}" id="reply-{post.id}"><header class="disc-post__head">'
            f'{_author_html(people.get(post.user_id))}{starter_tag}'
            f'<span class="disc-post__when"><a href="#reply-{post.id}">#{number}</a> · {_time_html(post.created_at)}{post_edited}</span></header>'
            f'{_hidden_note(post)}<div class="disc-post__content" data-raw="{_e(post.body)}" data-spoiler="{str(post.spoiler).lower()}">'
            f'{_body_html(post)}</div>{_post_actions(kind, post, user, is_thread=False, thread=thread)}</article>')
    count = len([post for post in replies if not post.hidden_at])
    replies_html = (f'<h2 class="disc-replies__title" id="replies">{count} repl{"y" if count == 1 else "ies"}</h2>'
                    f'<div class="disc-replies">{"".join(reply_cards)}</div>' if reply_cards else
                    '<h2 class="disc-replies__title" id="replies">No replies yet</h2>'
                    '<p class="disc-muted">Be the first to answer.</p>')
    if thread.locked_at:
        composer = '<p class="disc-closed">A moderator locked this discussion, so it isn\'t taking new replies.</p>'
    elif thread.hidden_at or thread.deleted_at and not thread.reply_count:
        composer = ""
    elif user is None:
        composer = _guest_prompt(path + "#reply", "join the discussion")
    else:
        composer = (f'<form class="disc-form disc-reply" id="reply" data-disc-reply novalidate>'
                    '<label class="disc-form__label" for="discReply">Add a reply</label>'
                    f'<textarea id="discReply" name="body" rows="4" maxlength="{boards.REPLY_BODY_MAX}" required '
                    'placeholder="What do you think?"></textarea>'
                    f'{_composer_tips()}'
                    '<label class="disc-form__check"><input name="spoiler" type="checkbox"> My reply has spoilers</label>'
                    '<div class="disc-form__row"><button type="submit" class="site-btn site-btn--primary">Post reply</button>'
                    '<p class="disc-form__status" role="status" aria-live="polite"></p></div></form>')
    title = thread.title
    meta = (f'Started by {_author_html(starter) if not thread.deleted_at else "a member"} · {_time_html(thread.created_at)}'
            f' · in <a href="{_e(board)}">{_e(title)} discussions</a>')
    heading_flags = '<span class="disc-tag disc-tag--muted">Locked</span> ' if thread.locked_at else ""
    head = _head_html(kind, title, title_path, _poster(db, group), thread.subject, heading_flags + meta, board=board)
    back = (f'<p class="disc-back"><a href="{_e(board)}">← All {_e(title)} discussions</a>'
            + (f' · <a href="{_e(title_path)}">{_e(title)} reviews and details</a>' if title_path else "") + '</p>')
    body = (head + f'<div class="site-wrap disc-wrap"><div class="disc-main" data-disc-thread="{_e(thread.id)}">'
            f'{opening}{replies_html}{composer}{back}</div>{_rules_aside()}</div>')
    # Hidden posts only reach their authors and moderators, so they never count towards indexing.
    indexable = title_path is not None and boards.is_indexable(thread, [r for r in replies if not r.hidden_at])
    # A deleted opening post (older ones still have their text stored) must not live on in the description.
    description = (f"{thread.subject}: a discussion about {title} on OmniTrackr. "
                   + ("" if thread.deleted_at else "Contains spoilers." if thread.spoiler
                      else boards.plain_excerpt(thread.body, 110))).strip()
    structured = ""
    if not thread.deleted_at and not thread.hidden_at:
        posting = {
            "@context": "https://schema.org", "@type": "DiscussionForumPosting", "headline": thread.subject,
            "url": SITE_URL + path, "datePublished": thread.created_at.isoformat(timespec="seconds") + "Z",
            "author": {"@type": "Person", "name": starter.username if starter else "OmniTrackr member",
                       **({"url": SITE_URL + starter.profile_url} if starter and starter.profile_url else {})},
            "interactionStatistic": {"@type": "InteractionCounter", "interactionType": "https://schema.org/CommentAction",
                                     "userInteractionCount": count},
            "about": {"@type": "CreativeWork", "name": title, **({"url": SITE_URL + title_path} if title_path else {})},
        }
        if not thread.spoiler:
            posting["text"] = boards.plain_excerpt(thread.body, 5000)
        comments = []
        for post in replies:
            if post.hidden_at or post.spoiler:
                continue
            who = people.get(post.user_id)
            comments.append({"@type": "Comment", "text": boards.plain_excerpt(post.body, 3000),
                             "datePublished": post.created_at.isoformat(timespec="seconds") + "Z",
                             "author": {"@type": "Person", "name": who.username if who else "OmniTrackr member"}})
        if comments:
            posting["comment"] = comments[:100]
        structured = f'<script type="application/ld+json">{_script_json(posting)}</script>'
    html = _page(title=f"{thread.subject} - {title} discussion | OmniTrackr", description=boards.plain_excerpt(description, 158),
                 canonical=SITE_URL + path, robots="index, follow" if indexable else "noindex, follow", body=body,
                 structured=structured, image=_poster(db, group), signed_in=user is not None)
    response = strict_html_response(html)
    response.headers["Cache-Control"] = "private, no-store" if user is not None else "public, max-age=60"
    response.headers["Vary"] = "Cookie"
    if not indexable:
        response.headers["X-Robots-Tag"] = "noindex, follow"
    return response


@router.get("/discussions/moderation", include_in_schema=False)
def moderation_page(user=Depends(get_optional_current_user), db: Session = Depends(get_db)):
    if user is None or not is_moderator(user):
        raise HTTPException(404, "Not found")
    queue = boards.moderation_queue(db)
    rows = []
    for entry in queue:
        thread = entry["thread"]
        target = "" if entry["target"] == "thread" else f' data-reply-id="{_e(entry["id"])}"'
        link = boards.thread_path(thread) + ("" if entry["target"] == "thread" else f'#reply-{entry["id"]}')
        state = '<span class="disc-tag">Hidden</span>' if entry["hidden"] else '<span class="disc-tag disc-tag--muted">Visible</span>'
        reasons = ", ".join(entry["reasons"]) or "Hidden by a moderator"
        rows.append(
            f'<article class="disc-post" data-disc-thread="{_e(thread.id)}"><header class="disc-post__head">{state} '
            f'<a href="{_e(link)}">{_e(thread.subject)}</a> <span class="disc-muted">on {_e(thread.title)}, by {_e(entry["author"])}</span></header>'
            f'<p class="disc-muted">{entry["reports"]} open report{"s" if entry["reports"] != 1 else ""}: {_e(reasons)}</p>'
            f'<div class="disc-body">{boards.body_html(entry["body"])}</div><div class="disc-actions">'
            f'<button type="button" class="disc-action disc-action--mod" data-disc-mod="restore"{target}>Keep it up</button>'
            f'<button type="button" class="disc-action disc-action--mod" data-disc-mod="hide"{target}>Hide it</button>'
            f'<button type="button" class="disc-action disc-action--mod" data-disc-mod="spoiler"{target}>Mark spoilers</button>'
            f'<button type="button" class="disc-action disc-action--mod" data-disc-delete{target}>Delete</button></div></article>')
    content = "".join(rows) or '<p class="disc-muted">Nothing waiting. Reported and hidden posts show up here.</p>'
    body = (f'<header class="disc-head"><div class="site-wrap"><h1>Discussion reports</h1>'
            f'<p class="disc-head__meta">{len(queue)} post{"s" if len(queue) != 1 else ""} to look at</p></div></header>'
            f'<div class="site-wrap disc-wrap disc-wrap--single"><div class="disc-main">{content}</div></div>')
    response = strict_html_response(_page(title="Discussion reports | OmniTrackr", description="Moderation queue",
                                          canonical=SITE_URL + "/discussions/moderation", robots="noindex, nofollow",
                                          body=body, signed_in=True))
    _private(response)
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


# ---------------------------------------------------------------- API

class ThreadCreate(BaseModel):
    subject: str = Field(..., max_length=boards.SUBJECT_MAX + 40)
    body: str = Field(..., max_length=boards.THREAD_BODY_MAX + 200)
    spoiler: bool = False


class ReplyCreate(BaseModel):
    body: str = Field(..., max_length=boards.REPLY_BODY_MAX + 200)
    spoiler: bool = False


class PostEdit(BaseModel):
    body: str = Field(..., max_length=boards.THREAD_BODY_MAX + 200)
    spoiler: Optional[bool] = None
    reply_id: Optional[PositiveDatabaseId] = None


class PostReport(BaseModel):
    reason: str = Field(..., max_length=20)
    reply_id: Optional[PositiveDatabaseId] = None


class PostModerate(BaseModel):
    action: Literal["hide", "restore", "lock", "unlock", "spoiler", "unspoiler"]
    reply_id: Optional[PositiveDatabaseId] = None


def _thread(db: Session, thread_id: int, user) -> models.TitleDiscussion:
    try:
        return boards.get_thread(db, thread_id, user)
    except boards.DiscussionError as error:
        _fail(error)


@router.get("/api/titles/{kind}/{slug}/discussions")
def list_threads(kind: str, slug: str, response: Response, page: int = Query(1, ge=1, le=1000),
                 db: Session = Depends(get_db)):
    if kind not in title_pages.KINDS:
        raise HTTPException(404, "Unknown title type")
    threads = boards.board_threads(db, kind, slug, offset=(page - 1) * boards.BOARD_PAGE_SIZE)
    people = boards.authors(db, [thread.user_id for thread in threads])
    response.headers["Cache-Control"] = "public, max-age=60"
    return {"count": boards.board_count(db, kind, slug), "threads": [{
        "id": t.id, "url": boards.thread_path(t), "subject": t.subject, "replies": t.reply_count,
        "spoiler": t.spoiler, "locked": bool(t.locked_at), "deleted": bool(t.deleted_at),
        "excerpt": None if t.spoiler or t.deleted_at else boards.plain_excerpt(t.body),
        "author": people[t.user_id].username if t.user_id in people else None,
        "created_at": t.created_at.isoformat(), "last_activity_at": t.last_activity_at.isoformat(),
    } for t in threads]}


@router.post("/api/titles/{kind}/{slug}/discussions", status_code=201)
def start_thread(kind: str, slug: str, payload: ThreadCreate, request: Request, response: Response,
                 user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    group = title_pages.find(db, kind, slug)
    if group is None:
        raise HTTPException(404, "Title not found")
    try:
        thread = boards.start(db, user, group, payload.subject, payload.body, payload.spoiler)
    except boards.DiscussionError as error:
        _fail(error)
    return {"id": thread.id, "url": boards.thread_path(thread)}


@router.post("/api/discussions/{thread_id}/replies", status_code=201)
def add_reply(thread_id: PositiveDatabaseId, payload: ReplyCreate, request: Request, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    thread = _thread(db, thread_id, user)
    try:
        post = boards.reply(db, user, thread, payload.body, payload.spoiler)
    except boards.DiscussionError as error:
        _fail(error)
    return {"id": post.id, "url": f"{boards.thread_path(thread)}#reply-{post.id}"}


@router.patch("/api/discussions/{thread_id}")
def edit_post(thread_id: PositiveDatabaseId, payload: PostEdit, request: Request, response: Response,
              user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    thread = _thread(db, thread_id, user)
    try:
        post = boards.edit(db, user, thread, payload.reply_id, payload.body, payload.spoiler)
    except boards.DiscussionError as error:
        _fail(error)
    return {"body_html": boards.body_html(post.body), "spoiler": post.spoiler}


@router.delete("/api/discussions/{thread_id}")
def delete_thread(thread_id: PositiveDatabaseId, response: Response, reply_id: Optional[PositiveDatabaseId] = None,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    thread = _thread(db, thread_id, user)
    board = boards.board_path(thread.kind, thread.slug)
    try:
        if reply_id is not None:
            boards.delete_reply(db, user, thread, reply_id)
            return {"state": "deleted", "board": board}
        return {"state": boards.delete_thread(db, user, thread), "board": board}
    except boards.DiscussionError as error:
        _fail(error)


@router.post("/api/discussions/{thread_id}/report")
def report_post(thread_id: PositiveDatabaseId, payload: PostReport, request: Request, response: Response,
                user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    thread = _thread(db, thread_id, user)
    try:
        return boards.report(db, user, thread, payload.reply_id, payload.reason)
    except boards.DiscussionError as error:
        _fail(error)


@router.post("/api/discussions/{thread_id}/moderate")
def moderate_post(thread_id: PositiveDatabaseId, payload: PostModerate, response: Response,
                  user=Depends(get_current_user), db: Session = Depends(get_db)):
    _private(response)
    if not is_moderator(user):
        raise HTTPException(403, "Only moderators can do that.")
    thread = _thread(db, thread_id, user)
    try:
        return boards.moderate(db, user, thread, payload.reply_id, payload.action)
    except boards.DiscussionError as error:
        _fail(error)
