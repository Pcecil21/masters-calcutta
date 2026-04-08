"""Strategy recommendation endpoints.

Provides real-time bid recommendations based on model probabilities,
remaining bankroll, auction phase, and portfolio composition.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.data.loaders import get_store
from app.schemas import (
    AuctionState,
    Golfer,
    PriceCheckRequest,
    PriceCheckResponse,
    QuickSheetEntry,
    StrategyRecommendation,
)
from app.strategy.ev_calculator import EVCalculator
from app.strategy.kelly import KellyCalculator

router = APIRouter(prefix="/strategy", tags=["strategy"])


def _compute_max_bid(
    golfer: Golfer,
    config: dict,
    state: AuctionState,
    portfolio_count: int,
) -> float:
    """Compute the maximum recommended bid for a golfer.

    In a Calcutta, unspent bankroll is wasted — you MUST deploy capital.
    The primary signal is breakeven EV (the price where EV = 0).  Kelly
    acts as a secondary guardrail to avoid over-concentrating.

    Factors:
    - Breakeven price from EV model (what the golfer is actually worth)
    - Kelly-criterion bankroll sizing (prevents ruin on any single golfer)
    - Auction phase (bid aggressively early for elite, conserve late)
    - Portfolio diversification needs
    - Budget pacing (don't blow bankroll too early)
    """
    ev_calc = get_store().get("ev_calculator") or EVCalculator()
    golfer_probs = {
        "win_prob": golfer.model_win_prob,
        "top5_prob": golfer.model_top5_prob,
        "top10_prob": golfer.model_top10_prob,
    }
    total_pool = config.get("total_pool", 0.0)

    result = ev_calc.calculate_ev(golfer_probs, 1.0, total_pool)
    ev = result["expected_payout"]
    remaining = state.remaining_bankroll
    unsold_count = len(state.golfers_remaining)

    if remaining <= 0 or ev <= 0:
        return 0.0

    # PRIMARY: breakeven price (where EV = 0) with a margin of safety.
    # Recommend bidding up to 85% of breakeven — leaves 15% expected edge.
    breakeven = ev_calc.breakeven_price(golfer_probs, total_pool)
    base_max = breakeven * 0.85

    # Phase adjustment
    phase = state.current_phase
    if phase in ("pre_auction", "early") and golfer.model_win_prob > 0.08:
        base_max *= 1.15  # pay premium for elite early — they're worth fighting for
    elif phase == "late":
        base_max *= 0.90  # slightly more conservative late

    # Diversification: if we already have 5+ golfers, reduce max bids
    if portfolio_count >= 5:
        base_max *= 0.85

    # Reserve floor: keep minimum to stay in the game
    min_reserve = max(0, (unsold_count - 1) * 2.0)
    available_for_bid = max(0, remaining - min_reserve)

    return round(min(base_max, available_for_bid), 2)


def _classify_alert_level(ev: float, max_bid: float, golfer: Golfer) -> str:
    """Classify a golfer into an alert level based on EV multiple."""
    if ev <= 0:
        return "avoid"

    # Estimate market price from consensus probability
    store = get_store()
    config = store["config"]
    pool = config.get("total_pool", 0.0)
    estimated_price = golfer.consensus_win_prob * pool * 0.8 if pool > 0 else 0

    ev_multiple = ev / estimated_price if estimated_price > 0 else 0

    if ev_multiple >= 2.0:
        return "must_bid"
    if ev_multiple >= 1.5:
        return "good_value"
    if ev_multiple >= 1.0:
        return "fair"
    if ev_multiple >= 0.5:
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


def _get_ev_for_golfer(golfer: Golfer, config: dict) -> float:
    """Get expected payout for a golfer using the shared EVCalculator."""
    ev_calc = get_store().get("ev_calculator") or EVCalculator()
    result = ev_calc.calculate_ev(
        {
            "win_prob": golfer.model_win_prob,
            "top5_prob": golfer.model_top5_prob,
            "top10_prob": golfer.model_top10_prob,
        },
        1.0,  # dummy price
        config.get("total_pool", 0.0),
    )
    return result["expected_payout"]


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

        ev = _get_ev_for_golfer(golfer, config)
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


@router.post("/price-check", response_model=PriceCheckResponse)
async def price_check(req: PriceCheckRequest) -> PriceCheckResponse:
    """Real-time price check for a golfer during a live auction.

    Given the auctioneer's current ask price, instantly evaluate whether
    the user should bid or pass based on model EV and Kelly sizing.
    """
    store = get_store()
    golfer = store["golfers"].get(req.golfer_id)
    if golfer is None:
        raise HTTPException(status_code=404, detail=f"Golfer {req.golfer_id} not found")

    state: AuctionState = store["auction_state"]
    config = store["config"]
    total_pool = config.get("total_pool", 0.0) or (state.total_pool if state else 0.0)

    ev_calc = store.get("ev_calculator") or EVCalculator()
    golfer_probs = {
        "win_prob": golfer.model_win_prob,
        "top5_prob": golfer.model_top5_prob,
        "top10_prob": golfer.model_top10_prob,
    }

    result = ev_calc.calculate_ev(golfer_probs, req.current_price, total_pool)
    expected_payout = result["expected_payout"]
    ev = result["ev"]
    ev_multiple = result["ev_multiple"]

    # Kelly-based max bid
    portfolio = store["portfolio"]
    portfolio_count = len(portfolio.entries) if portfolio else 0
    max_bid = _compute_max_bid(golfer, config, state, portfolio_count)

    # Verdict logic
    if ev_multiple > 1.0 and req.current_price <= max_bid:
        verdict = "BID"
    elif ev_multiple < 0.8:
        verdict = "PASS"
    else:
        verdict = "MARGINAL"

    # Snappy message
    name_short = golfer.name.split()[-1]  # last name
    if verdict == "BID":
        pct_under = ((expected_payout / req.current_price) - 1) * 100
        message = (
            f"{name_short} at ${req.current_price:.0f} is a steal - "
            f"model says worth ${expected_payout:.0f} ({pct_under:.0f}% upside). BID."
        )
    elif verdict == "PASS":
        pct_over = ((req.current_price / expected_payout) - 1) * 100 if expected_payout > 0 else 100
        message = (
            f"{name_short} at ${req.current_price:.0f} is "
            f"{pct_over:.0f}% overpriced (worth ${expected_payout:.0f}). PASS."
        )
    else:
        message = (
            f"{name_short} at ${req.current_price:.0f} is close to fair value "
            f"(${expected_payout:.0f}). Proceed with caution."
        )

    return PriceCheckResponse(
        golfer_id=req.golfer_id,
        golfer_name=golfer.name,
        current_price=req.current_price,
        expected_payout=round(expected_payout, 2),
        ev=round(ev, 2),
        ev_multiple=round(ev_multiple, 3),
        max_bid=round(max_bid, 2),
        verdict=verdict,
        message=message,
    )


@router.get("/quick-sheet", response_model=list[QuickSheetEntry])
async def quick_sheet() -> list[QuickSheetEntry]:
    """Pre-computed cheat sheet for every remaining golfer.

    Returns golfer_id, name, max_bid, breakeven_price, and alert_level
    sorted by max_bid descending. Print this and bring it to the auction.
    """
    store = get_store()
    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]
    total_pool = config.get("total_pool", 0.0) or (state.total_pool if state else 0.0)
    portfolio = store["portfolio"]
    portfolio_count = len(portfolio.entries) if portfolio else 0

    ev_calc = store.get("ev_calculator") or EVCalculator()
    entries: list[QuickSheetEntry] = []

    for gid in state.golfers_remaining:
        golfer = golfers.get(gid)
        if golfer is None:
            continue

        golfer_probs = {
            "win_prob": golfer.model_win_prob,
            "top5_prob": golfer.model_top5_prob,
            "top10_prob": golfer.model_top10_prob,
        }

        breakeven = ev_calc.breakeven_price(golfer_probs, total_pool)
        ev = _get_ev_for_golfer(golfer, config)
        max_bid = _compute_max_bid(golfer, config, state, portfolio_count)
        alert_level = _classify_alert_level(ev, max_bid, golfer)

        entries.append(
            QuickSheetEntry(
                golfer_id=gid,
                name=golfer.name,
                max_bid=round(max_bid, 2),
                breakeven_price=round(breakeven, 2),
                alert_level=alert_level,
            )
        )

    entries.sort(key=lambda e: e.max_bid, reverse=True)
    return entries


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

    ev = _get_ev_for_golfer(golfer, config)
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
        ev = _get_ev_for_golfer(golfer, config)
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
