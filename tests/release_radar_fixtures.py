"""Offline Release Radar providers backed by the JSON fixtures in tests/fixtures."""
import json
from datetime import date
from pathlib import Path

from app import release_radar as radar

FIXTURES = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def movies(client, window):
    data = load("release_radar_wikidata.json")
    return radar.normalize_wikidata(data["candidates"], data["details"], window)


async def tv(client, window):
    return radar.normalize_tvmaze(load("release_radar_tvmaze.json"), window)


async def anime(client, window):
    return radar.normalize_anilist(load("release_radar_anilist.json"), window)


async def games(client, window):
    return radar.normalize_rawg(load("release_radar_rawg.json")["results"], window)


FIXTURE_PROVIDERS = {"movies": movies, "tv": tv, "anime": anime, "games": games}


def install_fixture_providers(today=date(2026, 9, 27), monkeypatch=None):
    """Point the radar at fixtures and pin "today". Returns a fresh cache."""
    cache = radar.RadarCache(None)
    if monkeypatch is not None:
        for category, provider in FIXTURE_PROVIDERS.items():
            monkeypatch.setitem(radar.PROVIDERS, category, provider)
        monkeypatch.setattr(radar, "today_utc", lambda: today)
        monkeypatch.setattr(radar, "CACHE", cache)
    else:
        radar.PROVIDERS.update(FIXTURE_PROVIDERS)
        radar.today_utc = lambda: today
        radar.CACHE = cache
    return cache
