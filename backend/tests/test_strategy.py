"""Tests for the strategy recommendation endpoints."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_recommendations_return_for_remaining(configured_client: TestClient, store: dict):
    """Recommendations should only include unsold golfers."""
    ids = list(store["golfers"].keys())
    # Sell the first golfer
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "Dave", "price": 200},
    )
    resp = configured_client.get("/api/strategy/recommendations")
    assert resp.status_code == 200
    recs = resp.json()
    rec_ids = {r["golfer_id"] for r in recs}
    assert ids[0] not in rec_ids, "Sold golfer should not appear in recommendations"
    # All remaining golfers should have a recommendation
    assert len(recs) == len(ids) - 1


def test_recommendations_sorted_by_alert_then_ev(configured_client: TestClient):
    """Recommendations should be sorted by alert_level priority, then max_bid desc."""
    resp = configured_client.get("/api/strategy/recommendations")
    recs = resp.json()
    alert_order = {"must_bid": 0, "good_value": 1, "fair": 2, "overpriced": 3, "avoid": 4}
    # Check the list is sorted by (alert_priority, -max_bid)
    for i in range(len(recs) - 1):
        a = recs[i]
        b = recs[i + 1]
        a_pri = alert_order.get(a["alert_level"], 99)
        b_pri = alert_order.get(b["alert_level"], 99)
        if a_pri == b_pri:
            assert a["max_bid"] >= b["max_bid"], (
                f"Within same alert level, max_bid should be descending: "
                f"{a['max_bid']} < {b['max_bid']}"
            )
        else:
            assert a_pri <= b_pri


def test_anti_consensus_sorted_by_divergence(configured_client: TestClient, store: dict):
    """Anti-consensus endpoint should return golfers sorted by anti_consensus_score desc."""
    resp = configured_client.get("/api/strategy/anti-consensus")
    assert resp.status_code == 200
    recs = resp.json()
    # The route sorts by the Golfer.anti_consensus_score field on the model.
    # Verify the corresponding golfer objects are in descending order.
    golfers = store["golfers"]
    scores = []
    for r in recs:
        golfer = golfers.get(r["golfer_id"])
        if golfer:
            scores.append(golfer.anti_consensus_score)
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], "anti_consensus should be sorted descending"


def test_max_bid_endpoint(configured_client: TestClient, sample_golfer_id: str):
    """GET /api/strategy/{golfer_id}/max-bid returns a valid StrategyRecommendation."""
    resp = configured_client.get(f"/api/strategy/{sample_golfer_id}/max-bid")
    assert resp.status_code == 200
    body = resp.json()
    assert body["golfer_id"] == sample_golfer_id
    assert body["max_bid"] >= 0
    assert 0 <= body["confidence"] <= 1.0
    assert body["alert_level"] in {"must_bid", "good_value", "fair", "overpriced", "avoid"}
    assert len(body["reasoning"]) > 0
