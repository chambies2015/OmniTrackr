"""Lets a guest's save bar open the "Keep your list" sheet on the page they are reading.

Guides, title pages and shelves let visitors save titles without an account
(static/guest-list.js). Their sign-up links used to send people to the bottom of
the homepage, away from what they were reading. On a page that has a save bar or
a save button, this html_finish step marks <body> with data-guest-sheet, and
guest-list.js then opens a small sheet in place: the saved titles, Continue with
Google (when the owner set it up) and Sign up with email. The sheet only ever
opens when a visitor who has saved something presses a sign-up link themselves.
"""
from __future__ import annotations

import re

from . import google_signin

_BODY = re.compile(r"<body(?=[\s>])")
# The homepage and the signed-out dashboard have the sign-up form itself.
_HAS_FORM = ('id="registerForm"', 'id="authDialog"')


def mark_guest_pages(html: str) -> str:
    if "data-guest-bar" not in html and "data-guest-save" not in html:
        return html
    if "data-guest-sheet" in html or any(marker in html for marker in _HAS_FORM):
        return html
    mode = "google" if google_signin.configured() else "email"
    return _BODY.sub(f'<body data-guest-sheet="{mode}"', html, count=1)
