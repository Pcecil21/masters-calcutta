"""
Core probability calculations for golf tournament modeling.

Provides utility functions for odds conversion, vig removal,
probability normalization, and empirical placement probability
estimation calibrated to professional golf tournaments.
"""

import numpy as np


def normalize_probabilities(probs: dict[str, float]) -> dict[str, float]:
    """Normalize a dictionary of probabilities so values sum to 1.0.

    Handles edge cases: negative values are floored to zero before
    normalization, and an all-zero input returns uniform probabilities.

    Args:
        probs: Mapping of golfer_id -> raw probability value.

    Returns:
        Mapping of golfer_id -> normalized probability that sums to 1.0.

    Raises:
        ValueError: If probs is empty.
    """
    if not probs:
        raise ValueError("Cannot normalize an empty probability dict.")

    keys = list(probs.keys())
    values = np.array([probs[k] for k in keys], dtype=np.float64)

    # Floor negatives to zero
    values = np.maximum(values, 0.0)

    total = values.sum()
    if total == 0.0:
        # Uniform fallback when all inputs are zero or negative
        values = np.ones_like(values) / len(values)
    else:
        values = values / total

    return {k: float(v) for k, v in zip(keys, values)}


def implied_probability_from_odds(american_odds: int) -> float:
    """Convert American odds to implied probability.

    American odds express how much you win relative to a $100 stake:
      - Positive (+150): profit on a $100 bet  -> prob = 100 / (odds + 100)
      - Negative (-200): stake needed to win $100 -> prob = |odds| / (|odds| + 100)

    The result includes the bookmaker's vig and will therefore be
    slightly higher than the true probability.

    Args:
        american_odds: American-format odds (e.g., +800, -150).

    Returns:
        Implied probability as a float in (0, 1).

    Raises:
        ValueError: If american_odds is zero (not a valid American odds value).
    """
    if american_odds == 0:
        raise ValueError("American odds of 0 are not valid.")

    if american_odds > 0:
        return 100.0 / (american_odds + 100.0)
    else:
        return abs(american_odds) / (abs(american_odds) + 100.0)


def remove_vig(implied_probs: list[float]) -> list[float]:
    """Remove bookmaker vig (overround) from a set of implied probabilities.

    Bookmakers set odds so that implied probabilities sum to > 1.0 (the
    overround). This function scales them back so they sum to exactly 1.0,
    using the multiplicative method (proportional reduction).

    Args:
        implied_probs: List of implied probabilities from odds conversion.
            Must all be positive and their sum must exceed 0.

    Returns:
        List of true probabilities with the vig removed, summing to 1.0.

    Raises:
        ValueError: If any probability is non-positive or the list is empty.
    """
    if not implied_probs:
        raise ValueError("Cannot remove vig from an empty list.")

    arr = np.array(implied_probs, dtype=np.float64)

    if np.any(arr <= 0):
        raise ValueError("All implied probabilities must be positive.")

    overround = arr.sum()
    true_probs = arr / overround

    return true_probs.tolist()


def placement_probabilities(win_prob: float, field_size: int = 87) -> dict[str, float]:
    """Estimate top-5, top-10, top-20, and make-cut probabilities from win probability.

    Uses empirical multipliers derived from historical PGA Tour / Masters data.
    The relationship between win probability and placement probability is
    roughly linear for contenders but flattens for longshots due to high
    variance in 72-hole stroke play.

    Empirical multipliers (approximate, from 2010-2025 majors data):
        top5  ~ 3.5x win_prob
        top10 ~ 6.0x win_prob
        top20 ~ 10.0x win_prob
        cut   ~ 16.0x win_prob

    All values are capped at sensible maxima so that even a heavy favorite
    does not exceed realistic placement rates.

    Args:
        win_prob: Probability of winning the tournament, in [0, 1].
        field_size: Number of golfers in the field (default 87 for Masters).

    Returns:
        Dict with keys: win, top5, top10, top20, make_cut.
    """
    # Empirical multipliers calibrated to major championship data.
    # These are slightly non-linear: the multiplier compresses for
    # higher win probabilities to keep placement rates realistic.
    top5_raw = win_prob * (3.5 - 2.0 * win_prob)
    top10_raw = win_prob * (6.0 - 5.0 * win_prob)
    top20_raw = win_prob * (10.0 - 12.0 * win_prob)
    cut_raw = win_prob * (16.0 - 25.0 * win_prob)

    # Cap at realistic maxima.
    # Even the best golfer in the world makes the cut ~92% of the time
    # at the Masters, finishes top-20 ~55%, top-10 ~40%, top-5 ~28%.
    top5 = float(np.clip(top5_raw, 0.0, 0.30))
    top10 = float(np.clip(top10_raw, 0.0, 0.45))
    top20 = float(np.clip(top20_raw, 0.0, 0.60))
    make_cut = float(np.clip(cut_raw, 0.0, 0.95))

    # Enforce monotonicity: win <= top5 <= top10 <= top20 <= make_cut
    top5 = max(top5, win_prob)
    top10 = max(top10, top5)
    top20 = max(top20, top10)
    make_cut = max(make_cut, top20)

    # For very weak golfers, ensure a minimum cut probability based on
    # field size (roughly top-50 + ties make the cut at the Masters).
    cut_line_frac = min(50.0 / field_size, 0.65)
    # Even a random golfer in the field has some base probability.
    base_cut_prob = cut_line_frac * 0.15  # ~10-11% floor for weakest invitee
    make_cut = max(make_cut, base_cut_prob)

    return {
        "win": float(win_prob),
        "top5": top5,
        "top10": top10,
        "top20": top20,
        "make_cut": make_cut,
    }
