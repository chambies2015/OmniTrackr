"""
External API proxy endpoints for the OmniTrackr API.
"""
import os
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
import httpx

router = APIRouter(tags=["proxy"])


def get_limiter(request: Request) -> Limiter:
    """Get limiter from app state."""
    return request.app.state.limiter


@router.get("/api/proxy/omdb")
async def proxy_omdb_api(
    request: Request,
    title: str = Query(..., description="Movie/TV show title"),
    year: Optional[str] = Query(None, description="Release year"),
    type: Optional[str] = Query(None, description="Type: movie, series, or episode")
):
    """Proxy endpoint for OMDB API. Keeps API key secure on server."""
    omdb_key = os.getenv("OMDB_API_KEY", "")
    if not omdb_key:
        raise HTTPException(status_code=503, detail="OMDB API key not configured")
    
    try:
        url = f"https://www.omdbapi.com/?t={title}"
        if year:
            url += f"&y={year}"
        if type:
            url += f"&type={type}"
        url += f"&apikey={omdb_key}"
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
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
    search: str = Query(..., description="Game title to search")
):
    """Proxy endpoint for RAWG API. Keeps API key secure on server."""
    rawg_key = os.getenv("RAWG_API_KEY", "")
    if not rawg_key:
        raise HTTPException(status_code=503, detail="RAWG API key not configured")
    
    try:
        url = f"https://api.rawg.io/api/games?search={search}&key={rawg_key}"
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
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
    query: str = Query(..., description="Anime title to search")
):
    """Proxy endpoint for Jikan API (MyAnimeList). No API key required."""
    try:
        url = f"https://api.jikan.moe/v4/anime?q={query}&limit=1"
        
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
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
