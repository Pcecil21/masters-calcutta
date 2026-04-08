"""
Real-time auction state management for live Calcutta bidding.

Tracks every bid, maintains bankroll state, detects auction phases,
and provides spend-rate analysis so you always know where you stand
during the fast-moving live auction.

Usage:
    tracker = AuctionTracker()
    tracker.configure(total_pool=10000, my_bankroll=1200, ...)
    tracker.record_bid("scottie_scheffler", "other_bidder", 450)
    tracker.record_bid("sungjae_im", "me", 150)
    state = tracker.get_state()
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app.strategy.ev_calculator import EVCalculator


class AuctionTracker:
    """Tracks live auction state including bids, bankroll, and pacing.

    Attributes:
        total_pool: Total dollar pool for the auction.
        my_bankroll: Starting bankroll allocated to me.
        payout_structure: How the pool is distributed by finish position.
        num_bidders: Number of participants in the auction.
        bid_history: Ordered list of all recorded bids.
        my_bids: Bids where buyer == "me".
        remaining_bankroll: Current unspent bankroll.
        golfer_registry: Optional lookup of golfer data for EV calculations.
    """

    def __init__(self) -> None:
        self.total_pool: float = 0.0
        self.my_bankroll: float = 0.0
        self.payout_structure: dict = {}
        self.num_bidders: int = 12
        self.bid_history: list[dict] = []
        self.my_bids: list[dict] = []
        self.remaining_bankroll: float = 0.0
        self._configured: bool = False
        self._golfer_registry: dict[str, dict] = {}
        self._ev_calc: Optional[EVCalculator] = None

    def configure(
        self,
        total_pool: float,
        my_bankroll: float,
        payout_structure: Optional[dict] = None,
        num_bidders: int = 12,
        golfers: Optional[list[dict]] = None,
    ) -> None:
        """Set up the auction parameters before bidding begins.

        Args:
            total_pool: Total auction pool in dollars.
            my_bankroll: My available bankroll.
            payout_structure: Custom payout structure (or default).
            num_bidders: Number of bidders.
            golfers: Optional list of golfer dicts to register for EV lookups.
        """
        self.total_pool = total_pool
        self.my_bankroll = my_bankroll
        self.remaining_bankroll = my_bankroll
        self.payout_structure = payout_structure or {}
        self.num_bidders = num_bidders
        self.bid_history = []
        self.my_bids = []
        self._configured = True

        self._ev_calc = EVCalculator(payout_structure)

        if golfers:
            for g in golfers:
                gid = g.get("id", g.get("golfer_id", ""))
                if gid:
                    self._golfer_registry[gid] = g

    def _ensure_configured(self) -> None:
        if not self._configured:
            raise RuntimeError(
                "AuctionTracker not configured. Call configure() first."
            )

    def record_bid(
        self,
        golfer_id: str,
        buyer: str,
        price: float,
    ) -> dict:
        """Record a completed bid and update state.

        Args:
            golfer_id: Identifier for the golfer purchased.
            buyer: "me" if I purchased, otherwise the buyer's name.
            price: Final purchase price.

        Returns:
            Updated state summary dict.
        """
        self._ensure_configured()

        bid = {
            "golfer_id": golfer_id,
            "buyer": buyer,
            "price": price,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sequence": len(self.bid_history) + 1,
        }

        self.bid_history.append(bid)

        if buyer.lower() == "me":
            self.my_bids.append(bid)
            self.remaining_bankroll -= price
            self.remaining_bankroll = max(self.remaining_bankroll, 0.0)

        return self.get_state()

    def undo_last_bid(self) -> dict:
        """Undo the most recent bid.

        Returns:
            Updated state summary dict.
        """
        self._ensure_configured()

        if not self.bid_history:
            return self.get_state()

        last_bid = self.bid_history.pop()

        if last_bid["buyer"].lower() == "me":
            self.remaining_bankroll += last_bid["price"]
            # Remove from my_bids if it's there
            self.my_bids = [
                b for b in self.my_bids
                if not (
                    b["golfer_id"] == last_bid["golfer_id"]
                    and b["sequence"] == last_bid["sequence"]
                )
            ]

        return self.get_state()

    def get_state(self) -> dict:
        """Get full current auction state.

        Returns:
            Dictionary with bankroll, golfer counts, phase, and bid summary.
        """
        self._ensure_configured()

        sold_ids = [b["golfer_id"] for b in self.bid_history]
        remaining_ids = [
            gid for gid in self._golfer_registry
            if gid not in sold_ids
        ]

        my_golfer_ids = [b["golfer_id"] for b in self.my_bids]
        total_spent_by_me = sum(b["price"] for b in self.my_bids)
        total_auction_revenue = sum(b["price"] for b in self.bid_history)

        return {
            "total_pool": self.total_pool,
            "my_bankroll": self.my_bankroll,
            "remaining_bankroll": round(self.remaining_bankroll, 2),
            "total_spent": round(total_spent_by_me, 2),
            "golfers_sold": sold_ids,
            "golfers_remaining": remaining_ids,
            "num_sold": len(sold_ids),
            "num_remaining": len(remaining_ids),
            "my_golfers": my_golfer_ids,
            "num_my_golfers": len(my_golfer_ids),
            "total_auction_revenue": round(total_auction_revenue, 2),
            "current_phase": self.get_phase(),
            "num_bids": len(self.bid_history),
        }

    def get_remaining_ev(self) -> dict:
        """Calculate total expected value remaining in unsold golfers.

        Returns:
            Dict with total_ev, count, best_remaining, and avg_ev.
        """
        self._ensure_configured()

        sold_ids = set(b["golfer_id"] for b in self.bid_history)
        remaining = [
            g for gid, g in self._golfer_registry.items()
            if gid not in sold_ids
        ]

        if not remaining or self._ev_calc is None:
            return {
                "total_ev": 0.0,
                "count": 0,
                "best_remaining": None,
                "avg_ev": 0.0,
            }

        ev_list = []
        for g in remaining:
            probs = {
                "win_prob": g.get("model_win_prob", 0),
                "top5_prob": g.get("model_top5_prob", 0),
                "top10_prob": g.get("model_top10_prob", 0),
            }
            result = self._ev_calc.calculate_ev(probs, price=0, total_pool=self.total_pool)
            ev_list.append({
                "golfer_id": g.get("id", g.get("golfer_id", "unknown")),
                "name": g.get("name", "Unknown"),
                "expected_payout": result["expected_payout"],
            })

        ev_list.sort(key=lambda x: x["expected_payout"], reverse=True)
        total_ev = sum(e["expected_payout"] for e in ev_list)

        return {
            "total_ev": round(total_ev, 2),
            "count": len(ev_list),
            "best_remaining": ev_list[0] if ev_list else None,
            "avg_ev": round(total_ev / len(ev_list), 2) if ev_list else 0.0,
        }

    def get_spend_rate(self) -> dict:
        """Analyze whether I'm on pace to spend my bankroll.

        Returns:
            Dict with pace analysis: on_pace, recommendation, details.
        """
        self._ensure_configured()

        total_golfers = len(self._golfer_registry) or 87  # Masters field default
        sold_count = len(self.bid_history)
        remaining_count = max(total_golfers - sold_count, 1)

        spent = self.my_bankroll - self.remaining_bankroll
        spent_pct = spent / self.my_bankroll if self.my_bankroll > 0 else 0
        progress_pct = sold_count / total_golfers if total_golfers > 0 else 0

        # Ideal: spending should track auction progress
        # If 50% of golfers sold, ~50% of budget should be spent
        pace_ratio = spent_pct / max(progress_pct, 0.01)

        if pace_ratio > 1.3:
            pace = "AHEAD"
            recommendation = (
                f"Spending too fast ({spent_pct:.0%} spent with {progress_pct:.0%} "
                f"of auction complete). Slow down -- save budget for late-auction value."
            )
        elif pace_ratio < 0.7:
            pace = "BEHIND"
            recommendation = (
                f"Underspending ({spent_pct:.0%} spent with {progress_pct:.0%} "
                f"of auction complete). Need to be more aggressive or you'll waste "
                f"${self.remaining_bankroll:.0f} in unspent bankroll."
            )
        else:
            pace = "ON_PACE"
            recommendation = (
                f"Good pacing ({spent_pct:.0%} spent, {progress_pct:.0%} complete). "
                f"${self.remaining_bankroll:.0f} remaining for {remaining_count} golfers."
            )

        # Per-golfer budget for remaining auction
        per_golfer_budget = (
            self.remaining_bankroll / remaining_count
            if remaining_count > 0 else 0
        )

        return {
            "pace": pace,
            "pace_ratio": round(pace_ratio, 2),
            "spent": round(spent, 2),
            "spent_pct": round(spent_pct * 100, 1),
            "auction_progress_pct": round(progress_pct * 100, 1),
            "remaining_bankroll": round(self.remaining_bankroll, 2),
            "remaining_golfers": remaining_count,
            "avg_budget_per_remaining": round(per_golfer_budget, 2),
            "recommendation": recommendation,
        }

    def get_phase(self) -> str:
        """Detect the current auction phase based on bid count.

        Phases:
            - "early": top names being sold (first ~20 golfers)
            - "middle": mid-tier golfers (golfers 21-50)
            - "late": value/longshots (golfers 51-75)
            - "final": last picks (76+)

        Returns:
            Phase string.
        """
        sold = len(self.bid_history)
        total = len(self._golfer_registry) or 87

        progress = sold / total if total > 0 else 0

        if progress < 0.23:   # ~20 of 87
            return "early"
        elif progress < 0.57:  # ~50 of 87
            return "middle"
        elif progress < 0.86:  # ~75 of 87
            return "late"
        else:
            return "final"
