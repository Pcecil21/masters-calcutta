"""Auction state management endpoints.

This is the most critical router -- it tracks every bid, recalculates
remaining bankroll, determines auction phase, and generates real-time
alerts when a must-bid golfer is about to go for less than model value.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.data.loaders import (
    clear_saved_state,
    get_store,
    reset_auction as _reset_auction,
    save_auction_state,
)
from app.schemas import (
    Alert,
    AuctionConfig,
    AuctionState,
    BidRecord,
    BidRequest,
    Golfer,
    Portfolio,
)
from app.strategy.ev_calculator import EVCalculator

router = APIRouter(prefix="/auction", tags=["auction"])

_auction_lock = asyncio.Lock()


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


def _recalculate_portfolio(portfolio: Portfolio) -> None:
    """Recompute portfolio totals: invested, EV, ROI, and risk (HHI)."""
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
    store["config"]["num_bidders"] = cfg.num_bidders
    store["config"]["payout_structure"] = cfg.payout_structure

    # Rebuild EVCalculator with the new payout structure
    store["ev_calculator"] = EVCalculator(cfg.payout_structure)
    store["alert_cache"] = None

    state: AuctionState = store["auction_state"]
    state.total_pool = cfg.total_pool
    state.my_bankroll = cfg.my_bankroll
    state.remaining_bankroll = cfg.my_bankroll

    save_auction_state()
    return state


@router.post("/bid", response_model=BidRecord)
async def record_bid(bid: BidRequest) -> BidRecord:
    """Record a bid result.  Updates auction state, portfolio, and bankroll."""
    store = get_store()

    async with _auction_lock:
        golfers = store["golfers"]
        state: AuctionState = store["auction_state"]
        config = store["config"]

        # Guard: auction must be configured before recording bids
        if (
            config.get("total_pool", 0) <= 0
            and not store["bid_history"]
            and config.get("estimated_pool", 0) <= 0
        ):
            raise HTTPException(
                status_code=400,
                detail="Configure auction before recording bids",
            )

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
            timestamp=datetime.now(timezone.utc),
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

            # Compute EV using the shared EVCalculator
            ev_calc = store.get("ev_calculator") or EVCalculator()
            ev_result = ev_calc.calculate_ev(
                {
                    "win_prob": golfer.model_win_prob,
                    "top5_prob": golfer.model_top5_prob,
                    "top10_prob": golfer.model_top10_prob,
                },
                bid.price,
                state.total_pool,
            )
            ev = ev_result["expected_payout"]

            from app.schemas import PortfolioEntry

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

            _recalculate_portfolio(portfolio)

        # Track total pool growth (sum of all bids)
        state.total_pool = sum(b.price for b in store["bid_history"])

        # Invalidate alert cache
        store["alert_cache"] = None

        save_auction_state()

    return record


@router.post("/undo", response_model=AuctionState)
async def undo_last_bid() -> AuctionState:
    """Undo the most recent bid.  Reverses all state changes."""
    store = get_store()

    async with _auction_lock:
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
            _recalculate_portfolio(portfolio)

        # Recalculate total pool
        state.total_pool = sum(b.price for b in store["bid_history"])

        # Invalidate alert cache
        store["alert_cache"] = None

        save_auction_state()

    return state


@router.get("/alerts", response_model=list[Alert])
async def get_alerts() -> list[Alert]:
    """Get current must-bid and value alerts for unsold golfers."""
    store = get_store()

    # Return cached alerts if available
    if store["alert_cache"] is not None:
        return store["alert_cache"]

    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]

    if config.get("total_pool", 0) <= 0:
        return []

    ev_calc = store.get("ev_calculator") or EVCalculator()

    alerts: list[Alert] = []
    for gid in state.golfers_remaining:
        golfer = golfers.get(gid)
        if golfer is None:
            continue

        ev_result = ev_calc.calculate_ev(
            {
                "win_prob": golfer.model_win_prob,
                "top5_prob": golfer.model_top5_prob,
                "top10_prob": golfer.model_top10_prob,
            },
            0.0,  # price=0 to get raw expected payout
            state.total_pool,
        )
        ev = ev_result["expected_payout"]
        if ev <= 0:
            continue

        # Estimate market price from consensus
        est_price = golfer.consensus_win_prob * state.total_pool * 0.8
        if est_price <= 0:
            est_price = 10.0

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

    # Cache the result
    store["alert_cache"] = alerts

    return alerts


@router.post("/reset", response_model=AuctionState)
async def reset() -> AuctionState:
    """Reset the entire auction.  Clears all bids and portfolio."""
    async with _auction_lock:
        _reset_auction()
        clear_saved_state()
    return get_store()["auction_state"]


# ---------------------------------------------------------------------------
# Feature 3: Competitor Scouting
# ---------------------------------------------------------------------------


@router.get("/competitors")
async def get_competitors():
    """Analyze bid history by buyer to scout competitor strategies."""
    store = get_store()
    bid_history: list[BidRecord] = store["bid_history"]
    golfers = store["golfers"]

    # Group bids by buyer (excluding "me")
    buyer_bids: dict[str, list[BidRecord]] = {}
    for bid in bid_history:
        if bid.buyer.lower() == "me":
            continue
        buyer_bids.setdefault(bid.buyer, []).append(bid)

    if not buyer_bids:
        return {"competitors": [], "summary": "No competitor bids recorded yet."}

    # Compute total spent across all competitors for quartile calculation
    all_totals = [sum(b.price for b in bids) for bids in buyer_bids.values()]
    all_totals_sorted = sorted(all_totals)
    q75_idx = int(len(all_totals_sorted) * 0.75)
    top_quartile_threshold = all_totals_sorted[q75_idx] if all_totals_sorted else 0

    competitors = []
    for buyer, bids in buyer_bids.items():
        total_spent = sum(b.price for b in bids)
        num_golfers = len(bids)
        avg_price = total_spent / num_golfers if num_golfers > 0 else 0

        golfer_details = []
        avg_win_prob = 0.0
        avg_anti_consensus = 0.0
        for bid in bids:
            golfer = golfers.get(bid.golfer_id)
            name = golfer.name if golfer else bid.golfer_id
            golfer_details.append({"name": name, "price": bid.price})
            if golfer:
                avg_win_prob += golfer.model_win_prob
                avg_anti_consensus += golfer.anti_consensus_score
        if num_golfers > 0:
            avg_win_prob /= num_golfers
            avg_anti_consensus /= num_golfers

        # Classify strategy profile
        profiles = []
        if avg_win_prob > 0.05:
            profiles.append("Favorite Hunter")
        if avg_anti_consensus > 0.005:
            profiles.append("Value Seeker")
        if num_golfers >= 5 and avg_price < 50:
            profiles.append("Spray and Pray")
        if total_spent >= top_quartile_threshold and top_quartile_threshold > 0:
            profiles.append("Big Spender")
        if not profiles:
            profiles.append("Balanced")

        profile = " / ".join(profiles)

        # Generate implication
        if "Favorite Hunter" in profiles:
            implication = (
                f"{buyer} loaded up on favorites -- remaining value shifts to "
                f"mid-tier and longshots."
            )
        elif "Big Spender" in profiles:
            implication = (
                f"{buyer} is spending aggressively (${total_spent:.0f}) -- "
                f"expect them to slow down or get squeezed late."
            )
        elif "Spray and Pray" in profiles:
            implication = (
                f"{buyer} is accumulating cheap options -- they have "
                f"broad coverage but thin on any single winner."
            )
        elif "Value Seeker" in profiles:
            implication = (
                f"{buyer} is targeting model-undervalued golfers -- "
                f"compete for anti-consensus picks early."
            )
        else:
            implication = (
                f"{buyer} is playing a balanced strategy with "
                f"{num_golfers} golfers at ${avg_price:.0f} average."
            )

        competitors.append({
            "buyer": buyer,
            "total_spent": round(total_spent, 2),
            "num_golfers": num_golfers,
            "avg_price": round(avg_price, 2),
            "golfers": golfer_details,
            "profile": profile,
            "implication": implication,
        })

    # Sort by total spent descending
    competitors.sort(key=lambda c: c["total_spent"], reverse=True)

    return {"competitors": competitors}


# ---------------------------------------------------------------------------
# Feature 4: Field Entry Handling
# ---------------------------------------------------------------------------


@router.get("/field-value")
async def get_field_value():
    """Calculate the combined probability and EV of all unsold golfers (the Field)."""
    import math

    store = get_store()
    golfers = store["golfers"]
    state: AuctionState = store["auction_state"]
    config = store["config"]

    remaining_golfers = [
        golfers[gid] for gid in state.golfers_remaining if gid in golfers
    ]

    if not remaining_golfers:
        return {
            "num_golfers": 0,
            "combined_win_prob": 0.0,
            "combined_top5_prob": 0.0,
            "combined_top10_prob": 0.0,
            "combined_top20_prob": 0.0,
            "combined_make_cut_prob": 0.0,
            "combined_ev": 0.0,
            "recommended_max_bid": 0.0,
            "individual_golfers": [],
        }

    ev_calc = store.get("ev_calculator") or EVCalculator()

    # Combined probability: 1 - product(1 - p_i) for each category
    combined_win = 1.0 - math.prod(1.0 - g.model_win_prob for g in remaining_golfers)
    combined_top5 = 1.0 - math.prod(1.0 - g.model_top5_prob for g in remaining_golfers)
    combined_top10 = 1.0 - math.prod(1.0 - g.model_top10_prob for g in remaining_golfers)
    combined_top20 = 1.0 - math.prod(1.0 - g.model_top20_prob for g in remaining_golfers)
    combined_make_cut = 1.0 - math.prod(1.0 - g.model_cut_prob for g in remaining_golfers)

    # Individual EVs and combined EV
    individual_golfers = []
    combined_ev = 0.0
    for g in remaining_golfers:
        ev_result = ev_calc.calculate_ev(
            {
                "win_prob": g.model_win_prob,
                "top5_prob": g.model_top5_prob,
                "top10_prob": g.model_top10_prob,
            },
            0.0,
            state.total_pool if state.total_pool > 0 else config.get("total_pool", 0),
        )
        ev = ev_result["expected_payout"]
        combined_ev += ev
        individual_golfers.append({
            "name": g.name,
            "golfer_id": g.id,
            "win_prob": round(g.model_win_prob, 6),
            "ev": round(ev, 2),
        })

    # Sort by EV descending
    individual_golfers.sort(key=lambda x: x["ev"], reverse=True)

    # Recommended max bid using Kelly criterion on combined win probability
    # Kelly fraction: f* = (bp - q) / b where b = odds, p = prob, q = 1-p
    pool = state.total_pool if state.total_pool > 0 else config.get("total_pool", 0)
    if pool > 0 and combined_win > 0:
        # Use the top prize (1st place) payout as the return multiple
        first_pct = config.get("payout_structure", {}).get("1st", 0.5)
        b = (pool * first_pct)  # potential winnings if field wins
        # Kelly: recommended_max = combined_ev * some fraction
        # Simpler: use 85% of combined EV as max bid (same as alerts logic)
        recommended_max = round(combined_ev * 0.85, 2)
    else:
        recommended_max = 0.0

    return {
        "num_golfers": len(remaining_golfers),
        "combined_win_prob": round(combined_win, 6),
        "combined_top5_prob": round(combined_top5, 6),
        "combined_top10_prob": round(combined_top10, 6),
        "combined_top20_prob": round(combined_top20, 6),
        "combined_make_cut_prob": round(combined_make_cut, 6),
        "combined_ev": round(combined_ev, 2),
        "recommended_max_bid": recommended_max,
        "individual_golfers": individual_golfers,
    }
