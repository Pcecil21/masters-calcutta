"""Masters Calcutta Auction API -- FastAPI application entry point.

Start with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data.loaders import (
    get_state_file_info,
    get_store,
    load_auction_state,
    load_seed_data,
)
from app.routers import auction, backtest, golfers, odds, portfolio, scorecard, strategy


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load seed data into the in-memory store on startup."""
    load_seed_data()
    yield


app = FastAPI(
    title="Masters Calcutta Auction API",
    description=(
        "Real-time auction management, strategy recommendations, and portfolio "
        "analysis for Masters Golf Calcutta auctions. Powered by a probabilistic "
        "model that identifies anti-consensus value."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS -- allow the React frontend at localhost:3000
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers -- all under /api prefix
# ---------------------------------------------------------------------------
app.include_router(golfers.router, prefix="/api")
app.include_router(auction.router, prefix="/api")
app.include_router(strategy.router, prefix="/api")
app.include_router(portfolio.router, prefix="/api")
app.include_router(backtest.router, prefix="/api")
app.include_router(odds.router, prefix="/api")
app.include_router(scorecard.router, prefix="/api")


@app.get("/api/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "masters-calcutta-api"}


@app.get("/api/auction/has-saved-state")
async def has_saved_state() -> dict:
    """Check whether a saved auction state file exists on disk."""
    return get_state_file_info()


@app.post("/api/auction/restore")
async def restore_auction_state() -> dict:
    """Restore auction state from disk after a server restart or crash."""
    restored = load_auction_state()
    if not restored:
        return {"restored": False, "message": "No saved state found to restore."}
    store = get_store()
    return {
        "restored": True,
        "auction_state": store["auction_state"].model_dump(),
        "bid_count": len(store["bid_history"]),
        "portfolio_count": len(store["portfolio"].entries) if store["portfolio"] else 0,
    }


@app.post("/api/recalculate")
async def recalculate() -> dict:
    """Clear MC cache and reload seed data."""
    cache_file = Path(__file__).resolve().parent.parent / "data" / "seed" / "mc_cache.json"
    if cache_file.exists():
        cache_file.unlink()
    load_seed_data()
    store = get_store()
    return {"status": "recalculated", "golfer_count": len(store["golfers"])}
