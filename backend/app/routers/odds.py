"""Odds refresh endpoint -- pulls live betting odds and updates consensus probabilities.

POST /api/odds/refresh
  - Fetches live Masters outright winner odds from The Odds API
  - Fuzzy-matches golfer names to the in-memory store
  - Updates consensus_win_prob and anti_consensus_score for each matched golfer
  - Invalidates alert cache
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.data.loaders import get_store
from app.data.scrapers.betting_odds import get_consensus_odds
from app.schemas import Golfer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/odds", tags=["odds"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class OddsRefreshRequest(BaseModel):
    api_key: Optional[str] = None


class OddsRefreshResponse(BaseModel):
    updated: int
    unmatched: list[str]
    source: str = "the-odds-api"


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------


def fuzzy_match_golfer(api_name: str, golfers: dict[str, Golfer]) -> str | None:
    """Match an API golfer name to an existing golfer_id in the store.

    Strategy (in order of preference):
    1. Exact match on golfer.name
    2. Last-name match (last token of both names)
    3. Case-insensitive substring containment (either direction)

    Returns the golfer_id or None if no match found.
    """
    api_lower = api_name.strip().lower()
    api_last = api_lower.split()[-1] if api_lower else ""

    # Pass 1: exact match
    for gid, g in golfers.items():
        if g.name.strip().lower() == api_lower:
            return gid

    # Pass 2: last-name match (only if unique)
    last_name_matches: list[str] = []
    for gid, g in golfers.items():
        store_last = g.name.strip().lower().split()[-1]
        # Also handle "Last, First" format
        store_last_comma = g.name.strip().lower().split(",")[0].strip()
        if api_last and (store_last == api_last or store_last_comma == api_last):
            last_name_matches.append(gid)
    if len(last_name_matches) == 1:
        return last_name_matches[0]

    # Pass 3: case-insensitive substring
    for gid, g in golfers.items():
        store_lower = g.name.strip().lower()
        if api_lower in store_lower or store_lower in api_lower:
            return gid

    return None


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=OddsRefreshResponse)
async def refresh_odds(body: OddsRefreshRequest | None = None) -> OddsRefreshResponse:
    """Pull live odds from The Odds API and update consensus probabilities.

    The API key can be passed in the request body or read from the
    ODDS_API_KEY environment variable.
    """
    api_key = (body.api_key if body else None) or None
    consensus = await get_consensus_odds(api_key=api_key)

    if not consensus:
        logger.warning("refresh_odds: no consensus data returned (check API key / connectivity)")
        return OddsRefreshResponse(updated=0, unmatched=[])

    store = get_store()
    golfers: dict[str, Golfer] = store["golfers"]

    updated = 0
    unmatched: list[str] = []

    for api_name, win_prob in consensus.items():
        gid = fuzzy_match_golfer(api_name, golfers)
        if gid is None:
            unmatched.append(api_name)
            continue

        golfer = golfers[gid]
        golfer.consensus_win_prob = round(win_prob, 6)
        golfer.anti_consensus_score = round(
            golfer.model_win_prob - golfer.consensus_win_prob, 6
        )
        updated += 1

    # Invalidate alert cache so downstream consumers see fresh data
    store["alert_cache"] = None

    logger.info(
        "refresh_odds complete: %d updated, %d unmatched", updated, len(unmatched)
    )
    return OddsRefreshResponse(updated=updated, unmatched=unmatched)
