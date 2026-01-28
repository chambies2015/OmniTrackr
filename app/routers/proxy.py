"""
External API proxy endpoints for the OmniTrackr API.
"""
import os
from typing import Optional
from urllib.parse import quote
from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import httpx

router = APIRouter(tags=["proxy"])

ALLOWED_DOMAINS = {
    "omdb": ["www.omdbapi.com", "omdbapi.com"],
    "rawg": ["api.rawg.io"],
    "jikan": ["api.jikan.moe"],
    "itunes": ["itunes.apple.com"],
    "openlibrary": ["openlibrary.org", "covers.openlibrary.org"]
}


def get_limiter(request: Request) -> Limiter:
    """Get limiter from app state."""
    return request.app.state.limiter


@router.get("/api/proxy/omdb")
async def proxy_omdb_api(
    request: Request,
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
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="OMDB API rate limit reached")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="OMDB API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail=f"OMDB API error: {e.response.text}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="OMDB API request timeout - may be due to network issues or VPN blocking")
    except httpx.ConnectError:
        raise HTTPException(status_code=504, detail="OMDB API connection error - may be due to network issues or VPN blocking")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching from OMDB API: {str(e)}")


@router.get("/api/proxy/rawg")
async def proxy_rawg_api(
    request: Request,
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
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="RAWG API rate limit reached")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="RAWG API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail=f"RAWG API error: {e.response.text}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="RAWG API request timeout - may be due to network issues or VPN blocking")
    except httpx.ConnectError:
        raise HTTPException(status_code=504, detail="RAWG API connection error - may be due to network issues or VPN blocking")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching from RAWG API: {str(e)}")


@router.get("/api/proxy/jikan")
async def proxy_jikan_api(
    request: Request,
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
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="Jikan API rate limit reached")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="Jikan API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail=f"Jikan API error: {e.response.text}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Jikan API request timeout - may be due to network issues or VPN blocking")
    except httpx.ConnectError:
        raise HTTPException(status_code=504, detail="Jikan API connection error - may be due to network issues or VPN blocking")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching from Jikan API: {str(e)}")


@router.get("/api/proxy/itunes")
async def proxy_itunes_api(
    request: Request,
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
            "limit": 1,
            "media": "music"
        }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="iTunes API rate limit reached")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="iTunes API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail=f"iTunes API error: {e.response.text}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="iTunes API request timeout - may be due to network issues or VPN blocking")
    except httpx.ConnectError:
        raise HTTPException(status_code=504, detail="iTunes API connection error - may be due to network issues or VPN blocking")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching from iTunes API: {str(e)}")


@router.get("/api/proxy/openlibrary")
async def proxy_openlibrary_api(
    request: Request,
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
                "limit": 1
            }
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(base_url, params=params)
            if response.status_code == 429:
                raise HTTPException(status_code=429, detail="Open Library API rate limit reached")
            response.raise_for_status()
            return response.json()
    except httpx.HTTPStatusError as e:
        if e.response.status_code >= 500:
            raise HTTPException(status_code=504, detail="Open Library API server error - may be due to network issues or VPN blocking")
        raise HTTPException(status_code=e.response.status_code, detail=f"Open Library API error: {e.response.text}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Open Library API request timeout - may be due to network issues or VPN blocking")
    except httpx.ConnectError:
        raise HTTPException(status_code=504, detail="Open Library API connection error - may be due to network issues or VPN blocking")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching from Open Library API: {str(e)}")
