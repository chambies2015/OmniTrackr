"""
External API proxy endpoints for the OmniTrackr API.
"""
import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
import httpx

from .. import models
from ..dependencies import get_current_user

router = APIRouter(tags=["proxy"])

@router.get("/api/proxy/omdb")
async def proxy_omdb_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    title: str = Query(..., description="Movie/TV show title", max_length=200),
    year: Optional[str] = Query(None, description="Release year", max_length=4),
    type: Optional[str] = Query(None, description="Type: movie, series, or episode", max_length=20)
):
    """Proxy endpoint for OMDB API. Keeps API key secure on server."""
    omdb_key = os.getenv("OMDB_API_KEY", "")
    if not omdb_key:
        raise HTTPException(status_code=503, detail="OMDB API key not configured")
    
    if len(title) > 200:
        raise HTTPException(status_code=400, detail="Title too long")
    
    try:
        base_url = "https://www.omdbapi.com/"
        params = {
            "t": title[:200],
            "apikey": omdb_key
        }
        if year and len(year) <= 4:
            params["y"] = year
        if type and type in ["movie", "series", "episode"]:
            params["type"] = type
        
        response = await request.app.state.external_api_client.get(base_url, params=params)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="OMDB API rate limit reached")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="OMDB API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="OMDB API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OMDB API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="OMDB API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from OMDB API")


@router.get("/api/proxy/rawg")
async def proxy_rawg_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    search: str = Query(..., description="Game title to search", max_length=200)
):
    """Proxy endpoint for RAWG API. Keeps API key secure on server."""
    rawg_key = os.getenv("RAWG_API_KEY", "")
    if not rawg_key:
        raise HTTPException(status_code=503, detail="RAWG API key not configured")
    
    if len(search) > 200:
        raise HTTPException(status_code=400, detail="Search term too long")
    
    try:
        base_url = "https://api.rawg.io/api/games"
        params = {
            "search": search[:200],
            "key": rawg_key
        }
        
        response = await request.app.state.external_api_client.get(base_url, params=params)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="RAWG API rate limit reached")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="RAWG API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="RAWG API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="RAWG API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="RAWG API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from RAWG API")


@router.get("/api/proxy/jikan")
async def proxy_jikan_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    query: str = Query(..., description="Anime title to search", max_length=200)
):
    """Proxy endpoint for Jikan API (MyAnimeList). No API key required."""
    if len(query) > 200:
        raise HTTPException(status_code=400, detail="Search query too long")
    
    try:
        base_url = "https://api.jikan.moe/v4/anime"
        params = {
            "q": query[:200],
            "limit": 1
        }
        
        response = await request.app.state.external_api_client.get(base_url, params=params)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Jikan API rate limit reached")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="Jikan API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="Jikan API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Jikan API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="Jikan API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from Jikan API")


@router.get("/api/proxy/itunes")
async def proxy_itunes_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    query: str = Query(..., description="Music title/artist to search", max_length=200),
    entity: str = Query("album", description="Search entity: album, song, or musicArtist", max_length=20)
):
    """Proxy endpoint for iTunes Search API. Free, no API key required."""
    if len(query) > 200:
        raise HTTPException(status_code=400, detail="Search query too long")
    
    if entity not in ["album", "song", "musicArtist"]:
        raise HTTPException(status_code=400, detail="Entity must be album, song, or musicArtist")
    
    try:
        base_url = "https://itunes.apple.com/search"
        params = {
            "term": query[:200],
            "entity": entity,
            "limit": 10,
            "media": "music"
        }
        
        response = await request.app.state.external_api_client.get(base_url, params=params)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="iTunes API rate limit reached")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="iTunes API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="iTunes API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="iTunes API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="iTunes API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from iTunes API")


@router.get("/api/proxy/openlibrary")
async def proxy_openlibrary_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    query: str = Query(..., description="Book title/author to search", max_length=200),
    isbn: Optional[str] = Query(None, description="ISBN to search by", max_length=20)
):
    """Proxy endpoint for Open Library API. No API key required."""
    if len(query) > 200:
        raise HTTPException(status_code=400, detail="Search query too long")
    
    try:
        if isbn:
            base_url = f"https://openlibrary.org/isbn/{isbn[:20]}.json"
            params = {}
        else:
            base_url = "https://openlibrary.org/search.json"
            params = {
                "q": query[:200],
                "limit": 10
            }
        
        response = await request.app.state.external_api_client.get(base_url, params=params)
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Open Library API rate limit reached")
        response.raise_for_status()
        return response.json()
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="Open Library API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="Open Library API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Open Library API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="Open Library API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from Open Library API")


def _jikan_person_name(name: str) -> str:
    """MyAnimeList stores "Oda, Eiichiro"; readers know "Eiichiro Oda"."""
    family, _, given = (name or "").partition(", ")
    return f"{given} {family}".strip() if given else (name or "").strip()


def normalize_jikan_manga(entry: dict) -> dict:
    published = (entry.get("published") or {}).get("prop", {}).get("from", {}) or {}
    images = (entry.get("images") or {}).get("jpg") or {}
    genres = [genre.get("name") for genre in (entry.get("genres") or []) + (entry.get("demographics") or []) if genre.get("name")]
    authors = [_jikan_person_name(author.get("name", "")) for author in entry.get("authors") or []]
    return {
        "mal_id": entry.get("mal_id"),
        "title": entry.get("title_english") or entry.get("title") or "",
        "original_title": entry.get("title") or "",
        "type": entry.get("type") or "Manga",
        "author": ", ".join(name for name in authors[:2] if name) or None,
        "year": published.get("year"),
        "genre": ", ".join(genres[:3]) or None,
        "volumes": entry.get("volumes"),
        "chapters": entry.get("chapters"),
        "status": entry.get("status"),
        "cover_art_url": images.get("large_image_url") or images.get("image_url"),
    }


@router.get("/api/proxy/jikan-manga")
async def proxy_jikan_manga_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    query: str = Query(..., description="Manga, manhwa or manhua title to search", max_length=200)
):
    """Proxy endpoint for Jikan's manga search (MyAnimeList). No API key required.

    Results come back already shaped for the manga form, safe-for-work only.
    """
    try:
        response = await request.app.state.external_api_client.get(
            "https://api.jikan.moe/v4/manga", params={"q": query[:200], "limit": 10, "sfw": "true"},
        )
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="Jikan API rate limit reached")
        response.raise_for_status()
        entries = response.json().get("data") or []
        return {"results": [normalize_jikan_manga(entry) for entry in entries if isinstance(entry, dict)]}
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="Jikan API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="Jikan API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Jikan API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="Jikan API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from Jikan API")


def normalize_itunes_podcast(entry: dict) -> dict:
    genres = [genre for genre in entry.get("genres") or [] if isinstance(genre, str) and genre != "Podcasts"]
    if not genres and entry.get("primaryGenreName") and entry.get("primaryGenreName") != "Podcasts":
        genres = [entry["primaryGenreName"]]
    episodes = entry.get("trackCount")
    return {
        "itunes_id": entry.get("collectionId") or entry.get("trackId"),
        "title": entry.get("collectionName") or entry.get("trackName") or "",
        "host": entry.get("artistName") or None,
        "genre": ", ".join(genres[:3]) or None,
        "episodes": episodes if isinstance(episodes, int) and episodes > 0 else None,
        # Apple gives the date of the newest episode, not the year the show began.
        "latest_episode": (entry.get("releaseDate") or "")[:10] or None,
        "cover_art_url": entry.get("artworkUrl600") or entry.get("artworkUrl100"),
        "url": entry.get("collectionViewUrl"),
    }


@router.get("/api/proxy/itunes-podcasts")
async def proxy_itunes_podcast_api(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    query: str = Query(..., description="Podcast title or host to search", max_length=200)
):
    """Proxy endpoint for the Apple Podcasts directory (iTunes Search API). No API key required.

    Results come back already shaped for the podcast form.
    """
    try:
        response = await request.app.state.external_api_client.get(
            "https://itunes.apple.com/search",
            params={"term": query[:200], "media": "podcast", "entity": "podcast", "limit": 10},
        )
        if response.status_code == 429:
            raise HTTPException(status_code=429, detail="iTunes API rate limit reached")
        response.raise_for_status()
        entries = response.json().get("results") or []
        return {"results": [normalize_itunes_podcast(entry) for entry in entries if isinstance(entry, dict)]}
    except HTTPException:
        raise
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="iTunes API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail="iTunes API request failed")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="iTunes API request timeout - may be due to network issues or VPN blocking")
    except httpx.TransportError:
        raise HTTPException(status_code=504, detail="iTunes API connection error - may be due to network issues or VPN blocking")
    except Exception:
        raise HTTPException(status_code=500, detail="Error fetching from iTunes API")
