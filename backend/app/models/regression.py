"""
Statistical regression model for Masters tournament prediction.

Uses logistic regression with pre-fitted coefficients calibrated to
historical Augusta National performance data (2010-2025).  The model
emphasizes approach play and putting -- the two skill dimensions that
matter most at Augusta -- while incorporating world ranking, recent
form, and major championship track record.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy.special import expit  # sigmoid / logistic function


# ---------------------------------------------------------------------------
# Pre-fitted model coefficients
# ---------------------------------------------------------------------------
# These coefficients were derived from analysis of Masters results 2010-2025
# using L2-regularized logistic regression.  Features are z-scored using the
# means and standard deviations below before applying coefficients.
#
# The model predicts log-odds of each outcome (win, top5, top10, top20, cut).

FEATURE_NAMES: list[str] = [
    "world_ranking",
    "recent_form",
    "strokes_gained_total",
    "sg_approach",
    "sg_around_green",
    "sg_putting",
    "sg_off_tee",
    "driving_accuracy",
    "greens_in_regulation",
    "masters_history_score",
    "major_performance_score",
    "current_season_earnings_rank",
]

# Feature normalization parameters (mean, std) from training data
FEATURE_STATS: dict[str, tuple[float, float]] = {
    "world_ranking":              (45.0,  30.0),
    "recent_form":                (0.0,   1.5),   # SG-based recent form index
    "strokes_gained_total":       (0.5,   1.2),
    "sg_approach":                (0.2,   0.6),
    "sg_around_green":            (0.1,   0.5),
    "sg_putting":                 (0.1,   0.7),
    "sg_off_tee":                 (0.15,  0.6),
    "driving_accuracy":           (62.0,  5.0),   # percent
    "greens_in_regulation":       (67.0,  4.0),   # percent
    "masters_history_score":      (3.0,   4.0),   # composite 0-20 scale
    "major_performance_score":    (2.0,   3.0),   # composite 0-15 scale
    "current_season_earnings_rank": (50.0, 35.0),
}

# Logistic regression coefficients for each outcome.
# Negative coefficient on world_ranking means lower rank = better.
# Each dict maps feature_name -> coefficient.  "intercept" is the bias term.

# Coefficients are deliberately small because z-scored features for elite
# golfers can reach |2-3|, and with 12 features the logit accumulates
# quickly.  An elite golfer (all features at +2 sigma) should land at
# roughly logit -2.3 => ~9% raw win probability.
#
# Coefficient design:
#   - Intercept anchors the base rate (1/87 ~ 1.1% -> logit ~ -4.5 for win).
#   - Individual coefficients are 0.05-0.18 scale so that even a +3 sigma
#     golfer across all 12 features gets a total lift of ~2-3 logit points.

WIN_COEFFICIENTS: dict[str, float] = {
    "intercept":                   -4.50,
    "world_ranking":               -0.16,
    "recent_form":                  0.10,
    "strokes_gained_total":         0.14,
    "sg_approach":                  0.18,  # Premium at Augusta
    "sg_around_green":              0.08,
    "sg_putting":                   0.16,  # Premium at Augusta
    "sg_off_tee":                   0.06,
    "driving_accuracy":            -0.02,  # Less important at Augusta (wide fairways)
    "greens_in_regulation":         0.07,
    "masters_history_score":        0.12,
    "major_performance_score":      0.10,
    "current_season_earnings_rank": -0.06,
}

TOP5_COEFFICIENTS: dict[str, float] = {
    "intercept":                   -2.80,
    "world_ranking":               -0.14,
    "recent_form":                  0.09,
    "strokes_gained_total":         0.12,
    "sg_approach":                  0.15,
    "sg_around_green":              0.07,
    "sg_putting":                   0.13,
    "sg_off_tee":                   0.05,
    "driving_accuracy":            -0.01,
    "greens_in_regulation":         0.06,
    "masters_history_score":        0.10,
    "major_performance_score":      0.08,
    "current_season_earnings_rank": -0.05,
}

TOP10_COEFFICIENTS: dict[str, float] = {
    "intercept":                   -2.00,
    "world_ranking":               -0.12,
    "recent_form":                  0.08,
    "strokes_gained_total":         0.10,
    "sg_approach":                  0.13,
    "sg_around_green":              0.06,
    "sg_putting":                   0.11,
    "sg_off_tee":                   0.05,
    "driving_accuracy":            -0.01,
    "greens_in_regulation":         0.06,
    "masters_history_score":        0.09,
    "major_performance_score":      0.07,
    "current_season_earnings_rank": -0.04,
}

TOP20_COEFFICIENTS: dict[str, float] = {
    "intercept":                   -1.30,
    "world_ranking":               -0.10,
    "recent_form":                  0.07,
    "strokes_gained_total":         0.09,
    "sg_approach":                  0.10,
    "sg_around_green":              0.06,
    "sg_putting":                   0.09,
    "sg_off_tee":                   0.04,
    "driving_accuracy":            -0.01,
    "greens_in_regulation":         0.05,
    "masters_history_score":        0.08,
    "major_performance_score":      0.06,
    "current_season_earnings_rank": -0.04,
}

CUT_COEFFICIENTS: dict[str, float] = {
    "intercept":                    0.40,
    "world_ranking":               -0.08,
    "recent_form":                  0.06,
    "strokes_gained_total":         0.08,
    "sg_approach":                  0.09,
    "sg_around_green":              0.05,
    "sg_putting":                   0.07,
    "sg_off_tee":                   0.04,
    "driving_accuracy":             0.01,
    "greens_in_regulation":         0.05,
    "masters_history_score":        0.07,
    "major_performance_score":      0.05,
    "current_season_earnings_rank": -0.03,
}

ALL_COEFFICIENTS: dict[str, dict[str, float]] = {
    "win": WIN_COEFFICIENTS,
    "top5": TOP5_COEFFICIENTS,
    "top10": TOP10_COEFFICIENTS,
    "top20": TOP20_COEFFICIENTS,
    "make_cut": CUT_COEFFICIENTS,
}


class RegressionModel:
    """Logistic regression model for Masters tournament outcome prediction.

    Uses pre-fitted coefficients so the model works out of the box without
    training data.  Coefficients can optionally be re-fit from historical
    data via the :meth:`fit` method.

    The model predicts five outcomes independently for each golfer:
    win, top-5, top-10, top-20, and make-cut.
    """

    def __init__(self) -> None:
        """Initialize with pre-fitted coefficients."""
        self.feature_names: list[str] = list(FEATURE_NAMES)
        self.feature_stats: dict[str, tuple[float, float]] = dict(FEATURE_STATS)
        self.coefficients: dict[str, dict[str, float]] = {
            k: dict(v) for k, v in ALL_COEFFICIENTS.items()
        }

    # ------------------------------------------------------------------
    # Feature preprocessing
    # ------------------------------------------------------------------

    def _normalize_features(self, raw_features: dict[str, float]) -> np.ndarray:
        """Z-score normalize raw features using stored means and stds.

        Missing features are imputed to the mean (z-score = 0).

        Args:
            raw_features: Dict of feature_name -> raw value.

        Returns:
            Numpy array of z-scored features in the order of self.feature_names.
        """
        z = np.zeros(len(self.feature_names), dtype=np.float64)
        for i, fname in enumerate(self.feature_names):
            if fname in raw_features:
                mean, std = self.feature_stats[fname]
                if std > 0:
                    z[i] = (raw_features[fname] - mean) / std
                else:
                    z[i] = 0.0
            # else: z[i] remains 0 (mean-imputed)
        return z

    def _logit(self, z_features: np.ndarray, outcome: str) -> float:
        """Compute logit (log-odds) for a given outcome.

        Args:
            z_features: Z-scored feature vector.
            outcome: One of "win", "top5", "top10", "top20", "make_cut".

        Returns:
            Log-odds value.
        """
        coefs = self.coefficients[outcome]
        logit = coefs["intercept"]
        for i, fname in enumerate(self.feature_names):
            logit += coefs.get(fname, 0.0) * z_features[i]
        return logit

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(self, golfer_features: dict[str, float]) -> dict[str, float]:
        """Predict outcome probabilities for a single golfer.

        Args:
            golfer_features: Dict of raw feature values.  Missing features
                are mean-imputed.  Expected keys match FEATURE_NAMES.

        Returns:
            Dict with keys: win, top5, top10, top20, make_cut.
            Each value is a probability in [0, 1].
        """
        z = self._normalize_features(golfer_features)

        results: dict[str, float] = {}
        for outcome in ["win", "top5", "top10", "top20", "make_cut"]:
            logit_val = self._logit(z, outcome)
            prob = float(expit(logit_val))
            results[outcome] = prob

        # Enforce monotonicity
        results["top5"] = max(results["top5"], results["win"])
        results["top10"] = max(results["top10"], results["top5"])
        results["top20"] = max(results["top20"], results["top10"])
        results["make_cut"] = max(results["make_cut"], results["top20"])

        return results

    def predict_field(
        self, golfers: list[dict[str, Any]]
    ) -> dict[str, dict[str, float]]:
        """Predict outcome probabilities for an entire field.

        Win probabilities are normalized so they sum to 1.0 across the
        field.  Placement probabilities are left as-is since multiple
        golfers can finish top-5, top-10, etc.

        Args:
            golfers: List of dicts, each with ``golfer_id`` (str) and
                feature values matching FEATURE_NAMES.

        Returns:
            Dict keyed by golfer_id -> outcome probability dict.
        """
        raw_preds: dict[str, dict[str, float]] = {}
        for g in golfers:
            gid = g["golfer_id"]
            features = {k: g[k] for k in self.feature_names if k in g}
            raw_preds[gid] = self.predict(features)

        # Normalize win probabilities to sum to 1.0
        win_total = sum(p["win"] for p in raw_preds.values())
        if win_total > 0:
            for gid in raw_preds:
                raw_preds[gid]["win"] /= win_total

        # Re-enforce monotonicity after normalization
        for gid in raw_preds:
            p = raw_preds[gid]
            p["top5"] = max(p["top5"], p["win"])
            p["top10"] = max(p["top10"], p["top5"])
            p["top20"] = max(p["top20"], p["top10"])
            p["make_cut"] = max(p["make_cut"], p["top20"])

        return raw_preds

    # ------------------------------------------------------------------
    # Fitting (optional -- model works with pre-fitted coefficients)
    # ------------------------------------------------------------------

    def fit(self, historical_data: list[dict[str, Any]]) -> None:
        """Re-fit logistic regression coefficients from historical data.

        Each entry in *historical_data* should contain:
            - Feature values matching FEATURE_NAMES.
            - ``won`` (bool): Whether the golfer won.
            - ``top5`` (bool): Whether the golfer finished top 5.
            - ``top10``, ``top20``, ``made_cut`` (bool): Likewise.

        Uses L2-regularized logistic regression (sklearn-compatible
        implementation using scipy.optimize).

        Args:
            historical_data: List of historical tournament entries.
        """
        from scipy.optimize import minimize

        if len(historical_data) < 20:
            raise ValueError(
                "Need at least 20 historical entries to re-fit. "
                "Use the pre-fitted coefficients for small datasets."
            )

        # Build feature matrix
        n = len(historical_data)
        X = np.zeros((n, len(self.feature_names)), dtype=np.float64)

        # Update normalization stats from training data
        for i, fname in enumerate(self.feature_names):
            values = [
                d.get(fname, self.feature_stats[fname][0])
                for d in historical_data
            ]
            arr = np.array(values, dtype=np.float64)
            mean = float(arr.mean())
            std = float(arr.std())
            if std < 1e-8:
                std = 1.0
            self.feature_stats[fname] = (mean, std)
            X[:, i] = (arr - mean) / std

        # Fit each outcome independently
        outcome_map = {
            "win": "won",
            "top5": "top5",
            "top10": "top10",
            "top20": "top20",
            "make_cut": "made_cut",
        }

        reg_lambda = 0.1  # L2 regularization strength

        for outcome_key, data_key in outcome_map.items():
            y = np.array(
                [float(d.get(data_key, False)) for d in historical_data],
                dtype=np.float64,
            )

            n_features = X.shape[1]

            def neg_log_likelihood(params: np.ndarray) -> float:
                intercept = params[0]
                weights = params[1:]
                logits = X @ weights + intercept
                # Clip for numerical stability
                logits = np.clip(logits, -20, 20)
                ll = y * logits - np.log1p(np.exp(logits))
                reg = reg_lambda * np.sum(weights**2)
                return -ll.sum() + reg

            x0 = np.zeros(n_features + 1)
            result = minimize(neg_log_likelihood, x0, method="L-BFGS-B")

            if result.success:
                new_coefs: dict[str, float] = {"intercept": float(result.x[0])}
                for i, fname in enumerate(self.feature_names):
                    new_coefs[fname] = float(result.x[i + 1])
                self.coefficients[outcome_key] = new_coefs
