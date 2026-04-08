"""Tests for the portfolio analysis endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_empty_portfolio(configured_client: TestClient):
    """An empty portfolio should return zero totals."""
    resp = configured_client.get("/api/portfolio")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_invested"] == 0
    assert body["total_expected_value"] == 0
    assert len(body["entries"]) == 0


def test_portfolio_after_bids(configured_client: TestClient, store: dict):
    """Portfolio entries should match golfers purchased as 'me'."""
    ids = list(store["golfers"].keys())
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "me", "price": 200},
    )
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[1], "buyer": "me", "price": 100},
    )
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[2], "buyer": "Dave", "price": 300},
    )
    portfolio = configured_client.get("/api/portfolio").json()
    assert len(portfolio["entries"]) == 2
    assert portfolio["total_invested"] == pytest.approx(300, abs=1)
    entry_ids = {e["golfer_id"] for e in portfolio["entries"]}
    assert ids[0] in entry_ids
    assert ids[1] in entry_ids
    assert ids[2] not in entry_ids


def test_portfolio_optimization_archetypes(configured_client: TestClient, store: dict):
    """Portfolio optimization should return valid diversification analysis."""
    ids = list(store["golfers"].keys())
    # Buy a couple golfers to have a non-empty portfolio
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "me", "price": 200},
    )
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[1], "buyer": "me", "price": 100},
    )
    resp = configured_client.get("/api/portfolio/optimization")
    assert resp.status_code == 200
    body = resp.json()
    assert "diversification_score" in body
    assert 0 <= body["diversification_score"] <= 100
    assert "style_breakdown" in body
    assert "portfolio_summary" in body
    assert body["portfolio_summary"]["total_golfers"] == 2


def test_expected_payout_breakdown(configured_client: TestClient, store: dict):
    """Each golfer projection should include per-tier EV breakdown."""
    ids = list(store["golfers"].keys())
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "me", "price": 200},
    )
    resp = configured_client.get("/api/portfolio/expected-payout")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["golfer_projections"]) == 1
    proj = body["golfer_projections"][0]
    assert "ev_by_tier" in proj
    assert proj["total_ev"] > 0
    # ev_by_tier should have entries for the payout positions
    assert len(proj["ev_by_tier"]) > 0
