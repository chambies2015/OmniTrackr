"""
Public review endpoints for the OmniTrackr API.
"""
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_

from .. import models, schemas
from ..dependencies import get_db

router = APIRouter(tags=["reviews"])


@router.get("/reviews")
async def reviews_index():
    """Serve the public reviews index page."""
    html_file = os.path.join(os.path.dirname(__file__), "..", "templates", "reviews.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    raise HTTPException(status_code=404, detail="Reviews page not found")


@router.get("/reviews/{review_id}")
async def review_detail(review_id: int):
    """Serve the public review detail page."""
    html_file = os.path.join(os.path.dirname(__file__), "..", "templates", "review_detail.html")
    if os.path.exists(html_file):
        return FileResponse(html_file)
    raise HTTPException(status_code=404, detail="Review detail page not found")


@router.get("/api/public/reviews", response_model=List[dict], tags=["public"])
async def get_public_reviews(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category: movie, tv_show, anime, video_game"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of reviews to return"),
    offset: int = Query(0, ge=0, description="Number of reviews to skip")
):
    """Get public reviews from all users. Only returns entries with non-empty review text."""
    reviews = []
    
    query_conditions = []
    
    if category == "movie":
        query_conditions.append(("movie", db.query(models.Movie).filter(
            and_(
                models.Movie.review.isnot(None),
                models.Movie.review != "",
                models.Movie.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).offset(offset).limit(limit).all()))
    elif category == "tv_show":
        query_conditions.append(("tv_show", db.query(models.TVShow).filter(
            and_(
                models.TVShow.review.isnot(None),
                models.TVShow.review != "",
                models.TVShow.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).offset(offset).limit(limit).all()))
    elif category == "anime":
        query_conditions.append(("anime", db.query(models.Anime).filter(
            and_(
                models.Anime.review.isnot(None),
                models.Anime.review != "",
                models.Anime.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).offset(offset).limit(limit).all()))
    elif category == "video_game":
        query_conditions.append(("video_game", db.query(models.VideoGame).filter(
            and_(
                models.VideoGame.review.isnot(None),
                models.VideoGame.review != "",
                models.VideoGame.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).offset(offset).limit(limit).all()))
    else:
        movie_reviews = db.query(models.Movie).filter(
            and_(
                models.Movie.review.isnot(None),
                models.Movie.review != "",
                models.Movie.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).limit(limit // 4 + 1).all()
        
        tv_reviews = db.query(models.TVShow).filter(
            and_(
                models.TVShow.review.isnot(None),
                models.TVShow.review != "",
                models.TVShow.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).limit(limit // 4 + 1).all()
        
        anime_reviews = db.query(models.Anime).filter(
            and_(
                models.Anime.review.isnot(None),
                models.Anime.review != "",
                models.Anime.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).limit(limit // 4 + 1).all()
        
        vg_reviews = db.query(models.VideoGame).filter(
            and_(
                models.VideoGame.review.isnot(None),
                models.VideoGame.review != "",
                models.VideoGame.user_id.in_(
                    db.query(models.User.id).filter(models.User.is_active == True)
                )
            )
        ).limit(limit // 4 + 1).all()
        
        query_conditions = [
            ("movie", movie_reviews),
            ("tv_show", tv_reviews),
            ("anime", anime_reviews),
            ("video_game", vg_reviews)
        ]
    
    for cat, items in query_conditions:
        for item in items:
            user = db.query(models.User).filter(models.User.id == item.user_id).first()
            if not user or not user.is_active:
                continue
                
            review_data = {
                "id": item.id,
                "category": cat,
                "title": item.title,
                "review": item.review,
                "rating": item.rating,
                "username": user.username,
                "user_id": user.id,
            }
            
            if cat == "movie":
                review_data.update({
                    "director": item.director,
                    "year": item.year,
                    "poster_url": item.poster_url,
                })
            elif cat in ["tv_show", "anime"]:
                review_data.update({
                    "year": item.year,
                    "seasons": item.seasons,
                    "episodes": item.episodes,
                    "poster_url": item.poster_url,
                })
            elif cat == "video_game":
                review_data.update({
                    "release_date": item.release_date.isoformat() if item.release_date else None,
                    "genres": item.genres,
                    "cover_art_url": item.cover_art_url,
                })
            
            reviews.append(review_data)
    
    return reviews[:limit]


@router.get("/api/public/reviews/{review_id}", response_model=dict, tags=["public"])
async def get_public_review(
    review_id: int,
    category: str = Query(..., description="Category: movie, tv_show, anime, or video_game"),
    db: Session = Depends(get_db)
):
    """Get a specific public review by ID and category."""
    user_query = db.query(models.User.id).filter(models.User.is_active == True)
    
    if category == "movie":
        item = db.query(models.Movie).filter(
            and_(
                models.Movie.id == review_id,
                models.Movie.review.isnot(None),
                models.Movie.review != "",
                models.Movie.user_id.in_(user_query)
            )
        ).first()
    elif category == "tv_show":
        item = db.query(models.TVShow).filter(
            and_(
                models.TVShow.id == review_id,
                models.TVShow.review.isnot(None),
                models.TVShow.review != "",
                models.TVShow.user_id.in_(user_query)
            )
        ).first()
    elif category == "anime":
        item = db.query(models.Anime).filter(
            and_(
                models.Anime.id == review_id,
                models.Anime.review.isnot(None),
                models.Anime.review != "",
                models.Anime.user_id.in_(user_query)
            )
        ).first()
    elif category == "video_game":
        item = db.query(models.VideoGame).filter(
            and_(
                models.VideoGame.id == review_id,
                models.VideoGame.review.isnot(None),
                models.VideoGame.review != "",
                models.VideoGame.user_id.in_(user_query)
            )
        ).first()
    else:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    if not item:
        raise HTTPException(status_code=404, detail="Review not found")
    
    user = db.query(models.User).filter(models.User.id == item.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=404, detail="Review not found")
    
    review_data = {
        "id": item.id,
        "category": category,
        "title": item.title,
        "review": item.review,
        "rating": item.rating,
        "username": user.username,
        "user_id": user.id,
    }
    
    if category == "movie":
        review_data.update({
            "director": item.director,
            "year": item.year,
            "poster_url": item.poster_url,
        })
    elif category in ["tv_show", "anime"]:
        review_data.update({
            "year": item.year,
            "seasons": item.seasons,
            "episodes": item.episodes,
            "poster_url": item.poster_url,
        })
    elif category == "video_game":
        review_data.update({
            "release_date": item.release_date.isoformat() if item.release_date else None,
            "genres": item.genres,
            "cover_art_url": item.cover_art_url,
        })
    
    return review_data
