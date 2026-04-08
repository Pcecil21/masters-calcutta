"""Post-auction scorecard: score your portfolio against actual tournament results.

Accepts final tournament standings, matches them to your purchased golfers,
and computes payouts, ROI, model accuracy (Brier score), and optimal
hindsight analysis.
"""

from __future__ import annotations

from difflib import SequenceMatcher
from typing import Optional

from fastapi import APIRouter, HTTPException

from app.data.loaders import get_store
from app.schemas import (
    ScorecardRequest,
    ScorecardResponse,
    TournamentResult,
)

router = APIRouter(prefix="/scorecard", tags=["scorecard"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fuzzy_match(name: str, candidates: dict[str, str], threshold: float = 0.6) -> Optional[str]:
    """Return the golfer_id whose name best matches *name*, or None.

    Args:
        name: The golfer name from the tournament results.
        candidates: Mapping of golfer_id -> golfer_name.
        threshold: Minimum similarity ratio to accept a match.

    Returns:
        The best-matching golfer_id, or None if no match exceeds threshold.
    """
    best_id: Optional[str] = None
    best_ratio = 0.0
    name_lower = name.lower().strip()

    for gid, gname in candidates.items():
        ratio = SequenceMatcher(None, name_lower, gname.lower().strip()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_id = gid
    return best_id if best_ratio >= threshold else None


def _payout_for_position(position: int, payout_structure: dict, total_pool: float) -> float:
    """Calculate dollar payout for a given finish position.

    Args:
        position: Finish position (1-based). 99 = missed cut.
        payout_structure: Mapping of position label -> pool percentage.
        total_pool: Total auction pool in dollars.

    Returns:
        Dollar payout (0.0 if position is outside the payout structure).
    """
    if position == 99:
        return 0.0

    # Map position int to label (e.g., 1 -> "1st", 2 -> "2nd", etc.)
    suffixes = {1: "st", 2: "nd", 3: "rd"}
    suffix = suffixes.get(position, "th")
    label = f"{position}{suffix}"

    pct = payout_structure.get(label, 0.0)
    return round(total_pool * pct, 2)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/calculate", response_model=ScorecardResponse)
async def calculate_scorecard(req: ScorecardRequest) -> ScorecardResponse:
    """Score the portfolio against actual tournament results.

    1. Fuzzy-match submitted results to golfers in the store.
    2. For each golfer in the portfolio, compute payout from actual finish.
    3. Aggregate totals, find best/worst picks.
    4. Compute Brier score for model accuracy.
    5. Compute optimal hindsight portfolio.
    """
    store = get_store()
    golfers = store["golfers"]
    portfolio = store["portfolio"]
    config = store["config"]
    bid_history = store["bid_history"]
    state = store["auction_state"]

    if not portfolio or not portfolio.entries:
        raise HTTPException(status_code=400, detail="No portfolio entries to score.")

    if not req.results:
        raise HTTPException(status_code=400, detail="No tournament results provided.")

    total_pool = state.total_pool if state.total_pool > 0 else config.get("total_pool", 0)
    payout_structure = config.get("payout_structure", {})

    # Build golfer_id -> name mapping for fuzzy matching
    id_to_name = {gid: g.name for gid, g in golfers.items()}

    # Match results to golfer IDs
    result_by_golfer_id: dict[str, TournamentResult] = {}
    for result in req.results:
        matched_id = _fuzzy_match(result.golfer_name, id_to_name)
        if matched_id:
            result_by_golfer_id[matched_id] = result

    # Score each portfolio entry
    my_golfers = []
    total_invested = 0.0
    total_payout = 0.0

    for entry in portfolio.entries:
        golfer = golfers.get(entry.golfer_id)
        golfer_name = golfer.name if golfer else entry.golfer_id

        result = result_by_golfer_id.get(entry.golfer_id)
        finish_position = result.finish_position if result else 99
        payout = _payout_for_position(finish_position, payout_structure, total_pool)
        profit = payout - entry.purchase_price

        my_golfers.append({
            "golfer_name": golfer_name,
            "golfer_id": entry.golfer_id,
            "purchase_price": entry.purchase_price,
            "finish_position": finish_position,
            "payout": payout,
            "profit": round(profit, 2),
        })

        total_invested += entry.purchase_price
        total_payout += payout

    net_profit = total_payout - total_invested
    roi_pct = (net_profit / total_invested * 100) if total_invested > 0 else 0.0

    # Best and worst picks
    if my_golfers:
        best = max(my_golfers, key=lambda g: g["profit"])
        worst = min(my_golfers, key=lambda g: g["profit"])
        best_pick = {"name": best["golfer_name"], "profit": best["profit"]}
        worst_pick = {"name": worst["golfer_name"], "profit": worst["profit"]}
    else:
        best_pick = {}
        worst_pick = {}

    # -----------------------------------------------------------------------
    # Model accuracy: Brier score
    # -----------------------------------------------------------------------
    # For each golfer with a result, compute:
    #   (model_win_prob - actual_win)^2
    # Brier score = mean of squared errors (lower is better).
    brier_samples = []
    for gid, golfer in golfers.items():
        result = result_by_golfer_id.get(gid)
        if result is None:
            continue
        actual_win = 1.0 if result.finish_position == 1 else 0.0
        error_sq = (golfer.model_win_prob - actual_win) ** 2
        brier_samples.append(error_sq)

    brier_score = sum(brier_samples) / len(brier_samples) if brier_samples else None

    model_accuracy = {
        "brier_score": round(brier_score, 6) if brier_score is not None else None,
        "golfers_scored": len(brier_samples),
        "interpretation": (
            "Lower is better. 0.0 = perfect, 0.25 = coin-flip baseline."
            if brier_score is not None
            else "No results matched to compute accuracy."
        ),
    }

    # -----------------------------------------------------------------------
    # Optimal hindsight: best portfolio with perfect info within bankroll
    # -----------------------------------------------------------------------
    # From all bids recorded (by anyone), find the purchases that would have
    # maximized payout within the user's bankroll.
    bankroll = config.get("my_bankroll", 0)

    # Build a list of (golfer_id, price_paid, payout) for all bids
    all_purchases = []
    for bid in bid_history:
        result = result_by_golfer_id.get(bid.golfer_id)
        if result is None:
            continue
        payout = _payout_for_position(result.finish_position, payout_structure, total_pool)
        all_purchases.append({
            "golfer_id": bid.golfer_id,
            "name": id_to_name.get(bid.golfer_id, bid.golfer_id),
            "price": bid.price,
            "payout": payout,
            "profit": round(payout - bid.price, 2),
        })

    # Greedy knapsack: sort by profit descending, fill bankroll
    all_purchases.sort(key=lambda p: p["profit"], reverse=True)
    optimal_picks = []
    remaining_budget = bankroll
    for p in all_purchases:
        if p["price"] <= remaining_budget:
            optimal_picks.append(p)
            remaining_budget -= p["price"]

    optimal_invested = sum(p["price"] for p in optimal_picks)
    optimal_payout = sum(p["payout"] for p in optimal_picks)
    optimal_profit = optimal_payout - optimal_invested

    optimal_hindsight = {
        "bankroll": bankroll,
        "optimal_picks": optimal_picks,
        "total_invested": round(optimal_invested, 2),
        "total_payout": round(optimal_payout, 2),
        "net_profit": round(optimal_profit, 2),
        "roi_pct": round(optimal_profit / optimal_invested * 100, 2) if optimal_invested > 0 else 0.0,
    }

    return ScorecardResponse(
        my_golfers=my_golfers,
        total_invested=round(total_invested, 2),
        total_payout=round(total_payout, 2),
        net_profit=round(net_profit, 2),
        roi_pct=round(roi_pct, 2),
        best_pick=best_pick,
        worst_pick=worst_pick,
        model_accuracy=model_accuracy,
        optimal_hindsight=optimal_hindsight,
    )
