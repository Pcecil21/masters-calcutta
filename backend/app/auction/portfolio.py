"""
Portfolio optimization for Calcutta auction management.

Analyzes the current portfolio of purchased golfers, estimates
correlation between outcomes, runs scenario analysis, and recommends
optimal remaining allocations to maximize expected profit while
managing downside risk.

Key insight: in a Calcutta, you want a diversified portfolio --
owning five mid-tier golfers with uncorrelated outcomes is far
better than owning one elite golfer, because the variance reduction
dramatically improves your expected geometric return.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np

from app.models.probability import placement_probabilities
from app.strategy.ev_calculator import EVCalculator


# Playing style categories for correlation estimation
_STYLE_CATEGORIES = {
    "bomber": ["bryson_dechambeau", "rory_mcilroy", "jon_rahm", "cameron_young", "dustin_johnson"],
    "precision": ["matt_fitzpatrick", "collin_morikawa", "patrick_cantlay", "xander_schauffele"],
    "scrambler": ["jordan_spieth", "phil_mickelson", "adam_scott", "jason_day"],
    "all_around": ["scottie_scheffler", "viktor_hovland", "hideki_matsuyama", "justin_thomas"],
    "grinder": ["sungjae_im", "tom_kim", "corey_conners", "brian_harman"],
}


class PortfolioOptimizer:
    """Portfolio analysis and optimization for Calcutta golfer portfolios.

    Evaluates the combined risk/return profile of a set of purchased
    golfers and recommends portfolio-improving additions.
    """

    def __init__(
        self,
        payout_structure: Optional[dict[str, float]] = None,
        total_pool: float = 10000.0,
    ) -> None:
        """Initialize the optimizer.

        Args:
            payout_structure: Custom payout structure for EV calculations.
            total_pool: Total auction pool in dollars.
        """
        self.total_pool = total_pool
        self.ev_calc = EVCalculator(payout_structure)

    def analyze(self, positions: list[dict]) -> dict:
        """Full portfolio analysis.

        Each position dict should have:
            - golfer_id: str
            - name: str (optional)
            - purchase_price: float
            - model_win_prob: float
            - model_top5_prob: float (optional)
            - model_top10_prob: float (optional)
            - world_ranking: int (optional)

        Args:
            positions: List of purchased golfer positions.

        Returns:
            Comprehensive portfolio analysis dict.
        """
        if not positions:
            return {
                "total_invested": 0.0,
                "total_expected_value": 0.0,
                "expected_roi": 0.0,
                "positions": [],
                "diversification_score": 0.0,
                "correlation_summary": "No positions to analyze.",
                "upside_scenario": {},
                "downside_scenario": {},
            }

        position_analyses = []
        total_invested = 0.0
        total_ev = 0.0

        for pos in positions:
            price = pos.get("purchase_price", 0)
            probs = {
                "win_prob": pos.get("model_win_prob", 0),
                "top5_prob": pos.get("model_top5_prob", 0),
                "top10_prob": pos.get("model_top10_prob", 0),
            }

            ev_result = self.ev_calc.calculate_ev(probs, price, self.total_pool)

            total_invested += price
            total_ev += ev_result["expected_payout"]

            position_analyses.append({
                "golfer_id": pos.get("golfer_id", "unknown"),
                "name": pos.get("name", "Unknown"),
                "purchase_price": price,
                "expected_payout": ev_result["expected_payout"],
                "ev": ev_result["ev"],
                "ev_multiple": ev_result["ev_multiple"],
                "roi": ev_result["roi"],
                "portfolio_weight": 0.0,  # computed below
            })

        # Portfolio weights
        for pa in position_analyses:
            pa["portfolio_weight"] = round(
                pa["purchase_price"] / total_invested * 100, 1
            ) if total_invested > 0 else 0.0

        expected_roi = (
            (total_ev - total_invested) / total_invested * 100
            if total_invested > 0 else 0.0
        )

        # Diversification score (0-100, higher = more diversified)
        div_score = self._diversification_score(positions)

        # Correlation summary
        corr_matrix = self.correlation_matrix(positions)
        avg_corr = self._average_correlation(corr_matrix)
        if avg_corr < 0.2:
            corr_summary = "Excellent diversification -- low correlation between positions."
        elif avg_corr < 0.4:
            corr_summary = "Good diversification -- moderate correlation."
        elif avg_corr < 0.6:
            corr_summary = "Fair diversification -- some clustering risk."
        else:
            corr_summary = "Poor diversification -- positions are highly correlated."

        # Scenario analysis
        scenarios = self._quick_scenarios(positions)

        return {
            "total_invested": round(total_invested, 2),
            "total_expected_value": round(total_ev, 2),
            "expected_profit": round(total_ev - total_invested, 2),
            "expected_roi": round(expected_roi, 2),
            "positions": position_analyses,
            "num_positions": len(positions),
            "diversification_score": div_score,
            "avg_correlation": round(avg_corr, 3),
            "correlation_summary": corr_summary,
            "upside_scenario": scenarios["upside"],
            "downside_scenario": scenarios["downside"],
            "median_scenario": scenarios["median"],
        }

    def optimal_remaining_allocation(
        self,
        portfolio: list[dict],
        remaining_golfers: list[dict],
        remaining_budget: float,
    ) -> list[dict]:
        """Recommend which remaining golfers best complement the portfolio.

        Scores each remaining golfer by:
        1. Expected value at estimated market price
        2. Diversification benefit (low correlation with existing portfolio)
        3. Portfolio gap filling (do we need an anchor? longshot lottery?)

        Args:
            portfolio: Currently owned positions.
            remaining_golfers: Golfers still available for purchase.
            remaining_budget: Dollars left to spend.

        Returns:
            Ranked list of recommended additions with scores and reasoning.
        """
        if not remaining_golfers or remaining_budget <= 0:
            return []

        # Analyze current portfolio composition
        has_elite = any(p.get("model_win_prob", 0) > 0.04 for p in portfolio)
        has_mid = any(0.01 < p.get("model_win_prob", 0) <= 0.04 for p in portfolio)
        has_longshot = any(p.get("model_win_prob", 0) <= 0.01 for p in portfolio)
        num_owned = len(portfolio)

        recommendations = []

        for g in remaining_golfers:
            gid = g.get("golfer_id", g.get("id", "unknown"))
            price = g.get("estimated_market_price", g.get("price", 0))
            if price <= 0 or price > remaining_budget:
                continue

            win_prob = g.get("model_win_prob", 0)
            probs = {
                "win_prob": win_prob,
                "top5_prob": g.get("model_top5_prob", 0),
                "top10_prob": g.get("model_top10_prob", 0),
            }

            ev_result = self.ev_calc.calculate_ev(probs, price, self.total_pool)

            # Diversification score: how much does this golfer reduce portfolio correlation?
            div_benefit = self._diversification_benefit(g, portfolio)

            # Gap-filling bonus
            gap_bonus = 0.0
            tier = "longshot"
            if win_prob > 0.04:
                tier = "elite"
                if not has_elite:
                    gap_bonus = 0.3  # big bonus for filling elite gap
            elif win_prob > 0.01:
                tier = "mid_tier"
                if not has_mid:
                    gap_bonus = 0.15
            else:
                if not has_longshot and num_owned >= 3:
                    gap_bonus = 0.1  # bonus for lottery tickets when portfolio is building

            # Composite score: EV-driven with diversification and gap bonuses
            ev_score = ev_result["ev_multiple"] if ev_result["ev_multiple"] != float("inf") else 0
            composite = ev_score * (1 + div_benefit + gap_bonus)

            reasoning_parts = []
            if ev_result["ev"] > 0:
                reasoning_parts.append(
                    f"EV+${ev_result['ev']:.0f} ({ev_result['ev_multiple']:.2f}x)"
                )
            else:
                reasoning_parts.append(f"EV${ev_result['ev']:.0f} ({ev_result['ev_multiple']:.2f}x)")

            if div_benefit > 0.15:
                reasoning_parts.append("strong diversification benefit")
            if gap_bonus > 0:
                reasoning_parts.append(f"fills {tier} gap in portfolio")

            recommendations.append({
                "golfer_id": gid,
                "name": g.get("name", "Unknown"),
                "estimated_price": round(price, 2),
                "expected_payout": ev_result["expected_payout"],
                "ev": ev_result["ev"],
                "ev_multiple": ev_result["ev_multiple"],
                "tier": tier,
                "diversification_benefit": round(div_benefit, 3),
                "gap_bonus": round(gap_bonus, 3),
                "composite_score": round(composite, 3),
                "reasoning": " | ".join(reasoning_parts),
            })

        recommendations.sort(key=lambda x: x["composite_score"], reverse=True)
        return recommendations

    def scenario_analysis(
        self,
        portfolio: list[dict],
        payout_structure: Optional[dict] = None,
        total_pool: Optional[float] = None,
    ) -> dict:
        """Probability of various profit levels via Monte Carlo simulation.

        Runs 10,000 simulated tournaments to estimate the distribution
        of portfolio outcomes.

        Args:
            portfolio: List of owned positions.
            payout_structure: Custom payout structure (or use instance default).
            total_pool: Custom pool size (or use instance default).

        Returns:
            Dict with probability of profit, 2x, breakeven, loss,
            expected profit, worst case, best case, and percentiles.
        """
        pool = total_pool or self.total_pool
        n_simulations = 10_000

        total_invested = sum(p.get("purchase_price", 0) for p in portfolio)
        if total_invested == 0 or not portfolio:
            return {
                "p_profit": 0.0,
                "p_2x": 0.0,
                "p_breakeven": 0.0,
                "p_loss": 1.0,
                "expected_profit": 0.0,
                "worst_case": 0.0,
                "best_case": 0.0,
                "median_profit": 0.0,
                "percentile_25": 0.0,
                "percentile_75": 0.0,
            }

        # Build payout tiers from structure
        ev_calc = EVCalculator(payout_structure) if payout_structure else self.ev_calc
        payout_tiers = ev_calc.payout_tiers

        # For each golfer, build a payout distribution
        # Positions: list of (purchase_price, list of (prob, payout))
        golfer_payouts = []
        for pos in portfolio:
            price = pos.get("purchase_price", 0)
            win_prob = pos.get("model_win_prob", 0)
            placements = placement_probabilities(win_prob)

            # Build discrete outcomes
            outcomes = []
            # Win
            outcomes.append((win_prob, pool * 0.50))
            # 2nd-5th
            p_2_5 = max(placements["top5"] - win_prob, 0)
            if p_2_5 > 0:
                outcomes.append((p_2_5, pool * 0.085))  # average of 2nd-5th payouts
            # 6th-10th
            p_6_10 = max(placements["top10"] - placements["top5"], 0)
            if p_6_10 > 0:
                outcomes.append((p_6_10, pool * 0.016))  # average of 6th-10th payouts
            # Miss everything
            total_p = sum(o[0] for o in outcomes)
            miss_p = max(1.0 - total_p, 0.0)
            outcomes.append((miss_p, 0.0))

            golfer_payouts.append((price, outcomes))

        # Monte Carlo simulation
        rng = np.random.default_rng(seed=42)
        portfolio_returns = np.zeros(n_simulations)

        for price, outcomes in golfer_payouts:
            probs = [o[0] for o in outcomes]
            payouts = [o[1] for o in outcomes]

            # Normalize probs
            prob_arr = np.array(probs)
            prob_arr = np.maximum(prob_arr, 0)
            prob_sum = prob_arr.sum()
            if prob_sum > 0:
                prob_arr = prob_arr / prob_sum
            else:
                prob_arr = np.ones(len(probs)) / len(probs)

            # Sample outcomes
            indices = rng.choice(len(payouts), size=n_simulations, p=prob_arr)
            sim_payouts = np.array([payouts[i] for i in indices])
            portfolio_returns += sim_payouts - price

        # Analyze distribution
        p_profit = float(np.mean(portfolio_returns > 0))
        p_2x = float(np.mean(portfolio_returns > total_invested))
        p_breakeven = float(np.mean(portfolio_returns >= 0))
        p_loss = float(np.mean(portfolio_returns < 0))

        return {
            "p_profit": round(p_profit, 4),
            "p_2x": round(p_2x, 4),
            "p_breakeven": round(p_breakeven, 4),
            "p_loss": round(p_loss, 4),
            "expected_profit": round(float(np.mean(portfolio_returns)), 2),
            "worst_case": round(float(np.min(portfolio_returns)), 2),
            "best_case": round(float(np.max(portfolio_returns)), 2),
            "median_profit": round(float(np.median(portfolio_returns)), 2),
            "percentile_25": round(float(np.percentile(portfolio_returns, 25)), 2),
            "percentile_75": round(float(np.percentile(portfolio_returns, 75)), 2),
        }

    def correlation_matrix(self, golfers: list[dict]) -> dict:
        """Estimate pairwise outcome correlation between golfers.

        Golfers with similar playing styles have correlated tournament
        outcomes -- if conditions favor bombers, all bombers benefit.
        This estimates correlation using:
          - Playing style similarity (same category = higher correlation)
          - World ranking proximity (similar skill = correlated)
          - Augusta history similarity

        Args:
            golfers: List of golfer data dicts.

        Returns:
            Dict with 'matrix' (2D dict), 'labels' (golfer ids), and
            'avg_correlation' (float).
        """
        if len(golfers) < 2:
            return {"matrix": {}, "labels": [], "avg_correlation": 0.0}

        n = len(golfers)
        ids = [g.get("golfer_id", g.get("id", f"golfer_{i}")) for i, g in enumerate(golfers)]

        # Build correlation matrix
        corr = np.eye(n)

        for i in range(n):
            for j in range(i + 1, n):
                c = self._estimate_pairwise_correlation(golfers[i], golfers[j])
                corr[i, j] = c
                corr[j, i] = c

        # Convert to nested dict
        matrix = {}
        for i, id_i in enumerate(ids):
            matrix[id_i] = {}
            for j, id_j in enumerate(ids):
                matrix[id_i][id_j] = round(float(corr[i, j]), 3)

        # Average off-diagonal correlation
        if n > 1:
            off_diag = corr[np.triu_indices(n, k=1)]
            avg = float(np.mean(off_diag))
        else:
            avg = 0.0

        return {
            "matrix": matrix,
            "labels": ids,
            "avg_correlation": round(avg, 3),
        }

    @staticmethod
    def _estimate_pairwise_correlation(g1: dict, g2: dict) -> float:
        """Estimate outcome correlation between two golfers.

        Based on playing style overlap, ranking proximity, and
        Augusta history similarity.
        """
        base_correlation = 0.15  # all golfers in same tournament have some correlation

        # Style similarity
        id1 = g1.get("golfer_id", g1.get("id", "")).lower()
        id2 = g2.get("golfer_id", g2.get("id", "")).lower()

        style1 = None
        style2 = None
        for style, members in _STYLE_CATEGORIES.items():
            if id1 in members:
                style1 = style
            if id2 in members:
                style2 = style

        if style1 and style2 and style1 == style2:
            base_correlation += 0.25  # same style = more correlated

        # Ranking proximity: closer rankings = more correlated
        r1 = g1.get("world_ranking", 50)
        r2 = g2.get("world_ranking", 50)
        rank_diff = abs(r1 - r2)
        if rank_diff <= 5:
            base_correlation += 0.15
        elif rank_diff <= 15:
            base_correlation += 0.08
        elif rank_diff <= 30:
            base_correlation += 0.03

        # Augusta history: both experienced or both newcomers
        exp1 = g1.get("masters_appearances", 0)
        exp2 = g2.get("masters_appearances", 0)
        if (exp1 >= 5 and exp2 >= 5) or (exp1 <= 2 and exp2 <= 2):
            base_correlation += 0.05

        return min(base_correlation, 0.85)

    def _diversification_score(self, positions: list[dict]) -> float:
        """Score portfolio diversification from 0 (concentrated) to 100 (diversified)."""
        if len(positions) <= 1:
            return 0.0

        n = len(positions)

        # Factor 1: number of positions (more = better, diminishing returns)
        count_score = min(n / 8.0, 1.0) * 40  # max 40 points for 8+ golfers

        # Factor 2: weight concentration (HHI-based)
        total = sum(p.get("purchase_price", 1) for p in positions)
        if total > 0:
            weights = [p.get("purchase_price", 1) / total for p in positions]
            hhi = sum(w ** 2 for w in weights)
            # HHI of 1/n is perfectly even, HHI of 1.0 is fully concentrated
            even_hhi = 1.0 / n
            concentration = (hhi - even_hhi) / (1.0 - even_hhi) if n > 1 else 1.0
            weight_score = (1 - concentration) * 30  # max 30 points
        else:
            weight_score = 0.0

        # Factor 3: correlation (lower avg correlation = better)
        corr = self.correlation_matrix(positions)
        avg_corr = corr["avg_correlation"]
        corr_score = (1 - avg_corr) * 30  # max 30 points

        return round(count_score + weight_score + corr_score, 1)

    def _diversification_benefit(self, candidate: dict, portfolio: list[dict]) -> float:
        """How much diversification benefit does adding this golfer provide?"""
        if not portfolio:
            return 0.5  # neutral benefit for first golfer

        correlations = []
        for p in portfolio:
            c = self._estimate_pairwise_correlation(candidate, p)
            correlations.append(c)

        avg_corr = sum(correlations) / len(correlations)
        # Lower correlation with existing portfolio = higher benefit
        return max(0.5 - avg_corr, 0.0)

    @staticmethod
    def _average_correlation(corr_result: dict) -> float:
        """Extract average correlation from correlation_matrix result."""
        return corr_result.get("avg_correlation", 0.0)

    def _quick_scenarios(self, positions: list[dict]) -> dict:
        """Fast scenario estimates without full Monte Carlo."""
        total_invested = sum(p.get("purchase_price", 0) for p in positions)
        total_ev = 0.0
        best_win_payout = 0.0

        for pos in positions:
            probs = {
                "win_prob": pos.get("model_win_prob", 0),
                "top5_prob": pos.get("model_top5_prob", 0),
                "top10_prob": pos.get("model_top10_prob", 0),
            }
            ev_result = self.ev_calc.calculate_ev(
                probs, pos.get("purchase_price", 0), self.total_pool
            )
            total_ev += ev_result["expected_payout"]
            # Best case: this golfer wins
            win_payout = self.total_pool * 0.50
            if win_payout > best_win_payout:
                best_win_payout = win_payout

        return {
            "upside": {
                "description": "One of your golfers wins the Masters",
                "profit": round(best_win_payout - total_invested, 2),
                "roi": round(
                    (best_win_payout - total_invested) / total_invested * 100, 1
                ) if total_invested > 0 else 0,
            },
            "median": {
                "description": "Expected outcome based on model probabilities",
                "profit": round(total_ev - total_invested, 2),
                "roi": round(
                    (total_ev - total_invested) / total_invested * 100, 1
                ) if total_invested > 0 else 0,
            },
            "downside": {
                "description": "No golfer finishes in the money",
                "profit": round(-total_invested, 2),
                "roi": -100.0,
            },
        }
