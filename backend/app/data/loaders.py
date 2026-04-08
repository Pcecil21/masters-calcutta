"""In-memory data store and seed data loader for the Masters Calcutta system.

The store is a module-level singleton dict that holds all auction state.
All routers read/write from this store via get_store().
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from app.schemas import (
    AuctionState,
    BidRecord,
    Golfer,
    Portfolio,
)

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
        "payout_structure": {
            "1st": 0.50,
            "2nd": 0.20,
            "3rd": 0.10,
            "top5": 0.05,
            "top10": 0.03,
            "made_cut": 0.01,
        },
    },
}


def get_store() -> dict[str, Any]:
    """Return the singleton in-memory store."""
    return _STORE


# ---------------------------------------------------------------------------
# Seed data loading
# ---------------------------------------------------------------------------

_SEED_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "seed"


def _implied_prob_from_odds(decimal_odds: float) -> float:
    """Convert decimal betting odds to implied probability."""
    if decimal_odds <= 0:
        return 0.0
    return 1.0 / decimal_odds


def _generate_default_field() -> list[dict]:
    """Generate a realistic 2026 Masters field with model probabilities.

    This is used when the seed JSON file does not exist yet.  The numbers
    are calibrated to reflect realistic pre-tournament expectations.
    """
    players = [
        # (name, world_rank, decimal_odds, appearances, wins, top10s, form, augusta)
        ("Scottie Scheffler", 1, 5.0, 8, 2, 5, 95, 95),
        ("Xander Schauffele", 2, 10.0, 8, 0, 4, 92, 80),
        ("Rory McIlroy", 3, 12.0, 17, 0, 8, 88, 75),
        ("Jon Rahm", 4, 14.0, 8, 0, 4, 78, 72),
        ("Collin Morikawa", 5, 16.0, 5, 0, 2, 90, 65),
        ("Ludvig Aberg", 6, 18.0, 2, 0, 1, 88, 70),
        ("Bryson DeChambeau", 7, 20.0, 7, 0, 2, 85, 55),
        ("Hideki Matsuyama", 8, 22.0, 12, 1, 5, 82, 82),
        ("Patrick Cantlay", 9, 28.0, 8, 0, 3, 80, 68),
        ("Tommy Fleetwood", 10, 30.0, 7, 0, 3, 78, 65),
        ("Shane Lowry", 11, 35.0, 7, 0, 2, 77, 60),
        ("Viktor Hovland", 12, 35.0, 5, 0, 2, 72, 58),
        ("Brooks Koepka", 13, 40.0, 9, 0, 3, 70, 62),
        ("Justin Thomas", 14, 40.0, 9, 0, 4, 68, 66),
        ("Cameron Smith", 15, 45.0, 7, 0, 3, 65, 60),
        ("Tony Finau", 16, 50.0, 8, 0, 2, 72, 55),
        ("Sahith Theegala", 17, 50.0, 3, 0, 0, 80, 40),
        ("Wyndham Clark", 18, 55.0, 3, 0, 0, 75, 38),
        ("Max Homa", 19, 55.0, 4, 0, 0, 70, 42),
        ("Russell Henley", 20, 60.0, 6, 0, 1, 68, 48),
        ("Sungjae Im", 21, 60.0, 6, 0, 2, 72, 52),
        ("Robert MacIntyre", 22, 65.0, 3, 0, 0, 74, 35),
        ("Matt Fitzpatrick", 23, 65.0, 7, 0, 2, 66, 55),
        ("Cameron Young", 24, 70.0, 3, 0, 0, 65, 38),
        ("Keegan Bradley", 25, 70.0, 10, 0, 1, 68, 50),
        ("Jordan Spieth", 26, 40.0, 11, 1, 7, 55, 88),
        ("Dustin Johnson", 27, 60.0, 13, 1, 5, 50, 78),
        ("Adam Scott", 28, 80.0, 22, 1, 5, 48, 75),
        ("Tiger Woods", 29, 100.0, 24, 5, 14, 20, 98),
        ("Phil Mickelson", 30, 150.0, 30, 3, 11, 15, 80),
        ("Corey Conners", 31, 80.0, 6, 0, 1, 62, 48),
        ("Denny McCarthy", 32, 90.0, 3, 0, 0, 64, 30),
        ("Sam Burns", 33, 70.0, 4, 0, 0, 66, 40),
        ("Tom Kim", 34, 60.0, 3, 0, 0, 74, 38),
        ("Joaquin Niemann", 35, 80.0, 4, 0, 0, 60, 35),
        ("Sepp Straka", 36, 90.0, 4, 0, 0, 58, 32),
        ("Will Zalatoris", 37, 50.0, 4, 0, 2, 60, 65),
        ("Min Woo Lee", 38, 100.0, 2, 0, 0, 62, 28),
        ("Jason Day", 39, 80.0, 13, 0, 3, 55, 62),
        ("Si Woo Kim", 40, 120.0, 7, 0, 1, 50, 40),
        ("Chris Kirk", 41, 100.0, 7, 0, 0, 55, 38),
        ("Taylor Moore", 42, 150.0, 2, 0, 0, 52, 22),
        ("Brian Harman", 43, 80.0, 6, 0, 1, 58, 48),
        ("Nick Dunlap", 44, 120.0, 1, 0, 0, 60, 20),
        ("Akshay Bhatia", 45, 100.0, 2, 0, 0, 65, 25),
        ("Davis Thompson", 46, 120.0, 2, 0, 0, 58, 22),
        ("Aaron Rai", 47, 150.0, 1, 0, 0, 55, 18),
        ("Matthieu Pavon", 48, 100.0, 2, 0, 0, 56, 28),
        ("Stephan Jaeger", 49, 200.0, 1, 0, 0, 52, 15),
        ("Luke Clanton", 50, 200.0, 1, 0, 0, 50, 15),
        ("Santiago De La Fuente", 51, 250.0, 1, 0, 0, 45, 10),
        ("Hiroshi Tai", 52, 300.0, 1, 0, 0, 42, 10),
        ("Jasper Stubbs", 53, 300.0, 1, 0, 0, 40, 10),
        ("Noah Kent", 54, 500.0, 1, 0, 0, 35, 8),
        ("The Field", 55, 40.0, 0, 0, 0, 50, 50),
    ]

    field = []
    for i, (name, rank, odds, apps, wins, t10s, form, augusta) in enumerate(players):
        consensus_wp = _implied_prob_from_odds(odds)

        # Model probabilities - slightly adjusted from consensus to create
        # interesting anti-consensus opportunities
        adjustments = {
            "Jordan Spieth": 1.6,
            "Tiger Woods": 0.4,
            "Phil Mickelson": 0.3,
            "Dustin Johnson": 0.7,
            "Will Zalatoris": 1.4,
            "Sahith Theegala": 1.3,
            "Tom Kim": 1.2,
            "Hideki Matsuyama": 1.15,
            "Ludvig Aberg": 1.1,
            "Brooks Koepka": 0.8,
            "Cameron Smith": 0.85,
            "Rory McIlroy": 0.95,
            "Scottie Scheffler": 1.05,
        }
        model_factor = adjustments.get(name, 1.0)
        model_wp = min(consensus_wp * model_factor, 0.35)

        # Derive other probabilities from win prob using realistic ratios
        model_t5 = min(model_wp * 4.5, 0.80)
        model_t10 = min(model_wp * 7.0, 0.90)
        model_t20 = min(model_wp * 10.0, 0.95)
        model_cut = min(model_wp * 15.0 + 0.3, 0.99) if model_wp > 0.005 else 0.35

        # EV score: weighted combination of finish probabilities
        ev = (
            model_wp * 50.0
            + model_t5 * 20.0
            + model_t10 * 10.0
            + model_t20 * 5.0
            + model_cut * 1.0
        )

        anti_consensus = model_wp - consensus_wp

        field.append(
            {
                "id": f"golfer_{i + 1:03d}",
                "name": name,
                "world_ranking": rank,
                "odds_to_win": odds,
                "masters_appearances": apps,
                "masters_wins": wins,
                "masters_top10s": t10s,
                "recent_form_score": form,
                "augusta_history_score": augusta,
                "current_season_stats": {
                    "scoring_avg": round(69.5 + (rank * 0.04), 2),
                    "gir_pct": round(max(55, 75 - rank * 0.3), 1),
                    "sg_total": round(max(-0.5, 3.0 - rank * 0.06), 2),
                    "sg_approach": round(max(-0.3, 1.5 - rank * 0.03), 2),
                    "sg_putting": round(max(-0.5, 1.0 - rank * 0.02), 2),
                },
                "model_win_prob": round(model_wp, 5),
                "model_top5_prob": round(model_t5, 4),
                "model_top10_prob": round(model_t10, 4),
                "model_top20_prob": round(model_t20, 4),
                "model_cut_prob": round(model_cut, 4),
                "consensus_win_prob": round(consensus_wp, 5),
                "ev_score": round(ev, 3),
                "anti_consensus_score": round(anti_consensus, 5),
            }
        )
    return field


def load_seed_data() -> None:
    """Load golfer data into the in-memory store.

    Tries to read from data/seed/masters_2026_field.json first.
    Falls back to the built-in default field generator.
    """
    seed_file = _SEED_DIR / "masters_2026_field.json"

    if seed_file.exists():
        with open(seed_file, "r", encoding="utf-8") as f:
            raw = json.load(f)
    else:
        raw = _generate_default_field()
        # Write it out so other processes can use the same data
        seed_file.parent.mkdir(parents=True, exist_ok=True)
        with open(seed_file, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)

    golfers: dict[str, Golfer] = {}
    for entry in raw:
        g = Golfer(**entry)
        golfers[g.id] = g

    _STORE["golfers"] = golfers
    _STORE["bid_history"] = []
    _STORE["portfolio"] = Portfolio()
    _STORE["auction_state"] = AuctionState(
        golfers_remaining=list(golfers.keys()),
        golfers_sold=[],
    )


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
