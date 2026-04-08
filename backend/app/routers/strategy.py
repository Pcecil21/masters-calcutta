"""Strategy recommendation endpoints.

Provides real-time bid recommendations based on model probabilities,
remaining bankroll, auction phase, and portfolio composition.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data.loaders import get_store
from app.schemas import AuctionState, Golfer, StrategyRecommendation

router = APIRouter(prefix="/strategy", tags=["strategy"])


def _compute_golfer_ev(golfer: Golfer, config: dict) -> float:
    """Compute dollar EV for a golfer given payout structure."""
    pool = config.get("total_pool", 0.0)
    ps = config.get("payout_structure", {})
    if pool <= 0:
        return 0.0

    ev = 0.0
    ev += golfer.model_win_prob * pool * ps.get("1st", 0.50)
    p_2nd = max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.3)
    ev += p_2nd * pool * ps.get("2nd", 0.20)
    p_3rd = max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.25)
    ev += p_3rd * pool * ps.get("3rd", 0.10)
    p_top5_rest = max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.45)
    ev += p_top5_rest * pool * ps.get("top5", 0.05)
    p_top10_rest = max(0, golfer.model_top10_prob - golfer.model_top5_prob)
    ev += p_top10_rest * pool * ps.get("top10", 0.03)
    p_cut_rest = max(0, golfer.model_cut_prob - golfer.model_top10_prob)
    ev += p_cut_rest * pool * ps.get("made_cut", 0.01)

    return round(ev, 2)


def _compute_max_bid(
    golfer: Golfer,
    config: dict,
    state: AuctionState,
    portfolio_count: int,
) -> float:
    """Compute the maximum recommended bid for a golfer.

    Factors:
    - Dollar EV from payout structure
    - Remaining bankroll constraints
    - Auction phase (bid more aggressively early for top golfers)
    - Portfolio diversification needs
    """
    ev = _compute_golfer_ev(golfer, config)
    remaining = state.remaining_bankroll
    unsold_count = len(state.golfers_remaining)

    if remaining <= 0 or ev <= 0:
        return 0.0

    # Base max bid: 85% of EV (never pay full EV)
    base_max = ev * 0.85

    # Phase adjustment: in early rounds, allow slightly higher bids for elite golfers
    phase = state.current_phase
    if phase == "early" and golfer.model_win_prob > 0.08:
        base_max *= 1.15  # willing to pay slight premium for elite early
    elif phase == "late":
        base_max *= 0.90  # more conservative late

    # Bankroll constraint: never bid more than 40% of remaining bankroll
    # unless this is genuinely elite (top 3 model probability)
    bankroll_cap = remaining * 0.40
    if golfer.model_win_prob > 0.12:
        bankroll_cap = remaining * 0.55  # allow bigger allocation for elite

    # Diversification: if we already have 5+ golfers, reduce max bids
    if portfolio_count >= 5:
        base_max *= 0.85

    # Reserve floor: always keep enough to buy at least a few more golfers
    min_reserve = max(0, (unsold_count - 1) * 2.0)  # $2 minimum per remaining
    available_for_bid = max(0, remaining - min_reserve)

    return round(min(base_max, bankroll_cap, available_for_bid), 2)


def _classify_alert_level(ev: float, max_bid: float, golfer: Golfer) -> str:
    """Classify a golfer into an alert level."""
    if ev <= 0:
        return "avoid"
    if golfer.anti_consensus_score > 0.03 and golfer.model_win_prob > 0.05:
        return "must_bid"
    if golfer.anti_consensus_score > 0.01:
        return "good_value"
    if golfer.anti_consensus_score > -0.01:
        return "fair"
    if golfer.anti_consensus_score > -0.03:
        return "overpriced"
    return "avoid"


def _build_reasoning(golfer: Golfer, ev: float, config: dict) -> str:
    """Generate human-readable reasoning for a recommendation."""
    pool = config.get("total_pool", 0)
    parts = []

    if golfer.anti_consensus_score > 0.02:
        parts.append(
            f"Model sees {golfer.anti_consensus_score * 100:.1f}% MORE win probability "
            f"than consensus -- undervalued by the market"
        )
    elif golfer.anti_consensus_score < -0.02:
        parts.append(
            f"Model sees {abs(golfer.anti_consensus_score) * 100:.1f}% LESS win probability "
            f"than consensus -- overvalued by the market"
        )

    if golfer.augusta_history_score > 75:
        parts.append(f"Strong Augusta history (score: {golfer.augusta_history_score}/100)")
    if golfer.recent_form_score > 80:
        parts.append(f"Excellent recent form (score: {golfer.recent_form_score}/100)")

    if ev > 0 and pool > 0:
        parts.append(f"Expected value: ${ev:.2f} ({ev / pool * 100:.1f}% of pool)")

    if golfer.masters_wins > 0:
        parts.append(f"Past champion ({golfer.masters_wins} win{'s' if golfer.masters_wins > 1 else ''})")

    return ". ".join(parts) if parts else "Standard recommendation based on model probabilities."


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/recommendations", response_model=list[StrategyRecommendation])
async def get_recommendations() -> list[StrategyRecommendation]:
    """Get strategy recommendations for all remaining unsold golfers.

    Recommendations are sorted by alert level priority (must_bid first)
    then by EV descending.
    """
    store = get_store()
    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]
    portfolio = store["portfolio"]
    portfolio_count = len(portfolio.entries) if portfolio else 0

    alert_order = {"must_bid": 0, "good_value": 1, "fair": 2, "overpriced": 3, "avoid": 4}
    recs: list[StrategyRecommendation] = []

    for gid in state.golfers_remaining:
        golfer = golfers.get(gid)
        if golfer is None:
            continue

        ev = _compute_golfer_ev(golfer, config)
        max_bid = _compute_max_bid(golfer, config, state, portfolio_count)
        alert_level = _classify_alert_level(ev, max_bid, golfer)
        reasoning = _build_reasoning(golfer, ev, config)

        # Confidence: higher when model strongly disagrees with consensus
        confidence = min(1.0, 0.5 + abs(golfer.anti_consensus_score) * 10)

        recs.append(
            StrategyRecommendation(
                golfer_id=gid,
                max_bid=max_bid,
                confidence=round(confidence, 3),
                reasoning=reasoning,
                alert_level=alert_level,
            )
        )

    recs.sort(key=lambda r: (alert_order.get(r.alert_level, 99), -r.max_bid))
    return recs


@router.get("/{golfer_id}/max-bid", response_model=StrategyRecommendation)
async def get_max_bid(golfer_id: str) -> StrategyRecommendation:
    """Get the maximum recommended bid for a specific golfer."""
    store = get_store()
    golfer = store["golfers"].get(golfer_id)
    if golfer is None:
        raise HTTPException(status_code=404, detail=f"Golfer {golfer_id} not found")

    state: AuctionState = store["auction_state"]
    config = store["config"]
    portfolio = store["portfolio"]
    portfolio_count = len(portfolio.entries) if portfolio else 0

    ev = _compute_golfer_ev(golfer, config)
    max_bid = _compute_max_bid(golfer, config, state, portfolio_count)
    alert_level = _classify_alert_level(ev, max_bid, golfer)
    reasoning = _build_reasoning(golfer, ev, config)
    confidence = min(1.0, 0.5 + abs(golfer.anti_consensus_score) * 10)

    return StrategyRecommendation(
        golfer_id=golfer_id,
        max_bid=max_bid,
        confidence=round(confidence, 3),
        reasoning=reasoning,
        alert_level=alert_level,
    )


@router.get("/anti-consensus", response_model=list[StrategyRecommendation])
async def anti_consensus() -> list[StrategyRecommendation]:
    """Golfers where our model diverges most from betting consensus.

    Returns only remaining (unsold) golfers, sorted by anti_consensus_score
    descending. Positive = model sees more upside than market.
    """
    store = get_store()
    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]
    portfolio = store["portfolio"]
    portfolio_count = len(portfolio.entries) if portfolio else 0

    remaining_golfers = [
        golfers[gid] for gid in state.golfers_remaining if gid in golfers
    ]
    remaining_golfers.sort(key=lambda g: g.anti_consensus_score, reverse=True)

    recs: list[StrategyRecommendation] = []
    for golfer in remaining_golfers:
        ev = _compute_golfer_ev(golfer, config)
        max_bid = _compute_max_bid(golfer, config, state, portfolio_count)
        alert_level = _classify_alert_level(ev, max_bid, golfer)
        reasoning = _build_reasoning(golfer, ev, config)
        confidence = min(1.0, 0.5 + abs(golfer.anti_consensus_score) * 10)

        recs.append(
            StrategyRecommendation(
                golfer_id=golfer.id,
                max_bid=max_bid,
                confidence=round(confidence, 3),
                reasoning=reasoning,
                alert_level=alert_level,
            )
        )

    return recs
