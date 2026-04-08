"""In-memory data store and seed data loader for the Masters Calcutta system.

The store is a module-level singleton dict that holds all auction state.
All routers read/write from this store via get_store().
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.schemas import (
    AuctionState,
    BidRecord,
    Golfer,
    Portfolio,
    PortfolioEntry,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State persistence file
# ---------------------------------------------------------------------------
_STATE_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "auction_state.json"

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


# ---------------------------------------------------------------------------
# State persistence (crash recovery)
# ---------------------------------------------------------------------------


def save_auction_state() -> None:
    """Persist current auction state to disk for crash recovery."""
    state: AuctionState = _STORE["auction_state"]
    portfolio: Portfolio = _STORE["portfolio"]
    bid_history: list[BidRecord] = _STORE["bid_history"]

    payload = {
        "config": _STORE["config"],
        "auction_state": state.model_dump() if state else None,
        "portfolio": portfolio.model_dump() if portfolio else None,
        "bid_history": [
            {
                **b.model_dump(),
                "timestamp": b.timestamp.isoformat(),
            }
            for b in bid_history
        ],
        "saved_at": datetime.now(tz=timezone.utc).isoformat(),
    }

    # Remove non-serializable config keys
    safe_config = {k: v for k, v in payload["config"].items() if k != "ev_calculator"}
    payload["config"] = safe_config

    # Atomic write: write to .tmp then rename
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp_file = _STATE_FILE.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    tmp_file.replace(_STATE_FILE)

    logger.info(
        "Auction state saved: %d bids, portfolio=%d entries",
        len(bid_history),
        len(portfolio.entries) if portfolio else 0,
    )


def load_auction_state() -> bool:
    """Attempt to restore auction state from disk. Returns True if restored."""
    if not _STATE_FILE.exists():
        logger.info("No saved auction state found at %s", _STATE_FILE)
        return False

    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)

        # Restore config (merge with defaults so ev_calculator key stays)
        saved_config = payload.get("config", {})
        for key in ("total_pool", "my_bankroll", "num_bidders", "payout_structure"):
            if key in saved_config:
                _STORE["config"][key] = saved_config[key]

        # Rebuild EVCalculator with restored payout structure
        from app.strategy.ev_calculator import EVCalculator
        _STORE["ev_calculator"] = EVCalculator(_STORE["config"]["payout_structure"])

        # Restore auction state
        state_data = payload.get("auction_state")
        if state_data:
            _STORE["auction_state"] = AuctionState(**state_data)

        # Restore portfolio
        portfolio_data = payload.get("portfolio")
        if portfolio_data:
            entries = [PortfolioEntry(**e) for e in portfolio_data.get("entries", [])]
            _STORE["portfolio"] = Portfolio(
                entries=entries,
                total_invested=portfolio_data.get("total_invested", 0.0),
                total_expected_value=portfolio_data.get("total_expected_value", 0.0),
                expected_roi=portfolio_data.get("expected_roi", 0.0),
                risk_score=portfolio_data.get("risk_score", 0.0),
            )

        # Restore bid history
        bid_history_data = payload.get("bid_history", [])
        bids = []
        for b in bid_history_data:
            ts = b.get("timestamp")
            if isinstance(ts, str):
                b["timestamp"] = datetime.fromisoformat(ts)
            bids.append(BidRecord(**b))
        _STORE["bid_history"] = bids

        # Invalidate alert cache
        _STORE["alert_cache"] = None

        logger.info(
            "Auction state restored: %d bids, portfolio=%d entries",
            len(bids),
            len(_STORE["portfolio"].entries) if _STORE["portfolio"] else 0,
        )
        return True

    except Exception:
        logger.exception("Failed to restore auction state from %s", _STATE_FILE)
        return False


def clear_saved_state() -> None:
    """Delete the saved auction state file."""
    if _STATE_FILE.exists():
        _STATE_FILE.unlink()
        logger.info("Saved auction state cleared: %s", _STATE_FILE)


def get_state_file_info() -> dict:
    """Return metadata about the saved state file, or None if it doesn't exist."""
    if not _STATE_FILE.exists():
        return {"has_saved_state": False, "bid_count": 0, "timestamp": None}

    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        return {
            "has_saved_state": True,
            "bid_count": len(payload.get("bid_history", [])),
            "timestamp": payload.get("saved_at"),
        }
    except Exception:
        return {"has_saved_state": False, "bid_count": 0, "timestamp": None}
