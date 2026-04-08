"""Tests for seed data integrity."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas import Golfer

SEED_FILE = Path(__file__).resolve().parent.parent / "data" / "seed" / "masters_2026_field.json"


def test_seed_file_exists():
    """The seed data file must exist."""
    assert SEED_FILE.exists(), f"Seed file not found at {SEED_FILE}"


def test_seed_data_valid_pydantic():
    """Every entry in the seed file must validate against the Golfer schema."""
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    errors = []
    for i, entry in enumerate(raw):
        try:
            Golfer(**entry)
        except ValidationError as exc:
            errors.append(f"Entry {i} ({entry.get('name', 'UNKNOWN')}): {exc}")

    assert not errors, f"Seed data validation failures:\n" + "\n".join(errors)


def test_seed_probabilities_sum_reasonable():
    """Win probabilities should sum to roughly 1.0 (0.8-1.3 acceptable pre-normalization)."""
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    total_win_prob = sum(entry.get("model_win_prob", 0) for entry in raw)
    assert 0.8 <= total_win_prob <= 1.5, (
        f"Win probabilities sum to {total_win_prob:.3f}, expected 0.8-1.5"
    )


def test_seed_has_minimum_golfers():
    """The Masters field should have at least 50 golfers."""
    with open(SEED_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    assert len(raw) >= 50, f"Only {len(raw)} golfers in seed data, expected >= 50"
