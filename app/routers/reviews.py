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


def _active_user_ids_query(db: Session):
    return db.query(models.User.id).filter(models.User.is_active == True)


@router.get("/api/public/reviews", response_model=List[dict], tags=["public"])
async def get_public_reviews(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None, description="Filter by category: movie, tv_show, anime, video_game, music, book"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of reviews to return"),
    offset: int = Query(0, ge=0, description="Number of reviews to skip")
):
    """Get public reviews from all users. Only returns entries with non-empty review text and review_public=True."""
    reviews = []
    user_ids = _active_user_ids_query(db)

    def base_filter(model_cls):
        return and_(
            model_cls.review.isnot(None),
            model_cls.review != "",
            model_cls.review_public == True,
            model_cls.user_id.in_(user_ids)
        )

    if category == "movie":
        query_conditions = [("movie", db.query(models.Movie).filter(base_filter(models.Movie)).order_by(models.Movie.id.desc()).offset(offset).limit(limit).all())]
    elif category == "tv_show":
        query_conditions = [("tv_show", db.query(models.TVShow).filter(base_filter(models.TVShow)).order_by(models.TVShow.id.desc()).offset(offset).limit(limit).all())]
    elif category == "anime":
        query_conditions = [("anime", db.query(models.Anime).filter(base_filter(models.Anime)).order_by(models.Anime.id.desc()).offset(offset).limit(limit).all())]
    elif category == "video_game":
        query_conditions = [("video_game", db.query(models.VideoGame).filter(base_filter(models.VideoGame)).order_by(models.VideoGame.id.desc()).offset(offset).limit(limit).all())]
    elif category == "music":
        query_conditions = [("music", db.query(models.Music).filter(base_filter(models.Music)).order_by(models.Music.id.desc()).offset(offset).limit(limit).all())]
    elif category == "book":
        query_conditions = [("book", db.query(models.Book).filter(base_filter(models.Book)).order_by(models.Book.id.desc()).offset(offset).limit(limit).all())]
    else:
        per_cat = (offset + limit) // 6 + 2
        query_conditions = [
            ("movie", db.query(models.Movie).filter(base_filter(models.Movie)).order_by(models.Movie.id.desc()).limit(per_cat).all()),
            ("tv_show", db.query(models.TVShow).filter(base_filter(models.TVShow)).order_by(models.TVShow.id.desc()).limit(per_cat).all()),
            ("anime", db.query(models.Anime).filter(base_filter(models.Anime)).order_by(models.Anime.id.desc()).limit(per_cat).all()),
            ("video_game", db.query(models.VideoGame).filter(base_filter(models.VideoGame)).order_by(models.VideoGame.id.desc()).limit(per_cat).all()),
            ("music", db.query(models.Music).filter(base_filter(models.Music)).order_by(models.Music.id.desc()).limit(per_cat).all()),
            ("book", db.query(models.Book).filter(base_filter(models.Book)).order_by(models.Book.id.desc()).limit(per_cat).all()),
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
            elif cat == "music":
                review_data.update({
                    "artist": item.artist,
                    "year": item.year,
                    "cover_art_url": item.cover_art_url,
                })
            elif cat == "book":
                review_data.update({
                    "author": item.author,
                    "year": item.year,
                    "cover_art_url": item.cover_art_url,
                })

            reviews.append(review_data)

    if not category:
        reviews.sort(key=lambda item: item["id"], reverse=True)
        return reviews[offset:offset + limit]
    return reviews[:limit]


@router.get("/api/public/reviews/{review_id}", response_model=dict, tags=["public"])
async def get_public_review(
    review_id: int,
    category: str = Query(..., description="Category: movie, tv_show, anime, video_game, music, or book"),
    db: Session = Depends(get_db)
):
    """Get a specific public review by ID and category."""
    user_ids = _active_user_ids_query(db)

    def base_filter(model_cls):
        return and_(
            model_cls.id == review_id,
            model_cls.review.isnot(None),
            model_cls.review != "",
            model_cls.review_public == True,
            model_cls.user_id.in_(user_ids)
        )

    item = None
    if category == "movie":
        item = db.query(models.Movie).filter(base_filter(models.Movie)).first()
    elif category == "tv_show":
        item = db.query(models.TVShow).filter(base_filter(models.TVShow)).first()
    elif category == "anime":
        item = db.query(models.Anime).filter(base_filter(models.Anime)).first()
    elif category == "video_game":
        item = db.query(models.VideoGame).filter(base_filter(models.VideoGame)).first()
    elif category == "music":
        item = db.query(models.Music).filter(base_filter(models.Music)).first()
    elif category == "book":
        item = db.query(models.Book).filter(base_filter(models.Book)).first()
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
    elif category == "music":
        review_data.update({
            "artist": item.artist,
            "year": item.year,
            "cover_art_url": item.cover_art_url,
        })
    elif category == "book":
        review_data.update({
            "author": item.author,
            "year": item.year,
            "cover_art_url": item.cover_art_url,
        })

    return review_data
