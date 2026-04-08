"""Tests for the Kelly Criterion bankroll management engine."""

from __future__ import annotations

import pytest

from app.strategy.kelly import KellyCalculator


def test_kelly_zero_prob_returns_zero():
    """No bet when win probability is 0."""
    assert KellyCalculator.optimal_fraction(0.0, 2.0) == 0.0
    assert KellyCalculator.max_bid(0.0, expected_payout=500, bankroll=1000) == 0.0


def test_kelly_zero_bankroll_returns_zero():
    """No bid when bankroll is 0."""
    assert KellyCalculator.max_bid(0.3, expected_payout=500, bankroll=0) == 0.0


def test_fractional_kelly_less_than_full():
    """Quarter Kelly should produce a smaller fraction than full Kelly."""
    full = KellyCalculator.optimal_fraction(0.4, 3.0)
    quarter = KellyCalculator.fractional_kelly(0.4, 3.0, fraction=0.25)
    assert quarter < full
    assert quarter == pytest.approx(full * 0.25, rel=1e-6)


def test_max_bid_never_exceeds_bankroll():
    """max_bid must never exceed the current bankroll."""
    bankroll = 800
    bid = KellyCalculator.max_bid(
        win_prob=0.90,
        expected_payout=5000,
        bankroll=bankroll,
        fraction=1.0,  # full Kelly to push limits
    )
    assert bid <= bankroll


def test_max_bid_never_exceeds_expected_payout():
    """max_bid must never exceed expected_payout (breakeven ceiling)."""
    ep = 400
    bid = KellyCalculator.max_bid(
        win_prob=0.90,
        expected_payout=ep,
        bankroll=10000,
        fraction=1.0,
    )
    assert bid <= ep + 0.01  # tolerance for rounding


def test_portfolio_kelly_reduces_cap_at_high_exposure():
    """Effective kelly_cap should decrease as portfolio exposure increases."""
    positions_light = [
        {"golfer_id": "g1", "purchase_price": 100, "win_prob": 0.1, "expected_payout": 200},
    ]
    positions_heavy = [
        {"golfer_id": f"g{i}", "purchase_price": 150, "win_prob": 0.05, "expected_payout": 100}
        for i in range(6)  # 900 of 1000 bankroll spent = 90% exposure
    ]
    bankroll = 1000

    light = KellyCalculator.portfolio_kelly(positions_light, bankroll)
    heavy = KellyCalculator.portfolio_kelly(positions_heavy, bankroll)

    assert heavy["effective_kelly_cap"] < light["effective_kelly_cap"]
    assert heavy["portfolio_exposure"] > light["portfolio_exposure"]


def test_remaining_budget_allocation_sums_to_budget():
    """Total allocated should not exceed remaining bankroll."""
    remaining = 500
    golfers = [
        {
            "golfer_id": "g1",
            "win_prob": 0.10,
            "expected_payout": 600,
            "estimated_market_price": 200,
        },
        {
            "golfer_id": "g2",
            "win_prob": 0.05,
            "expected_payout": 300,
            "estimated_market_price": 100,
        },
        {
            "golfer_id": "g3",
            "win_prob": 0.02,
            "expected_payout": 100,
            "estimated_market_price": 50,
        },
    ]
    result = KellyCalculator.remaining_budget_allocation(
        remaining_bankroll=remaining,
        remaining_golfers=golfers,
        portfolio=[],
    )
    assert result["total_allocated"] <= remaining + 0.01
