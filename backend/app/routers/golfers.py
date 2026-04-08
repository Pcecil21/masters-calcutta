"""Golfer data endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data.loaders import get_store
from app.schemas import Golfer

router = APIRouter(prefix="/golfers", tags=["golfers"])


@router.get("", response_model=list[Golfer])
async def list_golfers() -> list[Golfer]:
    """Return all golfers with model probabilities."""
    store = get_store()
    return sorted(store["golfers"].values(), key=lambda g: g.world_ranking)


@router.get("/rankings", response_model=list[Golfer])
async def golfer_rankings() -> list[Golfer]:
    """Return golfers sorted by model win probability (descending)."""
    store = get_store()
    return sorted(
        store["golfers"].values(),
        key=lambda g: g.model_win_prob,
        reverse=True,
    )


@router.get("/value", response_model=list[Golfer])
async def golfer_value() -> list[Golfer]:
    """Return golfers sorted by anti-consensus score (model prob minus consensus).

    Positive values indicate our model sees more upside than the market.
    """
    store = get_store()
    return sorted(
        store["golfers"].values(),
        key=lambda g: g.anti_consensus_score,
        reverse=True,
    )


@router.get("/{golfer_id}", response_model=Golfer)
async def get_golfer(golfer_id: str) -> Golfer:
    """Get detailed stats for a single golfer."""
    store = get_store()
    golfer = store["golfers"].get(golfer_id)
    if golfer is None:
        raise HTTPException(status_code=404, detail=f"Golfer {golfer_id} not found")
    return golfer
