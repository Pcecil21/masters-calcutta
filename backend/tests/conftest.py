"""Shared fixtures for the Masters Calcutta test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.data.loaders import get_store, load_seed_data
from app.main import app


@pytest.fixture(autouse=True)
def _fresh_store():
    """Reload seed data before every test so tests are fully independent."""
    load_seed_data()
    yield


@pytest.fixture()
def app_client() -> TestClient:
    """Unconfigured FastAPI TestClient -- auction has NOT been configured yet."""
    return TestClient(app)


@pytest.fixture()
def store() -> dict:
    """Return the in-memory store with seed data loaded."""
    return get_store()


@pytest.fixture()
def configured_client(app_client: TestClient) -> TestClient:
    """TestClient that has already called POST /api/auction/configure."""
    resp = app_client.post(
        "/api/auction/configure",
        json={
            "total_pool": 5000,
            "my_bankroll": 800,
            "num_bidders": 12,
        },
    )
    assert resp.status_code == 200
    return app_client


@pytest.fixture()
def sample_golfer_id(store) -> str:
    """Return the first golfer ID from the store."""
    return next(iter(store["golfers"]))
