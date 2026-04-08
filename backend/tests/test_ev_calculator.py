"""Tests for the Expected Value calculator engine."""

from __future__ import annotations

import pytest

from app.strategy.ev_calculator import EVCalculator


@pytest.fixture()
def ev_calc() -> EVCalculator:
    return EVCalculator()


# Scheffler-level probabilities
SCHEFFLER_PROBS = {
    "win_prob": 0.21,
    "top5_prob": 0.80,
    "top10_prob": 0.90,
}

LONGSHOT_PROBS = {
    "win_prob": 0.003,
    "top5_prob": 0.02,
    "top10_prob": 0.05,
}


def test_ev_positive_for_favorite(ev_calc: EVCalculator):
    """Scheffler at a reasonable price should have positive EV."""
    result = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=500, total_pool=5000)
    assert result["ev"] > 0, "Scheffler at $500 in a $5000 pool should be +EV"


def test_ev_negative_at_high_price(ev_calc: EVCalculator):
    """Buying at 2x expected payout should be negative EV."""
    base = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=0, total_pool=5000)
    overpay = base["expected_payout"] * 2
    result = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=overpay, total_pool=5000)
    assert result["ev"] < 0


def test_ev_zero_pool(ev_calc: EVCalculator):
    """EV is zero when pool is zero because all payouts are pool-based."""
    result = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=0, total_pool=0)
    assert result["expected_payout"] == 0.0


def test_breakeven_price(ev_calc: EVCalculator):
    """Breakeven price should equal the expected payout."""
    breakeven = ev_calc.breakeven_price(SCHEFFLER_PROBS, total_pool=5000)
    payout = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=0, total_pool=5000)["expected_payout"]
    assert breakeven == pytest.approx(payout, rel=0.01)


def test_ev_at_price_points(ev_calc: EVCalculator):
    """ev_at_price_points returns correct count, sorted ascending by price."""
    prices = [100, 300, 200, 500, 400]
    results = ev_calc.ev_at_price_points(SCHEFFLER_PROBS, total_pool=5000, prices=prices)
    assert len(results) == len(prices)
    returned_prices = [r["price"] for r in results]
    assert returned_prices == sorted(returned_prices)


def test_ev_multiple_above_one_is_profitable(ev_calc: EVCalculator):
    """When ev_multiple > 1.0 the EV should be positive."""
    result = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=200, total_pool=5000)
    if result["ev_multiple"] > 1.0:
        assert result["ev"] > 0


def test_risk_adjusted_ev_lower_than_raw(ev_calc: EVCalculator):
    """Risk-adjusted EV should be <= raw EV for risk_aversion > 0."""
    raw = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=300, total_pool=5000)["ev"]
    risk_adj = ev_calc.risk_adjusted_ev(SCHEFFLER_PROBS, price=300, total_pool=5000, risk_aversion=0.5)
    assert risk_adj <= raw + 0.01  # small tolerance for rounding


def test_risk_neutral_equals_raw(ev_calc: EVCalculator):
    """risk_aversion=0 should give the same EV as raw calculation."""
    raw = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=300, total_pool=5000)["ev"]
    risk_adj = ev_calc.risk_adjusted_ev(SCHEFFLER_PROBS, price=300, total_pool=5000, risk_aversion=0.0)
    assert risk_adj == pytest.approx(raw, abs=1.0)


def test_payout_breakdown_sums_to_expected(ev_calc: EVCalculator):
    """Sum of per-position expected dollars should equal total expected payout."""
    result = ev_calc.calculate_ev(SCHEFFLER_PROBS, price=0, total_pool=5000)
    breakdown = result["payout_breakdown"]
    total_from_breakdown = sum(tier["expected_dollars"] for tier in breakdown.values())
    assert total_from_breakdown == pytest.approx(result["expected_payout"], abs=0.1)
