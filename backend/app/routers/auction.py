"""Auction state management endpoints.

This is the most critical router -- it tracks every bid, recalculates
remaining bankroll, determines auction phase, and generates real-time
alerts when a must-bid golfer is about to go for less than model value.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.data.loaders import get_store, reset_auction as _reset_auction
from app.schemas import (
    Alert,
    AuctionConfig,
    AuctionState,
    BidRecord,
    BidRequest,
    Golfer,
)

router = APIRouter(prefix="/auction", tags=["auction"])


def _compute_phase(sold_count: int, total_count: int) -> str:
    """Determine auction phase based on how many golfers have been sold."""
    if sold_count == 0:
        return "pre_auction"
    if sold_count >= total_count:
        return "complete"
    pct = sold_count / total_count
    if pct < 0.35:
        return "early"
    if pct < 0.70:
        return "middle"
    return "late"


def _compute_golfer_ev(golfer: Golfer, config: dict) -> float:
    """Compute dollar expected value for a golfer given the payout structure."""
    pool = config.get("total_pool", 0.0)
    ps = config.get("payout_structure", {})
    if pool <= 0:
        return 0.0

    ev = 0.0
    ev += golfer.model_win_prob * pool * ps.get("1st", 0.50)
    # 2nd place: approximate as top5 prob minus win prob, capped
    p_2nd = max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.3)
    ev += p_2nd * pool * ps.get("2nd", 0.20)
    # 3rd
    p_3rd = max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.25)
    ev += p_3rd * pool * ps.get("3rd", 0.10)
    # top5 (non-podium)
    p_top5_rest = max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.45)
    ev += p_top5_rest * pool * ps.get("top5", 0.05)
    # top10 (non-top5)
    p_top10_rest = max(0, golfer.model_top10_prob - golfer.model_top5_prob)
    ev += p_top10_rest * pool * ps.get("top10", 0.03)
    # made cut (non-top10)
    p_cut_rest = max(0, golfer.model_cut_prob - golfer.model_top10_prob)
    ev += p_cut_rest * pool * ps.get("made_cut", 0.01)

    return round(ev, 2)


def _generate_alerts(store: dict) -> list[Alert]:
    """Generate must-bid alerts for unsold golfers whose EV exceeds typical price."""
    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]
    bid_history: list[BidRecord] = store["bid_history"]

    if config.get("total_pool", 0) <= 0:
        return []

    # Compute average price paid so far to calibrate expectations
    prices = [b.price for b in bid_history]
    avg_price = sum(prices) / len(prices) if prices else 0

    alerts: list[Alert] = []
    for gid in state.golfers_remaining:
        golfer = golfers.get(gid)
        if golfer is None:
            continue
        ev = _compute_golfer_ev(golfer, config)
        if ev <= 0:
            continue

        # Estimate what this golfer "should" go for based on consensus
        est_price = golfer.consensus_win_prob * config["total_pool"] * 0.8
        if est_price <= 0:
            est_price = avg_price * 0.5 if avg_price > 0 else 10.0

        ev_multiple = ev / est_price if est_price > 0 else 0

        if ev_multiple >= 2.0:
            alerts.append(
                Alert(
                    golfer_id=gid,
                    message=f"MUST BID: {golfer.name} has {ev_multiple:.1f}x EV/price ratio",
                    alert_type="must_bid",
                    priority=1,
                    current_price=est_price,
                    recommended_max=round(ev * 0.85, 2),
                )
            )
        elif ev_multiple >= 1.5:
            alerts.append(
                Alert(
                    golfer_id=gid,
                    message=f"VALUE: {golfer.name} has {ev_multiple:.1f}x EV/price ratio",
                    alert_type="value_alert",
                    priority=2,
                    current_price=est_price,
                    recommended_max=round(ev * 0.80, 2),
                )
            )

    # Budget warning
    remaining = state.remaining_bankroll
    unsold = len(state.golfers_remaining)
    if remaining > 0 and unsold > 0 and remaining / unsold < 5:
        alerts.append(
            Alert(
                golfer_id="",
                message=f"BUDGET: Only ${remaining:.0f} left for {unsold} remaining golfers",
                alert_type="budget_warning",
                priority=1,
                current_price=None,
                recommended_max=None,
            )
        )

    alerts.sort(key=lambda a: a.priority)
    return alerts


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/state", response_model=AuctionState)
async def get_auction_state() -> AuctionState:
    """Return the current auction state."""
    return get_store()["auction_state"]


@router.post("/configure", response_model=AuctionState)
async def configure_auction(cfg: AuctionConfig) -> AuctionState:
    """Set total pool size, bankroll, and payout structure before auction starts."""
    store = get_store()
    store["config"]["total_pool"] = cfg.total_pool
    store["config"]["my_bankroll"] = cfg.my_bankroll
    store["config"]["payout_structure"] = cfg.payout_structure

    state: AuctionState = store["auction_state"]
    state.total_pool = cfg.total_pool
    state.my_bankroll = cfg.my_bankroll
    state.remaining_bankroll = cfg.my_bankroll
    return state


@router.post("/bid", response_model=BidRecord)
async def record_bid(bid: BidRequest) -> BidRecord:
    """Record a bid result.  Updates auction state, portfolio, and bankroll."""
    store = get_store()
    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]

    # Validate golfer exists
    golfer = golfers.get(bid.golfer_id)
    if golfer is None:
        raise HTTPException(status_code=404, detail=f"Golfer {bid.golfer_id} not found")

    # Validate golfer not already sold
    if bid.golfer_id in state.golfers_sold:
        raise HTTPException(
            status_code=400,
            detail=f"Golfer {bid.golfer_id} ({golfer.name}) already sold",
        )

    # Validate golfer is in remaining list
    if bid.golfer_id not in state.golfers_remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Golfer {bid.golfer_id} not in remaining pool",
        )

    # If I'm the buyer, validate bankroll
    if bid.buyer.lower() == "me":
        if bid.price > state.remaining_bankroll:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Bid ${bid.price:.2f} exceeds remaining bankroll "
                    f"${state.remaining_bankroll:.2f}"
                ),
            )

    # Create bid record
    record = BidRecord(
        golfer_id=bid.golfer_id,
        buyer=bid.buyer,
        price=bid.price,
        timestamp=datetime.utcnow(),
    )
    store["bid_history"].append(record)

    # Update auction state
    state.golfers_remaining.remove(bid.golfer_id)
    state.golfers_sold.append(bid.golfer_id)
    total_golfers = len(golfers)
    state.current_phase = _compute_phase(len(state.golfers_sold), total_golfers)

    # If I won this golfer, update bankroll and portfolio
    if bid.buyer.lower() == "me":
        state.remaining_bankroll -= bid.price

        # Add to portfolio
        from app.schemas import PortfolioEntry

        ev = _compute_golfer_ev(golfer, config)
        entry = PortfolioEntry(
            golfer_id=bid.golfer_id,
            purchase_price=bid.price,
            model_win_prob=golfer.model_win_prob,
            model_top5_prob=golfer.model_top5_prob,
            expected_value=ev,
            ev_multiple=round(ev / bid.price, 3) if bid.price > 0 else 0.0,
        )
        portfolio = store["portfolio"]
        portfolio.entries.append(entry)

        # Recalculate portfolio totals
        portfolio.total_invested = sum(e.purchase_price for e in portfolio.entries)
        portfolio.total_expected_value = sum(e.expected_value for e in portfolio.entries)
        portfolio.expected_roi = (
            (portfolio.total_expected_value - portfolio.total_invested)
            / portfolio.total_invested
            if portfolio.total_invested > 0
            else 0.0
        )

        # Risk score: concentration-based (HHI on expected value share)
        if len(portfolio.entries) > 0 and portfolio.total_expected_value > 0:
            shares = [
                e.expected_value / portfolio.total_expected_value
                for e in portfolio.entries
            ]
            hhi = sum(s ** 2 for s in shares)
            # HHI of 1.0 (single golfer) = risk 100; HHI of 1/n = risk ~10
            portfolio.risk_score = round(min(100, hhi * 100), 1)
        else:
            portfolio.risk_score = 0.0

    # Track total pool growth (sum of all bids)
    state.total_pool = sum(b.price for b in store["bid_history"])

    return record


@router.post("/undo", response_model=AuctionState)
async def undo_last_bid() -> AuctionState:
    """Undo the most recent bid.  Reverses all state changes."""
    store = get_store()
    bid_history: list[BidRecord] = store["bid_history"]
    state: AuctionState = store["auction_state"]

    if not bid_history:
        raise HTTPException(status_code=400, detail="No bids to undo")

    last_bid = bid_history.pop()

    # Reverse auction state
    if last_bid.golfer_id in state.golfers_sold:
        state.golfers_sold.remove(last_bid.golfer_id)
    state.golfers_remaining.append(last_bid.golfer_id)
    total_golfers = len(store["golfers"])
    state.current_phase = _compute_phase(len(state.golfers_sold), total_golfers)

    # If I was the buyer, reverse bankroll and portfolio
    if last_bid.buyer.lower() == "me":
        state.remaining_bankroll += last_bid.price

        portfolio = store["portfolio"]
        portfolio.entries = [
            e for e in portfolio.entries if e.golfer_id != last_bid.golfer_id
        ]
        # Recalculate
        portfolio.total_invested = sum(e.purchase_price for e in portfolio.entries)
        portfolio.total_expected_value = sum(e.expected_value for e in portfolio.entries)
        portfolio.expected_roi = (
            (portfolio.total_expected_value - portfolio.total_invested)
            / portfolio.total_invested
            if portfolio.total_invested > 0
            else 0.0
        )

    # Recalculate total pool
    state.total_pool = sum(b.price for b in store["bid_history"])

    return state


@router.get("/alerts", response_model=list[Alert])
async def get_alerts() -> list[Alert]:
    """Get current must-bid and value alerts for unsold golfers."""
    return _generate_alerts(get_store())


@router.post("/reset", response_model=AuctionState)
async def reset() -> AuctionState:
    """Reset the entire auction.  Clears all bids and portfolio."""
    _reset_auction()
    return get_store()["auction_state"]
