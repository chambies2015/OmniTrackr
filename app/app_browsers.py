"""Browsers built into other apps (Instagram, Facebook, TikTok...), where Google sign-in can't work.

Links opened inside Instagram, Facebook, TikTok, Snapchat and similar apps load in the
app's own browser. Google refuses to sign anyone in there: its page answers
"Error 403: disallowed_useragent". Before Nov 26 2026 the Continue with Google button
led straight to that error, and Google was the only way anyone had signed up.

/auth/google/start now sends a visitor in one of these browsers to /continue, which
explains, opens the same sign-up in Chrome on Android, and gives everyone a link that
carries the titles they saved over to Safari or Chrome (see static/continue.js).

Only names we are sure of are matched, and a visitor can always press "Try Google
here anyway". A wrong match costs one extra tap; a miss leaves things as they were.
Safari, Chrome and the in-app views that are really Safari or Chrome (Reddit, X,
Discord, home-screen apps) don't carry these names and are never matched.
"""
from __future__ import annotations

import re
from typing import Optional

# (pattern, name shown on the page). Messenger comes before Facebook because its
# user agent carries both.
APPS = (
    (re.compile(r"Instagram"), "Instagram"),
    (re.compile(r"FBAN/Messenger|MessengerForiOS|FB_IAB/Orca-Android|FB_IAB/MESSENGER"), "Messenger"),
    (re.compile(r"FBAN/|FBAV/|FB_IAB/|FBIOS"), "Facebook"),
    (re.compile(r"musical_ly|BytedanceWebview|TikTok"), "TikTok"),
    (re.compile(r"Snapchat"), "Snapchat"),
    (re.compile(r"LinkedInApp"), "LinkedIn"),
    # The app says "[Pinterest/iOS]" or "[Pinterest/Android]"; its crawler says "Pinterest/0.2 (+...bot.html)".
    (re.compile(r"\[Pinterest/|Pinterest for iOS"), "Pinterest"),
    (re.compile(r"\bLine/\d"), "LINE"),
    (re.compile(r"MicroMessenger"), "WeChat"),
    (re.compile(r"KAKAOTALK"), "KakaoTalk"),
)
# Any other Android app showing pages in its own WebView ("; wv)" in the user agent).
ANDROID_WEBVIEW = re.compile(r"Android[^)]*; wv\)")
OTHER_APP = "this app"
MAX_AGENT = 600


def app_name(user_agent: Optional[str]) -> Optional[str]:
    """The app whose built-in browser this is, OTHER_APP for an unnamed Android app, or None."""
    agent = (user_agent or "")[:MAX_AGENT]
    if not agent:
        return None
    for pattern, name in APPS:
        if pattern.search(agent):
            return name
    if ANDROID_WEBVIEW.search(agent):
        return OTHER_APP
    return None


def platform(user_agent: Optional[str]) -> str:
    """"ios", "android" or "other", for which steps the page shows."""
    agent = user_agent or ""
    if re.search(r"iPhone|iPad|iPod", agent):
        return "ios"
    if "Android" in agent:
        return "android"
    return "other"


def is_phone(user_agent: Optional[str]) -> bool:
    """Phones only, the way Site stats splits devices (site_traffic.classify_device)."""
    from .site_traffic import classify_device
    return classify_device(user_agent or "") == "mobile"
