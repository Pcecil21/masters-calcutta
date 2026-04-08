"""
Contrarian intelligence engine for Calcutta auction strategy.

Identifies and quantifies disagreements between the model's probability
estimates and the market consensus (betting odds / public perception).
These divergences represent potential edges -- places where the crowd
is systematically wrong and you can profit.

The engine classifies each edge by type (course history undervalued,
form trajectory missed, narrative overvalued, etc.) and generates
human-readable explanations so you can make informed decisions during
the fast-paced live auction.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np


# Edge type taxonomy
EDGE_TYPES = {
    "course_history_undervalued": (
        "Augusta history is underappreciated. Past performance at this course "
        "is one of the strongest predictors, and the market is ignoring it."
    ),
    "form_trajectory_missed": (
        "Recent form trajectory is being missed. The market is anchored to "
        "older results while this golfer's game is trending sharply."
    ),
    "narrative_overvalued": (
        "The narrative is driving the price, not the stats. Compelling storyline "
        "but the numbers don't support the premium."
    ),
    "experience_premium_ignored": (
        "Experience at Augusta matters enormously but the market is treating "
        "this veteran like any other golfer in this ranking tier."
    ),
    "stat_mismatch": (
        "Key Augusta-relevant stats (approach play, scrambling, par-5 scoring) "
        "are significantly better than the market price implies."
    ),
    "recency_bias_victim": (
        "One or two bad recent results have cratered this golfer's market value, "
        "but the underlying game remains elite."
    ),
}


class AntiConsensusEngine:
    """Contrarian analysis engine for finding mispriced golfers.

    Compares model probabilities against consensus (market/betting)
    probabilities and ranks golfers by the magnitude and confidence
    of the disagreement.
    """

    def __init__(self, z_score_threshold: float = 1.0) -> None:
        """Initialize the engine.

        Args:
            z_score_threshold: Minimum z-score magnitude to flag a golfer
                as a meaningful divergence.  Default 1.0 (one standard
                deviation from the mean divergence across the field).
        """
        self.z_score_threshold = z_score_threshold

    @staticmethod
    def calculate_divergence(
        model_prob: float,
        consensus_prob: float,
    ) -> dict:
        """Quantify the disagreement between model and consensus.

        Args:
            model_prob: Model-estimated win probability.
            consensus_prob: Market/consensus win probability (from odds).

        Returns:
            Dictionary with:
                - raw_diff: model_prob - consensus_prob (positive = undervalued)
                - percent_diff: percentage difference relative to consensus
                - ratio: model_prob / consensus_prob
                - direction: "undervalued" or "overvalued"
                - magnitude: absolute size of divergence
        """
        raw_diff = model_prob - consensus_prob
        if consensus_prob > 0:
            percent_diff = (raw_diff / consensus_prob) * 100
            ratio = model_prob / consensus_prob
        else:
            percent_diff = float("inf") if model_prob > 0 else 0.0
            ratio = float("inf") if model_prob > 0 else 1.0

        direction = "undervalued" if raw_diff > 0 else "overvalued"
        magnitude = abs(raw_diff)

        return {
            "raw_diff": round(raw_diff, 6),
            "percent_diff": round(percent_diff, 1),
            "ratio": round(ratio, 3),
            "direction": direction,
            "magnitude": round(magnitude, 6),
        }

    def rank_contrarian_plays(
        self,
        golfers: list[dict],
    ) -> list[dict]:
        """Rank all golfers by divergence magnitude weighted by confidence.

        Each golfer dict should have:
            - id or golfer_id: str
            - name: str
            - model_win_prob: float
            - consensus_win_prob: float
            - world_ranking: int (optional, used for confidence weighting)

        The ranking uses a composite score:
            score = |percent_diff| * confidence_weight

        Where confidence_weight is higher for golfers where we have
        more data (higher-ranked golfers with more tournament history).

        Args:
            golfers: List of golfer data dicts.

        Returns:
            Sorted list of contrarian play analysis dicts.
        """
        if not golfers:
            return []

        # Calculate all divergences first for z-score computation
        divergences = []
        for g in golfers:
            model_p = g.get("model_win_prob", 0.0)
            consensus_p = g.get("consensus_win_prob", 0.0)
            div = self.calculate_divergence(model_p, consensus_p)
            divergences.append((g, div))

        # Compute z-scores across the field
        raw_diffs = [d["raw_diff"] for _, d in divergences]
        if len(raw_diffs) > 1:
            mean_diff = np.mean(raw_diffs)
            std_diff = np.std(raw_diffs)
            if std_diff == 0:
                std_diff = 1.0
        else:
            mean_diff = 0.0
            std_diff = 1.0

        results = []
        for g, div in divergences:
            golfer_id = g.get("id", g.get("golfer_id", "unknown"))
            name = g.get("name", "Unknown")
            ranking = g.get("world_ranking", 50)

            z_score = (div["raw_diff"] - mean_diff) / std_diff

            # Confidence weight: higher for well-known golfers (more data)
            # and for larger absolute probabilities (less noise)
            base_prob = max(g.get("model_win_prob", 0), g.get("consensus_win_prob", 0))
            prob_confidence = min(base_prob * 50, 1.0)  # scales 0-1 for probs up to 2%
            rank_confidence = min(1.0, 80.0 / max(ranking, 1))  # top-10 gets ~1.0
            confidence = (prob_confidence * 0.6 + rank_confidence * 0.4)
            confidence = round(min(confidence, 1.0), 3)

            # Composite score for ranking
            composite_score = abs(div["percent_diff"]) * confidence

            # Classify the confidence level
            if abs(z_score) >= 2.0 and confidence >= 0.6:
                confidence_level = "HIGH"
            elif abs(z_score) >= 1.5 or confidence >= 0.5:
                confidence_level = "MEDIUM"
            else:
                confidence_level = "LOW"

            results.append({
                "golfer_id": golfer_id,
                "name": name,
                "model_win_prob": g.get("model_win_prob", 0.0),
                "consensus_win_prob": g.get("consensus_win_prob", 0.0),
                "divergence": div,
                "z_score": round(z_score, 3),
                "confidence": confidence,
                "confidence_level": confidence_level,
                "composite_score": round(composite_score, 2),
                "direction": div["direction"],
            })

        # Sort by composite score descending (biggest disagreements first)
        results.sort(key=lambda x: x["composite_score"], reverse=True)
        return results

    @staticmethod
    def classify_edge_type(golfer: dict) -> str:
        """Classify the type of edge the model has identified.

        Uses golfer attributes to determine WHY the model disagrees
        with consensus.  This helps the bidder understand and trust
        the recommendation.

        The golfer dict can include:
            - augusta_history_score: 0-100
            - recent_form_score: 0-100
            - masters_appearances: int
            - masters_wins: int
            - world_ranking: int
            - model_win_prob: float
            - consensus_win_prob: float
            - current_season_stats: dict (with keys like sg_approach, sg_around_green)

        Args:
            golfer: Golfer data dict.

        Returns:
            Edge type string matching one of the EDGE_TYPES keys.
        """
        model_p = golfer.get("model_win_prob", 0.0)
        consensus_p = golfer.get("consensus_win_prob", 0.0)
        is_undervalued = model_p > consensus_p

        augusta_score = golfer.get("augusta_history_score", 0.0)
        form_score = golfer.get("recent_form_score", 0.0)
        masters_apps = golfer.get("masters_appearances", 0)
        masters_wins = golfer.get("masters_wins", 0)
        ranking = golfer.get("world_ranking", 50)
        stats = golfer.get("current_season_stats", {})

        if is_undervalued:
            # Check for course history edge
            if augusta_score >= 70 and masters_apps >= 5:
                return "course_history_undervalued"

            # Check for form trajectory edge
            if form_score >= 75 and ranking > 20:
                return "form_trajectory_missed"

            # Check for experience edge
            if masters_apps >= 10 and masters_wins == 0 and augusta_score >= 50:
                return "experience_premium_ignored"

            # Check for stat mismatch
            sg_approach = stats.get("sg_approach", 0)
            sg_arg = stats.get("sg_around_green", 0)
            if sg_approach > 0.5 or sg_arg > 0.5:
                return "stat_mismatch"

            # Check for recency bias
            if ranking <= 30 and form_score < 50:
                return "recency_bias_victim"

            # Default for undervalued
            return "stat_mismatch"
        else:
            # Overvalued golfer
            if masters_wins >= 1 or masters_apps >= 15:
                return "narrative_overvalued"
            if form_score >= 80:
                return "narrative_overvalued"
            return "narrative_overvalued"

    @staticmethod
    def generate_narrative(
        golfer: dict,
        edge_type: str,
    ) -> str:
        """Generate a human-readable explanation of the model's disagreement.

        Produces a concise, opinionated narrative that explains WHY
        the model disagrees with consensus, using the golfer's actual
        data to support the argument.

        Args:
            golfer: Golfer data dict with name, probabilities, and attributes.
            edge_type: Edge classification from classify_edge_type().

        Returns:
            1-3 sentence narrative string.
        """
        name = golfer.get("name", "This golfer")
        model_p = golfer.get("model_win_prob", 0.0)
        consensus_p = golfer.get("consensus_win_prob", 0.0)
        ranking = golfer.get("world_ranking", 50)
        form_score = golfer.get("recent_form_score", 0.0)
        augusta_score = golfer.get("augusta_history_score", 0.0)
        masters_apps = golfer.get("masters_appearances", 0)
        masters_wins = golfer.get("masters_wins", 0)
        masters_top10s = golfer.get("masters_top10s", 0)
        stats = golfer.get("current_season_stats", {})

        model_pct = model_p * 100
        consensus_pct = consensus_p * 100
        diff_pct = abs(model_p - consensus_p) / max(consensus_p, 0.001) * 100

        is_undervalued = model_p > consensus_p
        direction_word = "undervalued" if is_undervalued else "overvalued"

        if edge_type == "course_history_undervalued":
            detail = ""
            if masters_top10s > 0:
                detail = f" with {masters_top10s} top-10 finishes in {masters_apps} appearances"
            elif masters_apps > 0:
                detail = f" in {masters_apps} Masters appearances"
            return (
                f"{name}'s Augusta history{detail} is being completely "
                f"ignored by the market. Model says {model_pct:.1f}% win probability "
                f"vs. consensus {consensus_pct:.1f}% -- {direction_word} by {diff_pct:.0f}%+. "
                f"Course experience at Augusta is one of the strongest edges in golf."
            )

        if edge_type == "form_trajectory_missed":
            return (
                f"{name} has been trending sharply upward (form score: {form_score:.0f}/100) "
                f"but the market is stuck on older perceptions. Model sees {model_pct:.1f}% "
                f"win probability vs. consensus {consensus_pct:.1f}%. The current game is "
                f"significantly better than the world ranking ({ranking}) suggests."
            )

        if edge_type == "narrative_overvalued":
            reason = "past glory" if masters_wins > 0 else "hype"
            return (
                f"{name} is being bid up on {reason}, not current form. Consensus has "
                f"{consensus_pct:.1f}% but the model only sees {model_pct:.1f}%. "
                f"Let someone else overpay for the name -- the numbers don't support it."
            )

        if edge_type == "experience_premium_ignored":
            return (
                f"{name} has {masters_apps} Masters under their belt -- that institutional "
                f"knowledge of Augusta's subtleties is worth real money. Model says "
                f"{model_pct:.1f}% vs. consensus {consensus_pct:.1f}%. Experience is the "
                f"most underpriced asset in a Calcutta."
            )

        if edge_type == "stat_mismatch":
            sg_approach = stats.get("sg_approach", 0)
            sg_arg = stats.get("sg_around_green", 0)
            stat_detail = ""
            if sg_approach > 0:
                stat_detail = f" approach play ranks elite ({sg_approach:+.2f} SG)"
            elif sg_arg > 0:
                stat_detail = f" short game ranks elite ({sg_arg:+.2f} SG around green)"
            return (
                f"{name}'s key Augusta-relevant stats are being overlooked. "
                f"Model: {model_pct:.1f}% vs. consensus: {consensus_pct:.1f}%"
                f"{' --' + stat_detail if stat_detail else ''}. "
                f"The profile fits Augusta's demands better than the modest public "
                f"profile suggests."
            )

        if edge_type == "recency_bias_victim":
            return (
                f"{name} (world #{ranking}) has hit a rough patch recently "
                f"(form: {form_score:.0f}/100) but the underlying talent is still elite. "
                f"Model: {model_pct:.1f}% vs. consensus: {consensus_pct:.1f}%. "
                f"Recency bias is creating a buying opportunity."
            )

        # Fallback
        return (
            f"{name}: model sees {model_pct:.1f}% win probability vs. consensus "
            f"{consensus_pct:.1f}% ({direction_word} by {diff_pct:.0f}%)."
        )
