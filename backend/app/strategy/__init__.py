"""
Strategy modules for the Masters Calcutta Auction system.

Provides Kelly Criterion bankroll management, expected value calculations,
game theory / bidder behavior modeling, and contrarian analysis.
"""

from .kelly import KellyCalculator
from .ev_calculator import EVCalculator
from .game_theory import BidderModel
from .anti_consensus import AntiConsensusEngine

__all__ = [
    "KellyCalculator",
    "EVCalculator",
    "BidderModel",
    "AntiConsensusEngine",
]
