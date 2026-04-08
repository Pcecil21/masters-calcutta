"""Tests for the auction lifecycle endpoints (the most critical router)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def test_configure_auction(app_client: TestClient):
    """POST /api/auction/configure returns a valid AuctionState."""
    resp = app_client.post(
        "/api/auction/configure",
        json={"total_pool": 5000, "my_bankroll": 800, "num_bidders": 12},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "total_pool" in body
    assert "my_bankroll" in body
    assert "golfers_remaining" in body
    assert "current_phase" in body


def test_configure_sets_pool_and_bankroll(app_client: TestClient):
    """Verify total_pool, my_bankroll, and remaining_bankroll are set correctly."""
    resp = app_client.post(
        "/api/auction/configure",
        json={"total_pool": 6000, "my_bankroll": 1000, "num_bidders": 10},
    )
    body = resp.json()
    assert body["total_pool"] == 6000
    assert body["my_bankroll"] == 1000
    assert body["remaining_bankroll"] == 1000


# ---------------------------------------------------------------------------
# Bidding
# ---------------------------------------------------------------------------


def test_bid_requires_configuration(app_client: TestClient, sample_golfer_id: str):
    """POST /api/auction/bid before configure returns 400."""
    resp = app_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 100},
    )
    # Before configuration bankroll is $0, so this should fail with either
    # a "configure" message or a "bankroll" exceeded message.
    assert resp.status_code == 400


def test_bid_happy_path(configured_client: TestClient, sample_golfer_id: str):
    """Bid on a golfer and verify the BidRecord fields."""
    resp = configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 200},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["golfer_id"] == sample_golfer_id
    assert body["buyer"] == "me"
    assert body["price"] == 200
    assert "timestamp" in body


def test_bid_updates_state(configured_client: TestClient, sample_golfer_id: str):
    """After a bid the golfer moves from remaining to sold."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "other_guy", "price": 150},
    )
    state = configured_client.get("/api/auction/state").json()
    assert sample_golfer_id in state["golfers_sold"]
    assert sample_golfer_id not in state["golfers_remaining"]


def test_bid_updates_bankroll(configured_client: TestClient, sample_golfer_id: str):
    """Buying as 'me' deducts from remaining_bankroll."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 200},
    )
    state = configured_client.get("/api/auction/state").json()
    assert state["remaining_bankroll"] == pytest.approx(800 - 200, abs=1)


def test_bid_updates_portfolio(configured_client: TestClient, sample_golfer_id: str):
    """Buying as 'me' adds a portfolio entry with expected_value and ev_multiple."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 200},
    )
    portfolio = configured_client.get("/api/portfolio").json()
    assert len(portfolio["entries"]) == 1
    entry = portfolio["entries"][0]
    assert entry["golfer_id"] == sample_golfer_id
    assert entry["purchase_price"] == 200
    assert entry["expected_value"] > 0
    assert entry["ev_multiple"] > 0


def test_bid_other_buyer_no_portfolio(configured_client: TestClient, sample_golfer_id: str):
    """Buying as another person does NOT add to my portfolio."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "Dave", "price": 300},
    )
    portfolio = configured_client.get("/api/portfolio").json()
    assert len(portfolio["entries"]) == 0


def test_bid_nonexistent_golfer(configured_client: TestClient):
    """Bidding on a golfer that doesn't exist returns 404."""
    resp = configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": "golfer_999", "buyer": "me", "price": 50},
    )
    assert resp.status_code == 404


def test_bid_already_sold(configured_client: TestClient, sample_golfer_id: str):
    """Bidding on an already-sold golfer returns 400."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 100},
    )
    resp = configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "other", "price": 200},
    )
    assert resp.status_code == 400
    assert "already sold" in resp.json()["detail"].lower()


def test_bid_exceeds_bankroll(configured_client: TestClient, sample_golfer_id: str):
    """Bidding more than remaining bankroll (as 'me') returns 400."""
    resp = configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 900},
    )
    assert resp.status_code == 400
    assert "bankroll" in resp.json()["detail"].lower()


def test_bid_updates_total_pool(configured_client: TestClient, store: dict):
    """total_pool equals the sum of all bids after recording them."""
    ids = list(store["golfers"].keys())
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "me", "price": 100},
    )
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[1], "buyer": "Dave", "price": 250},
    )
    state = configured_client.get("/api/auction/state").json()
    assert state["total_pool"] == pytest.approx(350, abs=1)


# ---------------------------------------------------------------------------
# Undo
# ---------------------------------------------------------------------------


def test_undo_reverses_bid(configured_client: TestClient, sample_golfer_id: str):
    """Undo puts the golfer back in remaining and restores bankroll."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 200},
    )
    state_after_undo = configured_client.post("/api/auction/undo").json()
    assert sample_golfer_id in state_after_undo["golfers_remaining"]
    assert sample_golfer_id not in state_after_undo["golfers_sold"]
    assert state_after_undo["remaining_bankroll"] == pytest.approx(800, abs=1)


def test_undo_empty_history(configured_client: TestClient):
    """Undo with no bids returns 400."""
    resp = configured_client.post("/api/auction/undo")
    assert resp.status_code == 400
    assert "No bids" in resp.json()["detail"]


def test_undo_recalculates_risk_score(configured_client: TestClient, store: dict):
    """After undo, portfolio risk_score is recalculated (not stale)."""
    ids = list(store["golfers"].keys())
    # Buy two golfers
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[0], "buyer": "me", "price": 100},
    )
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": ids[1], "buyer": "me", "price": 100},
    )
    p_before = configured_client.get("/api/portfolio").json()
    risk_two = p_before["risk_score"]

    # Undo last -- now only one golfer remains
    configured_client.post("/api/auction/undo")
    p_after = configured_client.get("/api/portfolio").json()
    risk_one = p_after["risk_score"]

    # With one golfer, risk (HHI concentration) should be 100 (single holding)
    assert risk_one == pytest.approx(100.0, abs=1)
    # With two golfers, risk should be lower than single-holder
    assert risk_two < 100.0


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


def test_reset_clears_everything(configured_client: TestClient, sample_golfer_id: str):
    """POST /api/auction/reset brings all state back to initial."""
    configured_client.post(
        "/api/auction/bid",
        json={"golfer_id": sample_golfer_id, "buyer": "me", "price": 200},
    )
    state = configured_client.post("/api/auction/reset").json()
    assert len(state["golfers_sold"]) == 0
    assert state["current_phase"] == "pre_auction"
    portfolio = configured_client.get("/api/portfolio").json()
    assert len(portfolio["entries"]) == 0


# ---------------------------------------------------------------------------
# Phase transitions
# ---------------------------------------------------------------------------


def test_auction_phase_transitions(configured_client: TestClient, store: dict):
    """Bid enough golfers to move through early -> middle -> late."""
    ids = list(store["golfers"].keys())
    total = len(ids)

    # _compute_phase: early < 35%, middle 35-70%, late >= 70%
    # Sell enough to cross the 35% threshold into middle
    cutoff_middle = int(total * 0.35) + 1
    for gid in ids[:cutoff_middle]:
        configured_client.post(
            "/api/auction/bid",
            json={"golfer_id": gid, "buyer": "Dave", "price": 10},
        )
    state = configured_client.get("/api/auction/state").json()
    assert state["current_phase"] == "middle", (
        f"Expected 'middle' after selling {cutoff_middle}/{total} golfers, "
        f"got '{state['current_phase']}'"
    )

    # Sell up to 70%+ to enter late phase
    cutoff_late = int(total * 0.70) + 1
    for gid in ids[cutoff_middle:cutoff_late]:
        configured_client.post(
            "/api/auction/bid",
            json={"golfer_id": gid, "buyer": "Dave", "price": 10},
        )
    state = configured_client.get("/api/auction/state").json()
    assert state["current_phase"] == "late", (
        f"Expected 'late' after selling {cutoff_late}/{total} golfers, "
        f"got '{state['current_phase']}'"
    )
