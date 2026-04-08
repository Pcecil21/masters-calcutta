"""
Alert engine for live Calcutta auction bidding.

Generates real-time alerts during the auction to flag value opportunities,
warn about budget pacing, and highlight portfolio gaps.  Alerts are
designed to be glanceable during the fast-paced live auction -- each
one has a priority level, a short punchy message, and actionable
bid recommendations.

Alert priority levels (5 = highest urgency):
    5 - MUST_BID:      EV multiple > 2.0x AND fills portfolio gap
    4 - STRONG_VALUE:   EV multiple > 1.5x
    3 - GOOD_VALUE:     EV multiple > 1.2x
    2 - FAIR_PRICE:     EV multiple 0.8-1.2x
    1 - OVERPRICED:     EV multiple < 0.8x
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.strategy.ev_calculator import EVCalculator
from app.strategy.kelly import KellyCalculator


@dataclass
class Alert:
    """A single auction alert with priority and actionable message."""

    golfer_id: str
    golfer_name: str
    alert_type: str
    priority: int
    message: str
    current_price: Optional[float] = None
    recommended_max: Optional[float] = None
    ev_multiple: Optional[float] = None
    expected_payout: Optional[float] = None

    def __str__(self) -> str:
        stars = "*" * self.priority
        return f"[{stars}] {self.alert_type}: {self.message}"


# Snappy message templates by alert type
_MESSAGES = {
    "MUST_BID": [
        "{name} at ${price:.0f} is ROBBERY - model says worth ${value:.0f}. BID NOW.",
        "DROP EVERYTHING. {name} at ${price:.0f} is a {multiple:.1f}x value play. This won't last.",
        "{name} for ${price:.0f}?! That's {multiple:.1f}x expected value. SMASH that bid.",
    ],
    "STRONG_VALUE": [
        "{name} at ${price:.0f} is solid value ({multiple:.1f}x). Worth bidding to ${max_bid:.0f}.",
        "Good price on {name} (${price:.0f}). Model says {multiple:.1f}x EV. Go for it.",
        "{name} still available at ${price:.0f} - that's {pct_below:.0f}% below fair value.",
    ],
    "GOOD_VALUE": [
        "{name} at ${price:.0f} is decent value ({multiple:.1f}x). Bid if budget allows.",
        "Moderate edge on {name} at ${price:.0f}. {multiple:.1f}x EV - not a steal but profitable.",
    ],
    "FAIR_PRICE": [
        "{name} at ${price:.0f} is fairly priced ({multiple:.1f}x). Only buy if filling a portfolio gap.",
        "{name} for ${price:.0f} is about right. No edge, no mistake.",
    ],
    "OVERPRICED": [
        "PASS on {name} at ${price:.0f}. Only worth ${value:.0f} ({multiple:.1f}x). Let someone else overpay.",
        "{name} at ${price:.0f} is {pct_above:.0f}% overpriced. Hard pass.",
        "The crowd is drunk on {name} at ${price:.0f}. Walk away. Model says ${value:.0f} max.",
    ],
}


class AlertEngine:
    """Generates real-time alerts for live auction bidding decisions.

    Evaluates each golfer against model valuations and portfolio context
    to produce prioritized, actionable alerts.
    """

    def __init__(
        self,
        payout_structure: Optional[dict] = None,
        total_pool: float = 10000.0,
    ) -> None:
        """Initialize the alert engine.

        Args:
            payout_structure: Custom payout structure.
            total_pool: Total auction pool in dollars.
        """
        self.total_pool = total_pool
        self.ev_calc = EVCalculator(payout_structure)
        self.kelly = KellyCalculator()

    def evaluate(
        self,
        golfer: dict,
        current_price: float,
        auction_state: dict,
        portfolio: list[dict],
    ) -> Optional[Alert]:
        """Evaluate a single golfer at the current bidding price.

        Args:
            golfer: Golfer data dict with model probabilities.
            current_price: Current bid price for this golfer.
            auction_state: Current auction state from AuctionTracker.
            portfolio: List of already-purchased positions.

        Returns:
            Alert object if one should be raised, or None.
        """
        golfer_id = golfer.get("id", golfer.get("golfer_id", "unknown"))
        name = golfer.get("name", "Unknown")

        probs = {
            "win_prob": golfer.get("model_win_prob", golfer.get("win_prob", 0)),
            "top5_prob": golfer.get("model_top5_prob", golfer.get("top5_prob", 0)),
            "top10_prob": golfer.get("model_top10_prob", golfer.get("top10_prob", 0)),
        }

        ev_result = self.ev_calc.calculate_ev(probs, current_price, self.total_pool)
        ev_multiple = ev_result["ev_multiple"]
        expected_payout = ev_result["expected_payout"]

        # Kelly-based max bid
        win_prob = probs["win_prob"]
        remaining_bankroll = auction_state.get("remaining_bankroll", 0)
        max_bid = self.kelly.max_bid(
            win_prob=max(probs.get("top10_prob", win_prob), win_prob),
            expected_payout=expected_payout,
            bankroll=remaining_bankroll,
        )

        # Check portfolio gaps
        has_elite = any(p.get("model_win_prob", 0) > 0.04 for p in portfolio)
        fills_gap = False
        if win_prob > 0.04 and not has_elite:
            fills_gap = True

        # Determine alert level
        if ev_multiple > 2.0 and fills_gap:
            alert_type = "MUST_BID"
            priority = 5
        elif ev_multiple > 2.0:
            alert_type = "MUST_BID"
            priority = 5
        elif ev_multiple > 1.5:
            alert_type = "STRONG_VALUE"
            priority = 4
        elif ev_multiple > 1.2:
            alert_type = "GOOD_VALUE"
            priority = 3
        elif ev_multiple >= 0.8:
            alert_type = "FAIR_PRICE"
            priority = 2
        else:
            alert_type = "OVERPRICED"
            priority = 1

        # Boost priority if fills portfolio gap
        if fills_gap and priority < 5:
            priority = min(priority + 1, 5)

        # Generate message
        message = self._generate_message(
            alert_type=alert_type,
            name=name,
            price=current_price,
            value=expected_payout,
            multiple=ev_multiple,
            max_bid=max_bid,
        )

        return Alert(
            golfer_id=golfer_id,
            golfer_name=name,
            alert_type=alert_type,
            priority=priority,
            message=message,
            current_price=current_price,
            recommended_max=round(max_bid, 2),
            ev_multiple=round(ev_multiple, 3),
            expected_payout=round(expected_payout, 2),
        )

    def get_active_alerts(
        self,
        remaining_golfers: list[dict],
        auction_state: dict,
        portfolio: list[dict],
    ) -> list[Alert]:
        """Scan all remaining golfers and generate alerts.

        Uses estimated market prices (if available) or a default
        price estimate for golfers not yet bid on.

        Args:
            remaining_golfers: Golfers still available.
            auction_state: Current auction state.
            portfolio: Currently owned positions.

        Returns:
            List of Alert objects sorted by priority (highest first).
        """
        alerts = []

        for g in remaining_golfers:
            # Use estimated market price or a rough estimate
            est_price = g.get(
                "estimated_market_price",
                g.get("consensus_win_prob", 0.01) * self.total_pool * 3,
            )
            est_price = max(est_price, 1.0)  # floor

            alert = self.evaluate(g, est_price, auction_state, portfolio)
            if alert is not None:
                alerts.append(alert)

        # Sort by priority descending, then by EV multiple descending
        alerts.sort(
            key=lambda a: (a.priority, a.ev_multiple or 0),
            reverse=True,
        )

        return alerts

    def budget_warning(self, auction_state: dict) -> Optional[Alert]:
        """Generate a budget pacing alert.

        Warns if spending too fast (will run out before auction ends)
        or too slow (will waste unspent bankroll).

        Args:
            auction_state: Current auction state from AuctionTracker.

        Returns:
            Budget Alert or None if pacing is fine.
        """
        remaining = auction_state.get("remaining_bankroll", 0)
        total = auction_state.get("my_bankroll", auction_state.get("total_pool", 0))
        num_sold = auction_state.get("num_sold", 0)
        num_remaining = auction_state.get("num_remaining", 0)
        total_golfers = num_sold + num_remaining
        phase = auction_state.get("current_phase", "middle")

        if total <= 0 or total_golfers <= 0:
            return None

        spent_pct = 1 - (remaining / total)
        progress_pct = num_sold / total_golfers

        # Too fast
        if progress_pct > 0.1 and spent_pct > progress_pct * 1.5:
            return Alert(
                golfer_id="__budget__",
                golfer_name="Budget",
                alert_type="BUDGET_WARNING",
                priority=4,
                message=(
                    f"SLOW DOWN! You've spent {spent_pct:.0%} of your bankroll "
                    f"but only {progress_pct:.0%} of the auction is complete. "
                    f"${remaining:.0f} left for {num_remaining} golfers."
                ),
            )

        # Too slow
        if phase in ("late", "final") and remaining > total * 0.4:
            return Alert(
                golfer_id="__budget__",
                golfer_name="Budget",
                alert_type="BUDGET_WARNING",
                priority=5,
                message=(
                    f"SPEND YOUR MONEY! ${remaining:.0f} left with only "
                    f"{num_remaining} golfers remaining. Unspent bankroll is "
                    f"WASTED. Buy the best available EV now."
                ),
            )

        # Moderate underspending
        if progress_pct > 0.5 and spent_pct < progress_pct * 0.5:
            return Alert(
                golfer_id="__budget__",
                golfer_name="Budget",
                alert_type="BUDGET_WARNING",
                priority=3,
                message=(
                    f"Getting behind on spending. {spent_pct:.0%} spent at "
                    f"{progress_pct:.0%} auction progress. Consider being "
                    f"more aggressive on the next 2-3 positive-EV golfers."
                ),
            )

        return None

    @staticmethod
    def _generate_message(
        alert_type: str,
        name: str,
        price: float,
        value: float,
        multiple: float,
        max_bid: float,
    ) -> str:
        """Generate a snappy alert message.

        Args:
            alert_type: Alert classification.
            name: Golfer name.
            price: Current price.
            value: Expected payout (fair value).
            multiple: EV multiple.
            max_bid: Kelly-recommended maximum bid.

        Returns:
            Human-readable alert message.
        """
        templates = _MESSAGES.get(alert_type, ["{name} at ${price:.0f} ({multiple:.1f}x EV)."])

        pct_below = max((value - price) / value * 100, 0) if value > 0 else 0
        pct_above = max((price - value) / value * 100, 0) if value > 0 else 0

        # Pick a template (rotate based on name hash for variety)
        idx = hash(name) % len(templates)
        template = templates[idx]

        return template.format(
            name=name,
            price=price,
            value=value,
            multiple=multiple,
            max_bid=max_bid,
            pct_below=pct_below,
            pct_above=pct_above,
        )
