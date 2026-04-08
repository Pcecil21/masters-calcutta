"""
Masters Golf Calcutta Auction - Probabilistic Modeling Engine

Provides ELO ratings, Monte Carlo simulation, regression modeling,
and an ensemble combiner to predict golfer probabilities at Augusta National.
"""

from .probability import (
    normalize_probabilities,
    implied_probability_from_odds,
    remove_vig,
    placement_probabilities,
)
from .elo import GolfEloModel
from .monte_carlo import MonteCarloSimulator
from .regression import RegressionModel
from .ensemble import EnsembleModel
from .pipeline import generate_model_probabilities

__all__ = [
    "normalize_probabilities",
    "implied_probability_from_odds",
    "remove_vig",
    "placement_probabilities",
    "GolfEloModel",
    "MonteCarloSimulator",
    "RegressionModel",
    "EnsembleModel",
    "generate_model_probabilities",
]
