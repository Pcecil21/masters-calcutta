"""Masters Calcutta Auction API -- FastAPI application entry point.

Start with:
    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.data.loaders import load_seed_data
from app.routers import auction, backtest, golfers, portfolio, strategy


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


@app.get("/api/health")
async def health_check() -> dict:
    """Basic health check endpoint."""
    return {"status": "ok", "service": "masters-calcutta-api"}
