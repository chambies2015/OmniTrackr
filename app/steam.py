"""Read a member's owned games from the Steam Web API for the Import Studio.

Only three fixed endpoints on api.steampowered.com are ever called, with a
profile id that has already been reduced to digits or a vanity name. The key
comes from ``STEAM_WEB_API_KEY``; without it the Steam option is hidden and
the endpoint says so.

The result is handed to the browser, which turns it into an ordinary import
file, so Steam games go through the same preview, duplicate check and
confirmation as every other export (see ``import_formats._steam_rows``).
"""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

API_ROOT = "https://api.steampowered.com"
PATHS = {
    "resolve": "/ISteamUser/ResolveVanityURL/v1/",
    "owned": "/IPlayerService/GetOwnedGames/v1/",
    "summary": "/ISteamUser/GetPlayerSummaries/v2/",
}
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
MAX_GAMES = 5000  # the Import Studio's row limit
MAX_MINUTES = 60 * 24 * 365 * 5  # five years of play; anything above is bad data
STEAM_ID_RE = re.compile(r"7656119\d{10}")
VANITY_RE = re.compile(r"[A-Za-z0-9_-]{2,32}")
PROFILE_URL_RE = re.compile(
    r"(?:https?://)?(?:www\.)?steamcommunity\.com/(id|profiles)/([^/?#\s]+)/?(?:[?#].*)?", re.IGNORECASE)
COVER_URL = "https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
STORE_URL = "https://store.steampowered.com/app/{appid}/"

PRIVATE_MESSAGE = (
    "Steam didn't return any games for this profile. On Steam, open your profile, choose Edit Profile, "
    "then Privacy Settings, and set Game details to Public. You can switch it back after importing."
)


class SteamError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def api_key() -> str:
    return os.getenv("STEAM_WEB_API_KEY", "").strip()


def enabled() -> bool:
    return bool(api_key())


def parse_profile(text: str) -> tuple[str, str]:
    """("id", 64-bit id) or ("vanity", name) from what a member typed. Anything else is refused."""
    value = (text or "").strip()
    if len(value) > 200:
        raise SteamError(400, "That doesn't look like a Steam profile. Paste your profile link or your 17-digit Steam ID.")
    match = PROFILE_URL_RE.fullmatch(value)
    if match:
        kind, part = match.group(1).lower(), match.group(2)
        if kind == "profiles" and STEAM_ID_RE.fullmatch(part):
            return "id", part
        if kind == "id" and VANITY_RE.fullmatch(part):
            return "vanity", part
        raise SteamError(400, "That Steam profile link isn't complete. Copy it from the address bar on your Steam profile.")
    if STEAM_ID_RE.fullmatch(value):
        return "id", value
    if VANITY_RE.fullmatch(value):
        return "vanity", value
    raise SteamError(400, "That doesn't look like a Steam profile. Paste your profile link or your 17-digit Steam ID.")


async def _get(client: httpx.AsyncClient, name: str, params: dict[str, Any]) -> dict:
    try:
        response = await client.get(API_ROOT + PATHS[name], params={**params, "key": api_key(), "format": "json"},
                                    timeout=TIMEOUT, follow_redirects=False)
    except httpx.TimeoutException as exc:
        raise SteamError(504, "Steam took too long to answer. Try again in a minute.") from exc
    except httpx.HTTPError as exc:
        raise SteamError(502, "Steam couldn't be reached. Try again shortly.") from exc
    if response.status_code == 429:
        raise SteamError(503, "Steam is busy right now. Try again in a few minutes.")
    if response.status_code in (401, 403):
        # The key itself was refused; members can't fix that, so don't send them to their settings.
        raise SteamError(503, "Steam import isn't working right now. Try again later.")
    if response.status_code != 200:
        raise SteamError(502, "Steam couldn't be reached. Try again shortly.")
    try:
        data = response.json()
    except ValueError as exc:
        raise SteamError(502, "Steam sent an answer that couldn't be read. Try again shortly.") from exc
    return data if isinstance(data, dict) else {}


async def resolve(client: httpx.AsyncClient, kind: str, value: str) -> str:
    if kind == "id":
        return value
    data = (await _get(client, "resolve", {"vanityurl": value})).get("response") or {}
    steam_id = str(data.get("steamid") or "")
    if data.get("success") != 1 or not STEAM_ID_RE.fullmatch(steam_id):
        raise SteamError(404, f"Steam has no profile at steamcommunity.com/id/{value}. Check the link on your Steam profile.")
    return steam_id


async def _persona(client: httpx.AsyncClient, steam_id: str) -> str:
    try:
        data = await _get(client, "summary", {"steamids": steam_id})
    except SteamError:
        return ""  # The name is only a label; the games still matter.
    players = (data.get("response") or {}).get("players") or []
    name = str((players[0] or {}).get("personaname") or "") if players else ""
    return " ".join(name.split())[:64]


def _minutes(value: Any) -> int:
    return min(value, MAX_MINUTES) if type(value) is int and value > 0 else 0


def _games(data: dict) -> list[dict]:
    games = []
    seen = set()
    for game in (data.get("response") or {}).get("games") or []:
        if not isinstance(game, dict):
            continue
        appid = game.get("appid")
        name = " ".join(str(game.get("name") or "").split())[:200]
        if type(appid) is not int or appid <= 0 or not name or appid in seen:
            continue
        seen.add(appid)
        last = game.get("rtime_last_played")
        last_played = (datetime.fromtimestamp(last, tz=timezone.utc).date().isoformat()
                       if type(last) is int and last > 0 else None)
        games.append({"appid": appid, "name": name, "minutes": _minutes(game.get("playtime_forever")),
                      "last_played": last_played})
    # Most played first, so a cap drops the games played least.
    games.sort(key=lambda game: (-game["minutes"], game["name"].casefold()))
    return games[:MAX_GAMES]


async def library(client: httpx.AsyncClient, profile: str) -> dict:
    """The member's games as an import document: {source, steam_id, persona, games, truncated}."""
    if not enabled():
        raise SteamError(503, "Steam import isn't set up on this site yet.")
    kind, value = parse_profile(profile)
    steam_id = await resolve(client, kind, value)
    data = await _get(client, "owned", {"steamid": steam_id, "include_appinfo": 1,
                                        "include_played_free_games": 1})
    games = _games(data)
    if not games:
        raise SteamError(404, PRIVATE_MESSAGE)
    total = (data.get("response") or {}).get("game_count")
    return {
        "source": "steam", "steam_id": steam_id, "persona": await _persona(client, steam_id),
        "games": games, "truncated": type(total) is int and total > len(games),
    }


def cover_url(appid: int) -> str:
    return COVER_URL.format(appid=appid)


def store_url(appid: int) -> str:
    return STORE_URL.format(appid=appid)
