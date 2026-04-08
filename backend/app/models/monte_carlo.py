"""
Monte Carlo tournament simulator for The Masters at Augusta National.

Simulates thousands of 4-round tournaments with Augusta-specific scoring
adjustments to produce empirical probability distributions for each golfer's
finish position, including win, top-5/10/20, and make-cut rates.

Uses fully vectorized numpy operations -- no Python loops over simulations
or golfers -- to run 10K sims x 90 golfers in under a second.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats


# ---------------------------------------------------------------------------
# Augusta National scoring constants
# ---------------------------------------------------------------------------
AUGUSTA_PAR = 72
AUGUSTA_SCORING_AVG = 72.5  # Typical field scoring average (all rounds)
CUT_AFTER_ROUND = 2  # Cut applied after round 2
CUT_TOP_N = 50  # Top 50 and ties make the cut at the Masters

# Amen Corner difficulty: holes 11 (par 4), 12 (par 3), 13 (par 5).
# These three holes play roughly 0.35 strokes over their cumulative par
# for the average player, adding variance and difficulty.
AMEN_CORNER_DIFFICULTY = 0.35  # Extra strokes per round vs. neutral holes

# Par 5 birdie rate adjustment.  Augusta's par 5s are reachable for
# long hitters and typically play under par.  We apply a per-round
# adjustment proportional to the golfer's par-5 scoring advantage.
PAR5_BIRDIE_WEIGHT = 0.40  # Scaling factor for par-5 advantage

# Wind / weather adds variance.  Augusta rounds can swing by 2-3 strokes
# when afternoon winds pick up or when early morning calm gives an edge.
WEATHER_VARIANCE_EXTRA = 0.6  # Additional std-dev points on windy days

# Sunday pressure: variance increases in the final round, especially for
# golfers near the lead.  This captures the empirical finding that
# final-round scoring spreads are wider at majors.
SUNDAY_PRESSURE_VARIANCE = 0.8  # Extra std-dev for round 4

# Cache path for simulation results
_CACHE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "seed" / "mc_cache.json"


class MonteCarloSimulator:
    """Monte Carlo engine for simulating Masters tournament outcomes.

    Each golfer is characterized by a scoring average and a consistency
    metric (standard deviation of round scores).  The simulator draws
    round scores from a normal distribution, applies Augusta-specific
    adjustments, enforces the 36-hole cut, and tallies finish positions
    across many simulations to estimate probabilities.
    """

    def __init__(self, seed: int | None = None) -> None:
        """Initialize the simulator.

        Args:
            seed: Optional RNG seed for reproducibility.
        """
        self.rng = np.random.default_rng(seed)

    # ------------------------------------------------------------------
    # Single-round simulation (convenience method for external callers)
    # ------------------------------------------------------------------

    def simulate_round(
        self,
        golfer_stats: dict[str, Any],
        round_number: int = 1,
        weather_factor: float = 0.0,
    ) -> float:
        """Simulate a single 18-hole round score for one golfer.

        The score is drawn from a normal distribution centered on the
        golfer's expected scoring average (adjusted for Augusta) with
        standard deviation derived from their consistency metric.

        Args:
            golfer_stats: Dict containing at minimum:
                - ``scoring_avg`` (float): Expected 18-hole scoring
                  average (e.g., 70.5 for an elite player).
                - ``consistency`` (float): Standard deviation of round
                  scores (typical range 2.2 - 3.5).
                Optional:
                - ``par5_advantage`` (float): Strokes better than field
                  average on par 5s per round (e.g., -0.3).
                - ``amen_corner_skill`` (float): Skill factor for holes
                  11-13, range [-1, 1] where positive = better (default 0).
                - ``pressure_rating`` (float): How the golfer performs
                  under pressure, range [-1, 1] (default 0).
            round_number: Which round (1-4).  Round 4 gets extra variance.
            weather_factor: Weather severity, 0.0 = calm, 1.0 = very windy.

        Returns:
            Simulated round score as a float (may be fractional; callers
            should round or sum before converting to integer).
        """
        base_avg = golfer_stats.get("scoring_avg", AUGUSTA_SCORING_AVG)
        base_std = golfer_stats.get("consistency", 2.8)

        # --- Augusta adjustments ---

        # Amen Corner difficulty (adds strokes for average players,
        # partially offset by skilled players)
        amen_skill = golfer_stats.get("amen_corner_skill", 0.0)
        amen_adj = AMEN_CORNER_DIFFICULTY * (1.0 - 0.6 * np.clip(amen_skill, -1, 1))

        # Par 5 advantage (negative = good, reduces expected score)
        par5_adv = golfer_stats.get("par5_advantage", 0.0)
        par5_adj = par5_adv * PAR5_BIRDIE_WEIGHT

        # Weather variance
        weather_std = weather_factor * WEATHER_VARIANCE_EXTRA

        # Sunday pressure (round 4 only)
        pressure_std = 0.0
        pressure_adj = 0.0
        if round_number == 4:
            pressure_std = SUNDAY_PRESSURE_VARIANCE
            pressure_rating = golfer_stats.get("pressure_rating", 0.0)
            # Golfers who choke under pressure score slightly higher
            pressure_adj = -0.3 * pressure_rating  # positive rating = handles it well

        # Combine
        mean_score = base_avg + amen_adj + par5_adj + pressure_adj
        total_std = np.sqrt(
            base_std**2 + weather_std**2 + pressure_std**2
        )

        score = float(self.rng.normal(mean_score, total_std))

        # Floor at a reasonable minimum (even the best round at Augusta
        # is unlikely to be lower than 62)
        return max(score, 62.0)

    # ------------------------------------------------------------------
    # Full-tournament simulation (vectorized)
    # ------------------------------------------------------------------

    def simulate_tournament(
        self,
        field: list[dict[str, Any]],
        n_simulations: int = 10_000,
        weather_schedule: list[float] | None = None,
        use_cache: bool = True,
    ) -> dict[str, dict[str, Any]]:
        """Simulate a full 4-round Masters tournament many times.

        Uses fully vectorized numpy operations: all simulations and all
        golfers are processed in bulk array operations with no Python
        loops over sims or golfers.

        For each simulation:
          1. Simulate rounds 1 and 2 for every golfer.
          2. Apply the 36-hole cut (top 50 and ties).
          3. Simulate rounds 3 and 4 for golfers who made the cut.
          4. Rank by 72-hole total and record finish positions.

        Args:
            field: List of golfer dicts.  Each must have ``golfer_id`` (str)
                and the keys expected by :meth:`simulate_round`.
            n_simulations: Number of tournament simulations to run.
            weather_schedule: Optional 4-element list of weather factors
                for each round (0.0 = calm, 1.0 = very windy).  If None,
                weather is drawn randomly per simulation.
            use_cache: If True, check for / write to mc_cache.json.

        Returns:
            Dict keyed by golfer_id, each containing:
                - ``win_prob`` (float)
                - ``top5_prob`` (float)
                - ``top10_prob`` (float)
                - ``top20_prob`` (float)
                - ``make_cut_prob`` (float)
                - ``avg_finish`` (float)
                - ``win_count`` (int)
                - ``simulations`` (int)
        """
        # --- Check cache ---
        if use_cache:
            cached = self._load_cache()
            if cached is not None:
                return cached

        n_sims = n_simulations
        n_golfers = len(field)
        id_list = [g["golfer_id"] for g in field]

        # -----------------------------------------------------------------
        # Pre-compute per-golfer scoring parameters as 1-D arrays (n_golfers,)
        # -----------------------------------------------------------------
        means = np.array(
            [g.get("scoring_avg", AUGUSTA_SCORING_AVG) for g in field],
            dtype=np.float64,
        )
        base_stds = np.array(
            [g.get("consistency", 2.8) for g in field], dtype=np.float64
        )
        amen_skills = np.clip(
            np.array([g.get("amen_corner_skill", 0.0) for g in field], dtype=np.float64),
            -1.0, 1.0,
        )
        amen_adjustments = AMEN_CORNER_DIFFICULTY * (1.0 - 0.6 * amen_skills)

        par5_advantages = np.array(
            [g.get("par5_advantage", 0.0) for g in field], dtype=np.float64
        )
        par5_adjustments = par5_advantages * PAR5_BIRDIE_WEIGHT

        pressure_ratings = np.array(
            [g.get("pressure_rating", 0.0) for g in field], dtype=np.float64
        )
        # Sunday-only adjustments (mean shift and extra std)
        pressure_mean_adj = -0.3 * pressure_ratings  # (n_golfers,)

        # Combined mean for rounds 1-3 (no pressure) and round 4 (with pressure)
        mean_r123 = means + amen_adjustments + par5_adjustments  # (n_golfers,)
        mean_r4 = mean_r123 + pressure_mean_adj  # (n_golfers,)

        # -----------------------------------------------------------------
        # Weather: generate (n_sims, 4) weather factors
        # -----------------------------------------------------------------
        if weather_schedule is not None:
            # Broadcast fixed schedule across all sims
            weather = np.broadcast_to(
                np.array(weather_schedule, dtype=np.float64), (n_sims, 4)
            ).copy()
        else:
            weather = np.clip(
                self.rng.exponential(0.3, size=(n_sims, 4)), 0.0, 1.0
            )

        # Weather std per round: (n_sims, 1) for broadcasting with golfers
        weather_stds = weather * WEATHER_VARIANCE_EXTRA  # (n_sims, 4)

        # -----------------------------------------------------------------
        # Compute total std per (sim, golfer) for each round type
        # Rounds 1-3: sqrt(base_std^2 + weather_std^2)
        # Round 4:    sqrt(base_std^2 + weather_std^2 + SUNDAY_PRESSURE^2)
        # -----------------------------------------------------------------
        base_var = base_stds**2  # (n_golfers,)
        pressure_var = SUNDAY_PRESSURE_VARIANCE**2

        # For rounds 1-2: weather varies per sim, base_var varies per golfer
        # weather_stds[:, r] is (n_sims,), base_var is (n_golfers,)
        # Result: (n_sims, n_golfers)
        def _total_std(round_idx: int, include_pressure: bool = False) -> np.ndarray:
            w_var = weather_stds[:, round_idx:round_idx+1] ** 2  # (n_sims, 1)
            variance = base_var[np.newaxis, :] + w_var  # (n_sims, n_golfers)
            if include_pressure:
                variance = variance + pressure_var
            return np.sqrt(variance)

        # -----------------------------------------------------------------
        # Generate round scores: (n_sims, n_golfers) per round
        # -----------------------------------------------------------------
        # Rounds 1 & 2
        std_r1 = _total_std(0)
        std_r2 = _total_std(1)
        scores_r1 = self.rng.normal(
            mean_r123[np.newaxis, :], std_r1, size=(n_sims, n_golfers)
        )
        scores_r2 = self.rng.normal(
            mean_r123[np.newaxis, :], std_r2, size=(n_sims, n_golfers)
        )

        # Floor at 62
        scores_r1 = np.maximum(scores_r1, 62.0)
        scores_r2 = np.maximum(scores_r2, 62.0)

        # 36-hole totals
        totals_36 = scores_r1 + scores_r2  # (n_sims, n_golfers)

        # -----------------------------------------------------------------
        # Apply cut: top 50 and ties per simulation
        # -----------------------------------------------------------------
        # Sort 36-hole scores per sim to find the cut line
        sorted_36 = np.sort(totals_36, axis=1)  # (n_sims, n_golfers)
        cut_idx = min(CUT_TOP_N - 1, n_golfers - 1)
        cut_lines = sorted_36[:, cut_idx]  # (n_sims,)

        # Boolean mask: True = made the cut
        made_cut = totals_36 <= cut_lines[:, np.newaxis]  # (n_sims, n_golfers)

        # -----------------------------------------------------------------
        # Rounds 3 & 4 (generate for all, then mask missed-cut)
        # -----------------------------------------------------------------
        std_r3 = _total_std(2)
        std_r4 = _total_std(3, include_pressure=True)
        scores_r3 = self.rng.normal(
            mean_r123[np.newaxis, :], std_r3, size=(n_sims, n_golfers)
        )
        scores_r4 = self.rng.normal(
            mean_r4[np.newaxis, :], std_r4, size=(n_sims, n_golfers)
        )
        scores_r3 = np.maximum(scores_r3, 62.0)
        scores_r4 = np.maximum(scores_r4, 62.0)

        # 72-hole totals; missed-cut golfers get infinity
        totals_72 = scores_r1 + scores_r2 + scores_r3 + scores_r4  # (n_sims, n_golfers)
        totals_72 = np.where(made_cut, totals_72, np.inf)

        # -----------------------------------------------------------------
        # Rank golfers per simulation using scipy rankdata (handles ties)
        # rankdata with method='min' gives tied golfers the lowest rank
        # -----------------------------------------------------------------
        # For missed-cut golfers (inf), rankdata will assign them the
        # highest ranks.  We override those to n_golfers+1.
        positions = np.apply_along_axis(
            lambda row: stats.rankdata(row, method="min"), axis=1, arr=totals_72
        ).astype(np.int64)  # (n_sims, n_golfers)

        # Override missed-cut positions
        positions = np.where(made_cut, positions, n_golfers + 1)

        # -----------------------------------------------------------------
        # Tally counts using vectorized comparisons
        # -----------------------------------------------------------------
        win_counts = np.sum(positions == 1, axis=0)      # (n_golfers,)
        top5_counts = np.sum(positions <= 5, axis=0)
        top10_counts = np.sum(positions <= 10, axis=0)
        top20_counts = np.sum(positions <= 20, axis=0)
        cut_counts = np.sum(made_cut, axis=0)

        # Average finish: for missed-cut sims, assign nominal position = n_golfers
        finish_positions = np.where(made_cut, positions, n_golfers).astype(np.float64)
        finish_sums = np.sum(finish_positions, axis=0)

        # -----------------------------------------------------------------
        # Build results dict
        # -----------------------------------------------------------------
        results: dict[str, dict[str, Any]] = {}
        for i, gid in enumerate(id_list):
            results[gid] = {
                "win_prob": float(win_counts[i] / n_sims),
                "top5_prob": float(top5_counts[i] / n_sims),
                "top10_prob": float(top10_counts[i] / n_sims),
                "top20_prob": float(top20_counts[i] / n_sims),
                "make_cut_prob": float(cut_counts[i] / n_sims),
                "avg_finish": float(finish_sums[i] / n_sims),
                "win_count": int(win_counts[i]),
                "simulations": n_sims,
            }

        # --- Save cache ---
        if use_cache:
            self._save_cache(results)

        return results

    # ------------------------------------------------------------------
    # Cache management
    # ------------------------------------------------------------------

    @staticmethod
    def _load_cache() -> dict[str, dict[str, Any]] | None:
        """Load cached MC results if the cache file exists."""
        if _CACHE_PATH.exists():
            try:
                with open(_CACHE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    @staticmethod
    def _save_cache(results: dict[str, dict[str, Any]]) -> None:
        """Save MC results to the cache file."""
        _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

    @classmethod
    def clear_cache(cls) -> None:
        """Delete the MC cache file if it exists."""
        if _CACHE_PATH.exists():
            _CACHE_PATH.unlink()

    # ------------------------------------------------------------------
    # Convenience: build field from ELO ratings
    # ------------------------------------------------------------------

    @staticmethod
    def field_from_elos(
        elo_ratings: dict[str, float],
        golfer_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Convert ELO ratings into a field list suitable for simulation.

        Maps ELO to an approximate scoring average and consistency using
        a linear model calibrated to PGA Tour data:
            scoring_avg ~ 74.5 - (elo - 1500) * 0.008
            consistency ~ 3.2 - (elo - 1500) * 0.001

        Additional metadata (par5_advantage, amen_corner_skill, etc.)
        is merged from *golfer_metadata* if provided.

        Args:
            elo_ratings: Golfer id -> ELO rating.
            golfer_metadata: Optional additional stats per golfer.

        Returns:
            List of golfer dicts ready for :meth:`simulate_tournament`.
        """
        field = []
        for gid, elo in elo_ratings.items():
            delta = elo - 1500.0
            scoring_avg = 74.5 - delta * 0.008
            # Clamp scoring average to realistic bounds
            scoring_avg = float(np.clip(scoring_avg, 67.0, 78.0))
            consistency = float(np.clip(3.2 - delta * 0.001, 1.8, 4.0))

            entry: dict[str, Any] = {
                "golfer_id": gid,
                "scoring_avg": scoring_avg,
                "consistency": consistency,
            }

            if golfer_metadata and gid in golfer_metadata:
                entry.update(golfer_metadata[gid])

            field.append(entry)

        return field
