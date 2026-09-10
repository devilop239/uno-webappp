# -*- coding: utf-8 -*-
"""FastAPI endpoints for MongoDB leaderboard and player statistics."""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional

from services import leaderboard_service, stats_service, user_service

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=Dict[str, Any])
async def get_leaderboard(
    category: str = Query("points", description="Sorting field: points | wins | games"),
    period: str = Query("all", description="Time filter: all | month | week | today"),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Get aggregated global player leaderboard directly from MongoDB.
    Categories: points, wins, games
    Periods: all, month, week, today
    """
    try:
        top_players = await leaderboard_service.get_global_leaderboard(
            category=category,
            period=period,
            limit=limit,
        )
        return {
            "category": category,
            "period": period,
            "count": len(top_players),
            "leaderboard": top_players,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed querying leaderboard: {str(e)}")


@router.get("/player/{user_id}", response_model=Dict[str, Any])
async def get_player_stats(user_id: int):
    """
    Get detailed player profile statistics (wins, losses, cards played, points).
    """
    try:
        stats = await stats_service.get_user_stats(user_id)
        if not stats:
            raise HTTPException(status_code=404, detail=f"Player stats for user_id={user_id} not found")
        return stats
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed querying user stats: {str(e)}")
