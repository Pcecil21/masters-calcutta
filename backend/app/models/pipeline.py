"""
Model pipeline for generating ensemble probabilities.

Provides a single entry-point function that orchestrates the ELO,
Monte Carlo, and Regression models through the EnsembleModel combiner,
returning blended probabilities keyed by golfer ID.
"""

from __future__ import annotations

import logging
from typing import Any

from .elo import DEFAULT_FIELD_ELOS, GolfEloModel
from .ensemble import EnsembleModel
from .monte_carlo import MonteCarloSimulator
from .regression import RegressionModel

logger = logging.getLogger(__name__)


def _elo_for_golfer(name: str, world_ranking: int) -> float:
    """Look up ELO from the default field dict, or estimate from ranking."""
    if name in DEFAULT_FIELD_ELOS:
        return DEFAULT_FIELD_ELOS[name]
    # Fallback: linear estimate from world ranking
    return max(1400.0, 1920.0 - (world_ranking - 1) * 8.0)


def _par5_advantage_from_stats(stats: dict) -> float:
    """Derive a par-5 advantage estimate from season stats.

    Golfers with high SG approach and SG total tend to score better
    on par 5s.  This is a rough proxy when we lack direct par-5 data.
    """
    sg_total = stats.get("sg_total", 0.0)
    sg_approach = stats.get("sg_approach", 0.0)
    # Positive SG -> negative par5_advantage (lower is better)
    return -(sg_total * 0.05 + sg_approach * 0.10)


def _pressure_rating_from_stats(golfer: Any) -> float:
    """Estimate pressure rating from Augusta history and recent form.

    Golfers with high Augusta history scores and wins handle pressure
    better.
    """
    augusta = getattr(golfer, "augusta_history_score", 50.0)
    wins = getattr(golfer, "masters_wins", 0)
    # Scale 0-100 Augusta score to roughly -0.5 to +0.5
    base = (augusta - 50.0) / 100.0
    win_bonus = min(wins * 0.15, 0.4)
    return float(min(max(base + win_bonus, -1.0), 1.0))


def _amen_corner_skill_from_stats(golfer: Any) -> float:
    """Estimate Amen Corner skill from Augusta history and SG approach."""
    augusta = getattr(golfer, "augusta_history_score", 50.0)
    stats = getattr(golfer, "current_season_stats", {})
    sg_approach = stats.get("sg_approach", 0.0)
    # Augusta history is the best proxy for Amen Corner skill
    base = (augusta - 50.0) / 80.0
    approach_bonus = sg_approach * 0.15
    return float(min(max(base + approach_bonus, -1.0), 1.0))


def generate_model_probabilities(golfers: dict) -> dict:
    """Run the full ensemble pipeline and return updated golfer probabilities.

    Args:
        golfers: dict of golfer_id -> Golfer objects (from the store).

    Returns:
        dict of golfer_id -> {model_win_prob, model_top5_prob,
        model_top10_prob, model_top20_prob, model_cut_prob}
    """
    if not golfers:
        return {}

    # -----------------------------------------------------------------
    # Step 1: Build ELO ratings map and field metadata
    # -----------------------------------------------------------------
    elo_ratings: dict[str, float] = {}
    golfer_metadata: dict[str, dict[str, Any]] = {}
    golfer_list: list[dict[str, Any]] = []

    for gid, golfer in golfers.items():
        name = getattr(golfer, "name", gid)
        world_ranking = getattr(golfer, "world_ranking", 50)
        stats = getattr(golfer, "current_season_stats", {})

        elo = _elo_for_golfer(name, world_ranking)
        elo_ratings[gid] = elo

        par5_adv = _par5_advantage_from_stats(stats)
        pressure = _pressure_rating_from_stats(golfer)
        amen_skill = _amen_corner_skill_from_stats(golfer)

        golfer_metadata[gid] = {
            "par5_advantage": par5_adv,
            "pressure_rating": pressure,
            "amen_corner_skill": amen_skill,
        }

        # Build the unified golfer dict used by the ensemble
        entry: dict[str, Any] = {
            "golfer_id": gid,
            "elo_rating": elo,
            "par5_advantage": par5_adv,
            "pressure_rating": pressure,
            "amen_corner_skill": amen_skill,
            "masters_appearances": getattr(golfer, "masters_appearances", 0),
            "masters_wins": getattr(golfer, "masters_wins", 0),
            "masters_top10s": getattr(golfer, "masters_top10s", 0),
        }

        # Merge season stats for the regression model
        if stats:
            entry["world_ranking"] = world_ranking
            entry["recent_form"] = (getattr(golfer, "recent_form_score", 50.0) - 50.0) / 33.0
            entry["strokes_gained_total"] = stats.get("sg_total", 0.0)
            entry["sg_approach"] = stats.get("sg_approach", 0.0)
            entry["sg_around_green"] = stats.get("sg_around_green", 0.0)
            entry["sg_putting"] = stats.get("sg_putting", 0.0)
            entry["sg_off_tee"] = stats.get("sg_off_tee", 0.0)
            entry["driving_accuracy"] = stats.get("driving_accuracy", 62.0)
            entry["greens_in_regulation"] = stats.get("gir_pct", 67.0)
            entry["masters_history_score"] = getattr(golfer, "augusta_history_score", 0.0) / 5.0
            entry["major_performance_score"] = (
                getattr(golfer, "masters_wins", 0) * 5.0
                + getattr(golfer, "masters_top10s", 0) * 1.0
            )
            entry["current_season_earnings_rank"] = world_ranking

        golfer_list.append(entry)

    # -----------------------------------------------------------------
    # Step 2: Build ensemble and run predictions
    # -----------------------------------------------------------------
    elo_model = GolfEloModel(initial_ratings=elo_ratings)
    mc_model = MonteCarloSimulator(seed=42)
    reg_model = RegressionModel()

    ensemble = EnsembleModel(
        elo_model=elo_model,
        mc_model=mc_model,
        reg_model=reg_model,
    )

    logger.info("Running ensemble prediction for %d golfers...", len(golfer_list))
    blended = ensemble.predict_field(golfer_list, n_simulations=10_000)

    # -----------------------------------------------------------------
    # Step 3: Map to the return format expected by the store
    # -----------------------------------------------------------------
    results: dict[str, dict[str, float]] = {}
    for gid in golfers:
        probs = blended.get(gid, {})
        results[gid] = {
            "model_win_prob": probs.get("win", 0.0),
            "model_top5_prob": probs.get("top5", 0.0),
            "model_top10_prob": probs.get("top10", 0.0),
            "model_top20_prob": probs.get("top20", 0.0),
            "model_cut_prob": probs.get("make_cut", 0.0),
        }

    return results
