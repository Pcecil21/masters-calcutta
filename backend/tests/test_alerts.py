"""Tests for the auction alerts system."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_alerts_empty_when_no_pool(app_client: TestClient):
    """No alerts should be generated when the pool is 0 (unconfigured)."""
    resp = app_client.get("/api/auction/alerts")
    assert resp.status_code == 200
    assert resp.json() == []


def test_alerts_contain_must_bid(configured_client: TestClient):
    """At least one must_bid or value_alert should exist for a configured pool."""
    resp = configured_client.get("/api/auction/alerts")
    assert resp.status_code == 200
    alerts = resp.json()
    # With a $5000 pool and real golfer data, the engine should flag some value
    alert_types = {a["alert_type"] for a in alerts}
    assert len(alerts) > 0, "Expected at least some alerts for a $5000 pool"
    assert "must_bid" in alert_types or "value_alert" in alert_types


def test_alerts_budget_warning(configured_client: TestClient, store: dict):
    """Budget warning fires when remaining bankroll is very low per remaining golfer."""
    ids = list(store["golfers"].keys())
    # Spend almost all bankroll on one golfer, leaving very little
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "me", "price": 790},
    )
    resp = configured_client.get("/api/auction/alerts")
    alerts = resp.json()
    budget_warnings = [a for a in alerts if a["alert_type"] == "budget_warning"]
    assert len(budget_warnings) >= 1, "Expected a budget_warning when bankroll is nearly exhausted"


def test_alerts_cached(configured_client: TestClient):
    """Second call should return cached results (same content)."""
    first = configured_client.get("/api/auction/alerts").json()
    second = configured_client.get("/api/auction/alerts").json()
    assert first == second


def test_alerts_invalidated_on_bid(configured_client: TestClient, sample_golfer_id: str):
    """Alerts should regenerate after a bid (cache invalidated)."""
    # Prime the cache
    configured_client.get("/api/auction/alerts")

    # Place a bid -- should invalidate cache
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "Dave", "price": 200},
    )

    alerts = configured_client.get("/api/auction/alerts").json()
    # The sold golfer should no longer appear in alerts
    alert_golfer_ids = {a["golfer_id"] for a in alerts}
    assert sample_golfer_id not in alert_golfer_ids
