"""
Monte Carlo tournament simulator for The Masters at Augusta National.

Simulates thousands of 4-round tournaments with Augusta-specific scoring
adjustments to produce empirical probability distributions for each golfer's
finish position, including win, top-5/10/20, and make-cut rates.
"""

from __future__ import annotations

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
    # Single-round simulation
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
    # Full-tournament simulation
    # ------------------------------------------------------------------

    def simulate_tournament(
        self,
        field: list[dict[str, Any]],
        n_simulations: int = 10_000,
        weather_schedule: list[float] | None = None,
    ) -> dict[str, dict[str, Any]]:
        """Simulate a full 4-round Masters tournament many times.

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
        n_golfers = len(field)
        id_list = [g["golfer_id"] for g in field]

        # Accumulators
        win_counts = np.zeros(n_golfers, dtype=np.int64)
        top5_counts = np.zeros(n_golfers, dtype=np.int64)
        top10_counts = np.zeros(n_golfers, dtype=np.int64)
        top20_counts = np.zeros(n_golfers, dtype=np.int64)
        cut_counts = np.zeros(n_golfers, dtype=np.int64)
        finish_sums = np.zeros(n_golfers, dtype=np.float64)

        for sim in range(n_simulations):
            # Determine weather for this simulation
            if weather_schedule is not None:
                weather = weather_schedule
            else:
                # Random weather: calm most of the time, occasionally windy
                weather = self.rng.exponential(0.3, size=4).clip(0, 1.0).tolist()

            # --- Rounds 1 & 2 ---
            scores_r1r2 = np.zeros(n_golfers, dtype=np.float64)
            round_scores = np.zeros((n_golfers, 4), dtype=np.float64)

            for i, golfer in enumerate(field):
                r1 = self.simulate_round(golfer, round_number=1, weather_factor=weather[0])
                r2 = self.simulate_round(golfer, round_number=2, weather_factor=weather[1])
                round_scores[i, 0] = r1
                round_scores[i, 1] = r2
                scores_r1r2[i] = r1 + r2

            # --- Apply cut (top 50 and ties) ---
            cut_line_score = np.sort(scores_r1r2)[min(CUT_TOP_N - 1, n_golfers - 1)]
            made_cut = scores_r1r2 <= cut_line_score

            # --- Rounds 3 & 4 (only for those who made the cut) ---
            total_scores = np.full(n_golfers, np.inf)  # missed cut = inf
            for i, golfer in enumerate(field):
                if not made_cut[i]:
                    continue
                r3 = self.simulate_round(golfer, round_number=3, weather_factor=weather[2])
                r4 = self.simulate_round(golfer, round_number=4, weather_factor=weather[3])
                round_scores[i, 2] = r3
                round_scores[i, 3] = r4
                total_scores[i] = round_scores[i].sum()

            # --- Rank and record ---
            # Sort by total score (ascending).  Ties share the better position.
            order = np.argsort(total_scores)
            positions = np.zeros(n_golfers, dtype=np.int64)

            rank = 1
            i = 0
            while i < n_golfers:
                # Find all golfers tied at this score
                j = i + 1
                while j < n_golfers and total_scores[order[j]] == total_scores[order[i]]:
                    j += 1
                for k in range(i, j):
                    positions[order[k]] = rank
                rank = j + 1
                i = j

            # Missed-cut golfers get a position beyond the field
            positions[~made_cut] = n_golfers + 1

            for i in range(n_golfers):
                pos = positions[i]
                if made_cut[i]:
                    cut_counts[i] += 1
                    finish_sums[i] += pos
                    if pos == 1:
                        win_counts[i] += 1
                    if pos <= 5:
                        top5_counts[i] += 1
                    if pos <= 10:
                        top10_counts[i] += 1
                    if pos <= 20:
                        top20_counts[i] += 1
                else:
                    # Assign a nominal finish position for averaging
                    finish_sums[i] += n_golfers

        # --- Convert counts to probabilities ---
        results: dict[str, dict[str, Any]] = {}
        for i, gid in enumerate(id_list):
            results[gid] = {
                "win_prob": float(win_counts[i] / n_simulations),
                "top5_prob": float(top5_counts[i] / n_simulations),
                "top10_prob": float(top10_counts[i] / n_simulations),
                "top20_prob": float(top20_counts[i] / n_simulations),
                "make_cut_prob": float(cut_counts[i] / n_simulations),
                "avg_finish": float(finish_sums[i] / n_simulations),
                "win_count": int(win_counts[i]),
                "simulations": n_simulations,
            }

        return results

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
