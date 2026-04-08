"""
Ensemble model combiner for Masters tournament predictions.

Blends predictions from the ELO, Monte Carlo, and Regression models
using configurable weights.  Default weights give the most influence
to the Monte Carlo simulator (which captures variance and Augusta-
specific scoring dynamics) with meaningful contributions from the
data-driven regression model and the ELO system.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.optimize import minimize

from .elo import GolfEloModel
from .monte_carlo import MonteCarloSimulator
from .regression import RegressionModel
from .probability import normalize_probabilities, placement_probabilities


# Outcome keys used throughout the ensemble
OUTCOMES = ("win", "top5", "top10", "top20", "make_cut")


class EnsembleModel:
    """Weighted ensemble of ELO, Monte Carlo, and Regression models.

    Attributes:
        elo_model: The ELO rating model instance.
        mc_model: The Monte Carlo simulator instance.
        reg_model: The regression model instance.
        weights: Dict mapping model name to blend weight (sum to 1.0).
    """

    def __init__(
        self,
        elo_model: GolfEloModel | None = None,
        mc_model: MonteCarloSimulator | None = None,
        reg_model: RegressionModel | None = None,
        weights: dict[str, float] | None = None,
    ) -> None:
        """Initialize the ensemble.

        Args:
            elo_model: Pre-configured ELO model.  Created with defaults if None.
            mc_model: Pre-configured Monte Carlo simulator.  Created if None.
            reg_model: Pre-configured regression model.  Created if None.
            weights: Model blend weights.  Keys must be "elo", "monte_carlo",
                "regression".  Defaults to ELO=0.25, MC=0.40, Reg=0.35.
        """
        self.elo_model = elo_model or GolfEloModel()
        self.mc_model = mc_model or MonteCarloSimulator()
        self.reg_model = reg_model or RegressionModel()

        if weights is not None:
            total = sum(weights.values())
            self.weights = {k: v / total for k, v in weights.items()}
        else:
            self.weights = {
                "elo": 0.25,
                "monte_carlo": 0.40,
                "regression": 0.35,
            }

    # ------------------------------------------------------------------
    # Individual model predictions
    # ------------------------------------------------------------------

    def _get_elo_predictions(
        self,
        golfers: list[dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        """Get predictions from the ELO model.

        The ELO model directly produces win probabilities.  Placement
        probabilities are derived via empirical multipliers.
        """
        # Build adjustment data if available
        adjustments: dict[str, dict[str, Any]] = {}
        for g in golfers:
            gid = g["golfer_id"]
            adj_data: dict[str, Any] = {}
            if "masters_finishes" in g:
                adj_data["masters_finishes"] = g["masters_finishes"]
            if "masters_appearances" in g:
                adj_data["masters_appearances"] = g["masters_appearances"]
            if "par5_scoring_avg" in g:
                adj_data["par5_scoring_avg"] = g["par5_scoring_avg"]
            if "stimp_putting_sg" in g:
                adj_data["stimp_putting_sg"] = g["stimp_putting_sg"]
            if adj_data:
                adjustments[gid] = adj_data

            # Ensure the golfer is in the ELO ratings
            if gid not in self.elo_model.ratings:
                self.elo_model.ratings[gid] = g.get("elo_rating", 1500.0)

        win_probs = self.elo_model.predict_field(
            golfer_adjustments=adjustments if adjustments else None
        )

        # Convert win probs to full placement probabilities
        field_size = len(golfers)
        results: dict[str, dict[str, float]] = {}
        for gid, wp in win_probs.items():
            placements = placement_probabilities(wp, field_size)
            results[gid] = {
                "win": placements["win"],
                "top5": placements["top5"],
                "top10": placements["top10"],
                "top20": placements["top20"],
                "make_cut": placements["make_cut"],
            }

        return results

    def _get_mc_predictions(
        self,
        golfers: list[dict[str, Any]],
        n_simulations: int = 10_000,
    ) -> dict[str, dict[str, float]]:
        """Get predictions from the Monte Carlo simulator."""
        # Build field from golfer data, falling back to ELO-derived stats
        field = []
        for g in golfers:
            entry: dict[str, Any] = {"golfer_id": g["golfer_id"]}

            # Scoring average: use provided or derive from ELO
            if "scoring_avg" in g:
                entry["scoring_avg"] = g["scoring_avg"]
            else:
                elo = self.elo_model.ratings.get(g["golfer_id"], 1500.0)
                entry["scoring_avg"] = 74.5 - (elo - 1500.0) * 0.008

            entry["consistency"] = g.get("consistency", 2.8)
            entry["par5_advantage"] = g.get("par5_advantage", 0.0)
            entry["amen_corner_skill"] = g.get("amen_corner_skill", 0.0)
            entry["pressure_rating"] = g.get("pressure_rating", 0.0)

            field.append(entry)

        mc_results = self.mc_model.simulate_tournament(
            field=field, n_simulations=n_simulations
        )

        # Extract the probability keys we need
        results: dict[str, dict[str, float]] = {}
        for gid, data in mc_results.items():
            results[gid] = {
                "win": data["win_prob"],
                "top5": data["top5_prob"],
                "top10": data["top10_prob"],
                "top20": data["top20_prob"],
                "make_cut": data["make_cut_prob"],
            }

        return results

    def _get_regression_predictions(
        self,
        golfers: list[dict[str, Any]],
    ) -> dict[str, dict[str, float]]:
        """Get predictions from the regression model."""
        return self.reg_model.predict_field(golfers)

    # ------------------------------------------------------------------
    # Ensemble blending
    # ------------------------------------------------------------------

    def predict_field(
        self,
        golfers: list[dict[str, Any]],
        n_simulations: int = 10_000,
    ) -> dict[str, dict[str, float]]:
        """Produce final blended probabilities for each golfer.

        Combines predictions from all three models using the configured
        weights, then normalizes win probabilities to sum to 1.0.

        Args:
            golfers: List of golfer dicts.  Each must have ``golfer_id``
                and may contain any features used by the sub-models.
            n_simulations: Number of Monte Carlo simulations to run.

        Returns:
            Dict keyed by golfer_id -> {win, top5, top10, top20, make_cut}.
            Win probabilities sum to 1.0 across the field.
        """
        # Collect predictions from each model
        elo_preds = self._get_elo_predictions(golfers)
        mc_preds = self._get_mc_predictions(golfers, n_simulations)
        reg_preds = self._get_regression_predictions(golfers)

        w_elo = self.weights["elo"]
        w_mc = self.weights["monte_carlo"]
        w_reg = self.weights["regression"]

        # Blend
        blended: dict[str, dict[str, float]] = {}
        for g in golfers:
            gid = g["golfer_id"]
            combined: dict[str, float] = {}

            for outcome in OUTCOMES:
                elo_val = elo_preds.get(gid, {}).get(outcome, 0.0)
                mc_val = mc_preds.get(gid, {}).get(outcome, 0.0)
                reg_val = reg_preds.get(gid, {}).get(outcome, 0.0)

                combined[outcome] = (
                    w_elo * elo_val + w_mc * mc_val + w_reg * reg_val
                )

            blended[gid] = combined

        # Normalize win probabilities to sum to 1.0
        win_probs = {gid: p["win"] for gid, p in blended.items()}
        normalized_wins = normalize_probabilities(win_probs)

        for gid in blended:
            blended[gid]["win"] = normalized_wins[gid]

            # Re-enforce monotonicity after normalization
            blended[gid]["top5"] = max(blended[gid]["top5"], blended[gid]["win"])
            blended[gid]["top10"] = max(blended[gid]["top10"], blended[gid]["top5"])
            blended[gid]["top20"] = max(blended[gid]["top20"], blended[gid]["top10"])
            blended[gid]["make_cut"] = max(
                blended[gid]["make_cut"], blended[gid]["top20"]
            )

        return blended

    # ------------------------------------------------------------------
    # Weight calibration
    # ------------------------------------------------------------------

    def calibrate_weights(
        self, historical_results: list[dict[str, Any]]
    ) -> dict[str, float]:
        """Optimize ensemble weights by backtesting on historical data.

        Uses Brier score minimization across all outcomes to find the
        blend weights that would have produced the most accurate
        predictions historically.

        Each entry in *historical_results* should contain:
            - ``golfer_id`` (str)
            - ``features`` (dict): Feature values for the golfer.
            - ``actual`` (dict): Actual outcomes with keys matching OUTCOMES,
              each True/False.
            - ``elo_pred`` (dict): ELO model predictions (optional; will be
              computed if missing).
            - ``mc_pred`` (dict): Monte Carlo predictions (optional).
            - ``reg_pred`` (dict): Regression predictions (optional).

        Args:
            historical_results: List of historical prediction-vs-actual records.

        Returns:
            Optimized weight dict.  Also updates self.weights in place.
        """
        if len(historical_results) < 10:
            # Not enough data to calibrate; keep defaults
            return dict(self.weights)

        # Extract prediction vectors for each model and actuals
        n = len(historical_results)
        n_outcomes = len(OUTCOMES)

        actuals = np.zeros((n, n_outcomes), dtype=np.float64)
        elo_arr = np.zeros((n, n_outcomes), dtype=np.float64)
        mc_arr = np.zeros((n, n_outcomes), dtype=np.float64)
        reg_arr = np.zeros((n, n_outcomes), dtype=np.float64)

        for i, entry in enumerate(historical_results):
            for j, outcome in enumerate(OUTCOMES):
                actuals[i, j] = float(entry.get("actual", {}).get(outcome, 0))
                elo_arr[i, j] = float(entry.get("elo_pred", {}).get(outcome, 0))
                mc_arr[i, j] = float(entry.get("mc_pred", {}).get(outcome, 0))
                reg_arr[i, j] = float(entry.get("reg_pred", {}).get(outcome, 0))

        def brier_score(weights_raw: np.ndarray) -> float:
            """Compute mean Brier score for given weights."""
            # Softmax to ensure weights sum to 1 and are positive
            exp_w = np.exp(weights_raw - weights_raw.max())
            w = exp_w / exp_w.sum()

            blended = w[0] * elo_arr + w[1] * mc_arr + w[2] * reg_arr
            blended = np.clip(blended, 1e-6, 1.0 - 1e-6)
            brier = np.mean((blended - actuals) ** 2)
            return float(brier)

        # Initial weights in log-space
        x0 = np.log(np.array([0.25, 0.40, 0.35]))

        result = minimize(brier_score, x0, method="Nelder-Mead")

        if result.success:
            exp_w = np.exp(result.x - result.x.max())
            optimal = exp_w / exp_w.sum()
            self.weights = {
                "elo": float(optimal[0]),
                "monte_carlo": float(optimal[1]),
                "regression": float(optimal[2]),
            }

        return dict(self.weights)

    # ------------------------------------------------------------------
    # Confidence intervals
    # ------------------------------------------------------------------

    def get_confidence_interval(
        self,
        golfer_id: str,
        golfers: list[dict[str, Any]],
        confidence: float = 0.90,
        n_bootstrap: int = 1_000,
        n_simulations_per: int = 2_000,
    ) -> dict[str, tuple[float, float]]:
        """Compute bootstrap confidence intervals for a golfer's probabilities.

        Runs multiple Monte Carlo simulations with different random seeds
        and computes the requested confidence interval from the resulting
        distribution of probability estimates.

        Args:
            golfer_id: The golfer to compute intervals for.
            golfers: Full field data (same format as predict_field).
            confidence: Confidence level (e.g., 0.90 for 90% CI).
            n_bootstrap: Number of bootstrap iterations.
            n_simulations_per: Monte Carlo simulations per bootstrap iteration.

        Returns:
            Dict keyed by outcome -> (lower_bound, upper_bound).
        """
        alpha = (1.0 - confidence) / 2.0

        # Collect MC results across bootstrap iterations
        samples: dict[str, list[float]] = {outcome: [] for outcome in OUTCOMES}

        # Build field once for reuse
        field = []
        for g in golfers:
            entry: dict[str, Any] = {"golfer_id": g["golfer_id"]}
            if "scoring_avg" in g:
                entry["scoring_avg"] = g["scoring_avg"]
            else:
                elo = self.elo_model.ratings.get(g["golfer_id"], 1500.0)
                entry["scoring_avg"] = 74.5 - (elo - 1500.0) * 0.008
            entry["consistency"] = g.get("consistency", 2.8)
            entry["par5_advantage"] = g.get("par5_advantage", 0.0)
            entry["amen_corner_skill"] = g.get("amen_corner_skill", 0.0)
            entry["pressure_rating"] = g.get("pressure_rating", 0.0)
            field.append(entry)

        for b in range(n_bootstrap):
            sim = MonteCarloSimulator(seed=b * 7919 + 42)
            mc_results = sim.simulate_tournament(
                field=field, n_simulations=n_simulations_per
            )

            if golfer_id in mc_results:
                data = mc_results[golfer_id]
                samples["win"].append(data["win_prob"])
                samples["top5"].append(data["top5_prob"])
                samples["top10"].append(data["top10_prob"])
                samples["top20"].append(data["top20_prob"])
                samples["make_cut"].append(data["make_cut_prob"])
            else:
                for outcome in OUTCOMES:
                    samples[outcome].append(0.0)

        intervals: dict[str, tuple[float, float]] = {}
        for outcome in OUTCOMES:
            arr = np.array(samples[outcome])
            lower = float(np.percentile(arr, 100.0 * alpha))
            upper = float(np.percentile(arr, 100.0 * (1.0 - alpha)))
            intervals[outcome] = (lower, upper)

        return intervals
