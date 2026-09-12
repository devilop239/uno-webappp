# -*- coding: utf-8 -*-
"""FastAPI endpoints for MongoDB leaderboard and player statistics."""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any

from services import leaderboard_service, stats_service

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])


@router.get("", response_model=Dict[str, Any])
async def get_leaderboard(
    category: str = Query("points", description="Public board category"),
    period: str = Query("all", description="Time filter: all | month | week"),
    limit: int = Query(20, ge=1, le=50),
):
    """Return a bounded public points leaderboard for the selected period."""
    if category != "points":
        raise HTTPException(status_code=400, detail="Only points leaderboard is available")
    if period not in {"all", "week", "month"}:
        raise HTTPException(status_code=400, detail="period must be all, week, or month")
    try:
        top_players = leaderboard_service.get_global_leaderboard(period=period, limit=limit)
        return {"category": "points", "period": period, "count": len(top_players), "leaderboard": top_players}
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
