"""
Expected Value calculation engine for Calcutta auction bidding.

Computes the dollar-weighted expected value of purchasing a golfer at
a given price, accounting for the full payout structure and the golfer's
probability of finishing in each payout tier.

The EV is the single most important number in a Calcutta: it tells you
what a golfer is *worth* in dollar terms.  Any price below EV is a
value purchase; any price above is overpaying.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.models.probability import placement_probabilities


# Default Masters Calcutta payout structure (percentage of total pool)
# Based on 2026 Olympic Hills Calcutta rules
DEFAULT_PAYOUT_STRUCTURE: dict[str, float] = {
    "1st": 0.40,
    "2nd": 0.18,
    "3rd": 0.12,
    "4th": 0.09,
    "5th": 0.06,
    "6th": 0.05,
    "7th": 0.03,
    "8th": 0.03,
    "9th": 0.02,
    "10th": 0.01,
}


# Default bonus structure: fixed-dollar awards outside the pool %
DEFAULT_BONUSES: dict[str, float] = {
    "round_leader_r1": 1000.0,
    "round_leader_r2": 1000.0,
    "round_leader_r3": 1000.0,
    "low_18": 1000.0,
    "low_27": 1000.0,
    "low_36": 1000.0,
    "last_place_sunday": 200.0,
}


class EVCalculator:
    """Expected value engine for Calcutta golfer pricing.

    Initialize with a payout structure and use it to evaluate any golfer's
    expected dollar return at a given price point.

    Attributes:
        payout_structure: Mapping of finish position -> pool percentage.
        payout_tiers: Ordered list of (position_label, pct) tuples.
        bonuses: Fixed-dollar bonuses (round leaders, low rounds, last place).
    """

    def __init__(self, payout_structure: Optional[dict[str, float]] = None, bonuses: Optional[dict[str, float]] = None) -> None:
        """Initialize the EV calculator.

        Args:
            payout_structure: Custom payout structure mapping position labels
                to pool percentages.  Defaults to the 2026 Olympic Hills
                Calcutta structure (40/18/12/9/6/5/3/3/2/1).
        """
        self.payout_structure = payout_structure or DEFAULT_PAYOUT_STRUCTURE.copy()
        self.bonuses = bonuses or DEFAULT_BONUSES.copy()
        self.payout_tiers = sorted(
            self.payout_structure.items(),
            key=lambda x: self._position_sort_key(x[0]),
        )

    @staticmethod
    def _position_sort_key(pos: str) -> int:
        """Extract numeric sort key from position label."""
        digits = "".join(c for c in pos if c.isdigit())
        return int(digits) if digits else 99

    def _golfer_finish_probs(self, golfer_probs: dict) -> dict[str, float]:
        """Map golfer probability data to per-position finish probabilities.

        Takes a golfer_probs dict with keys like:
            - win_prob (or win): probability of winning
            - top5_prob (or top5): probability of top 5
            - top10_prob (or top10): probability of top 10

        Returns exactly-finish probabilities for each payout tier:
            - P(1st) = win_prob
            - P(2nd) = top5 distribution minus win
            - P(3rd) = top5 distribution minus win and 2nd
            - P(4th-5th) = remaining top5 minus above
            - P(6th-10th) = (top10 - top5) / 5

        Args:
            golfer_probs: Probability dictionary for a single golfer.

        Returns:
            Dict mapping position label -> exact finish probability.
        """
        # Extract probabilities with flexible key naming
        win = golfer_probs.get("win_prob", golfer_probs.get("win", 0.0))
        top5 = golfer_probs.get("top5_prob", golfer_probs.get("top5", 0.0))
        top10 = golfer_probs.get("top10_prob", golfer_probs.get("top10", 0.0))

        # If we only have win_prob, generate placement probs
        if top5 == 0 and top10 == 0 and win > 0:
            placements = placement_probabilities(win)
            top5 = placements["top5"]
            top10 = placements["top10"]

        # Ensure monotonicity
        top5 = max(top5, win)
        top10 = max(top10, top5)

        # Distribute top-5 probability across positions 1-5
        # P(exactly 1st) = win
        # P(exactly 2nd-5th) = (top5 - win) / 4  (uniform within tier)
        p_2nd_to_5th_each = max(top5 - win, 0) / 4.0

        # P(exactly 6th-10th each) = (top10 - top5) / 5
        p_6th_to_10th_each = max(top10 - top5, 0) / 5.0

        finish_probs = {}
        for pos_label, _ in self.payout_tiers:
            key = self._position_sort_key(pos_label)
            if key == 1:
                finish_probs[pos_label] = win
            elif 2 <= key <= 5:
                finish_probs[pos_label] = p_2nd_to_5th_each
            elif 6 <= key <= 10:
                finish_probs[pos_label] = p_6th_to_10th_each
            else:
                finish_probs[pos_label] = 0.0

        return finish_probs

    def _bonus_ev(self, golfer_probs: dict, field_size: int = 55) -> dict:
        """Estimate expected bonus value for a golfer.

        Round leader / low-round bonuses correlate with skill.  We approximate
        the probability of leading after any single round as proportional to
        win probability, scaled so the field sums to 1.

        Args:
            golfer_probs: Probability dict with win_prob, top5_prob, etc.
            field_size: Number of golfers in the field.

        Returns:
            Dict with bonus_ev (total $), and per-bonus breakdown.
        """
        win = golfer_probs.get("win_prob", golfer_probs.get("win", 0.0))
        top10 = golfer_probs.get("top10_prob", golfer_probs.get("top10", 0.0))
        cut_prob = golfer_probs.get("cut_prob", golfer_probs.get("make_cut", 0.7))

        # Round leader probability: roughly proportional to win_prob but
        # more spread out (good players lead rounds more often than they win).
        # Approximate: p_lead_round ~ sqrt(win_prob) normalized.
        # For a single golfer we use: p_lead ≈ win_prob * 3 (since leading a
        # round is ~3x more likely than winning outright), capped at 0.30.
        p_round_leader = min(win * 3.0, 0.30)

        # Low 18/27/36: similar to round leader, slightly higher for
        # consistent players (correlated with top10 prob)
        p_low_round = min((win * 2.0 + top10 * 0.5) / 2.0, 0.25)

        # Last place Sunday: inversely correlated with skill; mostly
        # golfers who barely make the cut.  Approximate as small fixed prob
        # scaled inversely with cut_prob.
        p_last_sunday = max(0.005, (1.0 - cut_prob) * 0.02) if cut_prob < 0.95 else 0.005

        breakdown = {}
        total_bonus_ev = 0.0

        for key, amount in self.bonuses.items():
            if "round_leader" in key:
                p = p_round_leader
            elif "low_" in key:
                p = p_low_round
            elif "last_place" in key:
                p = p_last_sunday
            else:
                p = 0.0
            ev = p * amount
            breakdown[key] = {"prob": round(p, 6), "amount": amount, "ev": round(ev, 2)}
            total_bonus_ev += ev

        return {"bonus_ev": round(total_bonus_ev, 2), "breakdown": breakdown}

    def calculate_ev(
        self,
        golfer_probs: dict,
        price: float,
        total_pool: float,
    ) -> dict:
        """Calculate expected value for purchasing a golfer at a given price.

        Args:
            golfer_probs: Golfer probability data (win_prob, top5_prob, top10_prob).
            price: Purchase price in dollars.
            total_pool: Total auction pool size in dollars.

        Returns:
            Dictionary with:
                - expected_payout: probability-weighted dollar payout
                - ev: expected_payout - price (positive = profitable)
                - ev_multiple: expected_payout / price
                - roi: (expected_payout - price) / price as percentage
                - payout_breakdown: per-position expected payouts
        """
        finish_probs = self._golfer_finish_probs(golfer_probs)

        payout_breakdown = {}
        total_expected_payout = 0.0

        for pos_label, pool_pct in self.payout_tiers:
            dollar_payout = total_pool * pool_pct
            prob = finish_probs.get(pos_label, 0.0)
            expected = prob * dollar_payout
            total_expected_payout += expected
            payout_breakdown[pos_label] = {
                "finish_prob": round(prob, 6),
                "pool_payout": round(dollar_payout, 2),
                "expected_dollars": round(expected, 2),
            }

        # Add bonus EV (round leaders, low rounds, last place Sunday)
        bonus_result = self._bonus_ev(golfer_probs)
        bonus_ev = bonus_result["bonus_ev"]
        total_expected_payout += bonus_ev

        ev = total_expected_payout - price
        ev_multiple = total_expected_payout / price if price > 0 else float("inf")
        roi = (ev / price * 100) if price > 0 else float("inf")

        return {
            "expected_payout": round(total_expected_payout, 2),
            "ev": round(ev, 2),
            "ev_multiple": round(ev_multiple, 3),
            "roi": round(roi, 2),
            "bonus_ev": bonus_ev,
            "bonus_breakdown": bonus_result["breakdown"],
            "payout_breakdown": payout_breakdown,
        }

    def ev_at_price_points(
        self,
        golfer_probs: dict,
        total_pool: float,
        prices: list[float],
    ) -> list[dict]:
        """Calculate EV curve across multiple price points.

        Useful for understanding how value degrades as bidding rises.

        Args:
            golfer_probs: Golfer probability data.
            total_pool: Total auction pool.
            prices: List of price points to evaluate.

        Returns:
            List of EV results, one per price point, sorted by price.
        """
        results = []
        for price in sorted(prices):
            result = self.calculate_ev(golfer_probs, price, total_pool)
            result["price"] = price
            results.append(result)
        return results

    def breakeven_price(
        self,
        golfer_probs: dict,
        total_pool: float,
    ) -> float:
        """Find the price at which EV equals zero.

        This is the maximum you should ever bid for a golfer -- any
        price above this is negative EV.

        Args:
            golfer_probs: Golfer probability data.
            total_pool: Total auction pool.

        Returns:
            Breakeven price in dollars.
        """
        # Breakeven occurs when price = expected_payout, so just
        # calculate expected payout at price=0 (the price doesn't
        # affect the payout calculation, only the EV).
        result = self.calculate_ev(golfer_probs, price=1.0, total_pool=total_pool)
        return result["expected_payout"]

    def risk_adjusted_ev(
        self,
        golfer_probs: dict,
        price: float,
        total_pool: float,
        risk_aversion: float = 0.5,
    ) -> float:
        """Expected value adjusted for variance and risk aversion.

        Uses a mean-variance utility function:
            U = EV - (risk_aversion * variance)

        Higher risk_aversion penalizes high-variance bets (longshots)
        and rewards predictable outcomes (favorites with high cut rates).

        A risk_aversion of 0.0 is risk-neutral (pure EV).
        A risk_aversion of 1.0 is very conservative.

        Args:
            golfer_probs: Golfer probability data.
            price: Purchase price.
            total_pool: Total auction pool.
            risk_aversion: Risk aversion coefficient in [0, 1].

        Returns:
            Risk-adjusted EV in dollars.
        """
        finish_probs = self._golfer_finish_probs(golfer_probs)

        # Calculate the full distribution of outcomes
        outcomes = []
        probabilities = []

        # Probability of each payout tier
        total_finish_prob = 0.0
        for pos_label, pool_pct in self.payout_tiers:
            prob = finish_probs.get(pos_label, 0.0)
            payout = total_pool * pool_pct - price  # net profit
            outcomes.append(payout)
            probabilities.append(prob)
            total_finish_prob += prob

        # Probability of missing all payout tiers (total loss)
        miss_prob = max(1.0 - total_finish_prob, 0.0)
        outcomes.append(-price)  # lose entire purchase price
        probabilities.append(miss_prob)

        outcomes_arr = np.array(outcomes)
        probs_arr = np.array(probabilities)

        # Normalize probabilities if they exceed 1 due to overlapping tiers
        if probs_arr.sum() > 1.0:
            probs_arr = probs_arr / probs_arr.sum()

        mean_ev = float(np.dot(outcomes_arr, probs_arr))
        variance = float(np.dot(probs_arr, (outcomes_arr - mean_ev) ** 2))
        std_dev = math.sqrt(variance)

        # Mean-variance utility
        risk_penalty = risk_aversion * std_dev
        risk_adjusted = mean_ev - risk_penalty

        return round(risk_adjusted, 2)
