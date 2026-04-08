"""In-memory data store and seed data loader for the Masters Calcutta system.

The store is a module-level singleton dict that holds all auction state.
All routers read/write from this store via get_store().
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import (
    AuctionState,
    BidRecord,
    Golfer,
    Portfolio,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level singleton store
# ---------------------------------------------------------------------------

_STORE: dict[str, Any] = {
    "golfers": {},          # dict[str, Golfer]
    "auction_state": None,  # AuctionState
    "portfolio": None,      # Portfolio
    "bid_history": [],      # list[BidRecord]
    "config": {
        "total_pool": 0.0,
        "my_bankroll": 0.0,
        "num_bidders": 12,
        "payout_structure": {
            "1st": 0.50,
            "2nd": 0.20,
            "3rd": 0.12,
            "4th": 0.05,
            "5th": 0.05,
            "6th": 0.016,
            "7th": 0.016,
            "8th": 0.016,
            "9th": 0.016,
            "10th": 0.016,
        },
    },
    "ev_calculator": None,   # EVCalculator (initialized on startup)
    "alert_cache": None,     # cached alerts (invalidated on bid/undo/configure)
}


def get_store() -> dict[str, Any]:
    """Return the singleton in-memory store."""
    return _STORE


# ---------------------------------------------------------------------------
# Seed data loading
# ---------------------------------------------------------------------------

_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seed"


def load_seed_data() -> None:
    """Load golfer data into the in-memory store.

    Reads from data/seed/masters_2026_field.json -- the single canonical source.
    Raises FileNotFoundError if the seed file is missing.
    """
    from app.strategy.ev_calculator import EVCalculator

    seed_file = _SEED_DIR / "masters_2026_field.json"

    if not seed_file.exists():
        raise FileNotFoundError(
            f"Seed data file not found: {seed_file}. "
            "Please ensure data/seed/masters_2026_field.json exists. "
            "This is the canonical golfer data source."
        )

    with open(seed_file, "r", encoding="utf-8") as f:
        raw = json.load(f)

    golfers: dict[str, Golfer] = {}
    for entry in raw:
        try:
            g = Golfer(**entry)
        except ValidationError as exc:
            logger.error(
                "Validation failed for golfer entry %s: %s",
                entry.get("id", entry.get("name", "UNKNOWN")),
                exc,
            )
            continue
        golfers[g.id] = g

    _STORE["golfers"] = golfers
    _STORE["bid_history"] = []
    _STORE["portfolio"] = Portfolio()
    _STORE["auction_state"] = AuctionState(
        golfers_remaining=list(golfers.keys()),
        golfers_sold=[],
    )
    _STORE["ev_calculator"] = EVCalculator(_STORE["config"]["payout_structure"])
    _STORE["alert_cache"] = None


def reset_auction() -> None:
    """Reset auction state while preserving golfer data."""
    golfers = _STORE["golfers"]
    _STORE["bid_history"] = []
    _STORE["portfolio"] = Portfolio()
    _STORE["auction_state"] = AuctionState(
        total_pool=_STORE["config"].get("total_pool", 0.0),
        my_bankroll=_STORE["config"].get("my_bankroll", 0.0),
        remaining_bankroll=_STORE["config"].get("my_bankroll", 0.0),
        golfers_remaining=list(golfers.keys()),
        golfers_sold=[],
        current_phase="pre_auction",
    )
    _STORE["alert_cache"] = None
