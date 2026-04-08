"""Portfolio analysis endpoints.

Provides portfolio-level insights including diversification scoring,
correlation analysis, and projected payouts.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.data.loaders import get_store
from app.schemas import Golfer, Portfolio, PortfolioEntry

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _compute_golfer_ev(golfer: Golfer, config: dict) -> float:
    """Compute dollar EV for a golfer."""
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


@router.get("", response_model=Portfolio)
async def get_portfolio() -> Portfolio:
    """Return the current portfolio of golfers I've won."""
    return get_store()["portfolio"]


@router.get("/optimization", response_model=dict)
async def portfolio_optimization() -> dict:
    """Portfolio-level analysis with correlation and diversification metrics.

    Returns:
    - diversification_score: 0-100 (higher = more diversified)
    - style_breakdown: percentage of portfolio by golfer archetype
    - correlation_notes: qualitative overlap warnings
    - improvement_suggestions: what types of golfers to target next
    """
    store = get_store()
    portfolio: Portfolio = store["portfolio"]
    golfers = store["golfers"]
    config = store["config"]

    if not portfolio.entries:
        return {
            "diversification_score": 0,
            "style_breakdown": {},
            "correlation_notes": [],
            "improvement_suggestions": ["Start bidding to build your portfolio."],
            "portfolio_summary": {
                "total_golfers": 0,
                "total_invested": 0,
                "total_ev": 0,
                "expected_roi": 0,
            },
        }

    # Classify golfers by archetype based on their profile
    archetypes = {
        "elite_favorite": [],    # top 5 model probability
        "contender": [],         # top 10 probability > 0.3
        "value_pick": [],        # high anti-consensus score
        "longshot": [],          # low probability but cheap
        "augusta_specialist": [],  # high augusta history score
    }

    for entry in portfolio.entries:
        golfer = golfers.get(entry.golfer_id)
        if golfer is None:
            continue
        if golfer.model_win_prob > 0.08:
            archetypes["elite_favorite"].append(golfer.name)
        elif golfer.model_top10_prob > 0.30:
            archetypes["contender"].append(golfer.name)
        elif golfer.anti_consensus_score > 0.01:
            archetypes["value_pick"].append(golfer.name)
        elif golfer.augusta_history_score > 70:
            archetypes["augusta_specialist"].append(golfer.name)
        else:
            archetypes["longshot"].append(golfer.name)

    # Style breakdown as percentages
    total = len(portfolio.entries)
    style_breakdown = {
        k: round(len(v) / total * 100, 1) for k, v in archetypes.items() if v
    }

    # Diversification score based on archetype spread and count
    unique_archetypes = sum(1 for v in archetypes.values() if v)
    count_score = min(50, total * 10)  # up to 50 points for having 5+ golfers
    archetype_score = min(50, unique_archetypes * 12.5)  # up to 50 for 4+ archetypes
    diversification_score = round(count_score + archetype_score, 1)

    # Correlation warnings
    correlation_notes = []
    if len(archetypes["elite_favorite"]) >= 2:
        correlation_notes.append(
            f"Heavy favorite concentration: {', '.join(archetypes['elite_favorite'])}. "
            f"These golfers are negatively correlated for payout (only one can win)."
        )
    if not archetypes["longshot"] and not archetypes["value_pick"]:
        correlation_notes.append(
            "No longshots or value picks. Consider adding cheap upside exposure."
        )
    if total == 1:
        correlation_notes.append(
            "Single golfer portfolio has maximum concentration risk."
        )

    # Suggestions
    suggestions = []
    if not archetypes["elite_favorite"]:
        suggestions.append("Consider adding an elite favorite for high win probability.")
    if not archetypes["value_pick"]:
        suggestions.append("Look for anti-consensus value picks where our model disagrees with odds.")
    if not archetypes["longshot"] and total >= 3:
        suggestions.append("Add a cheap longshot for asymmetric upside.")
    if total < 4:
        suggestions.append(f"Portfolio is thin ({total} golfers). Aim for 5-8 for proper diversification.")

    return {
        "diversification_score": diversification_score,
        "style_breakdown": style_breakdown,
        "archetypes": {k: v for k, v in archetypes.items() if v},
        "correlation_notes": correlation_notes,
        "improvement_suggestions": suggestions,
        "portfolio_summary": {
            "total_golfers": total,
            "total_invested": round(portfolio.total_invested, 2),
            "total_ev": round(portfolio.total_expected_value, 2),
            "expected_roi": round(portfolio.expected_roi * 100, 1),
            "risk_score": portfolio.risk_score,
        },
    }


@router.get("/expected-payout", response_model=dict)
async def expected_payout() -> dict:
    """Project returns given the payout structure.

    Breaks down EV contribution by finish tier for each golfer.
    """
    store = get_store()
    portfolio: Portfolio = store["portfolio"]
    golfers = store["golfers"]
    config = store["config"]
    pool = config.get("total_pool", 0.0)
    ps = config.get("payout_structure", {})

    if not portfolio.entries or pool <= 0:
        return {
            "total_pool": pool,
            "payout_structure": ps,
            "golfer_projections": [],
            "total_invested": 0,
            "total_expected_payout": 0,
            "expected_profit": 0,
            "expected_roi_pct": 0,
            "win_probability_any": 0,
        }

    projections = []
    total_ev = 0.0
    combined_miss_prob = 1.0  # probability NONE of my golfers win

    for entry in portfolio.entries:
        golfer = golfers.get(entry.golfer_id)
        if golfer is None:
            continue

        tier_ev = {
            "1st": round(golfer.model_win_prob * pool * ps.get("1st", 0.50), 2),
            "2nd": round(
                max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.3)
                * pool * ps.get("2nd", 0.20), 2
            ),
            "3rd": round(
                max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.25)
                * pool * ps.get("3rd", 0.10), 2
            ),
            "top5": round(
                max(0, (golfer.model_top5_prob - golfer.model_win_prob) * 0.45)
                * pool * ps.get("top5", 0.05), 2
            ),
            "top10": round(
                max(0, golfer.model_top10_prob - golfer.model_top5_prob)
                * pool * ps.get("top10", 0.03), 2
            ),
            "made_cut": round(
                max(0, golfer.model_cut_prob - golfer.model_top10_prob)
                * pool * ps.get("made_cut", 0.01), 2
            ),
        }
        golfer_ev = sum(tier_ev.values())
        total_ev += golfer_ev
        combined_miss_prob *= (1.0 - golfer.model_win_prob)

        projections.append({
            "golfer_id": entry.golfer_id,
            "name": golfer.name,
            "purchase_price": entry.purchase_price,
            "ev_by_tier": tier_ev,
            "total_ev": round(golfer_ev, 2),
            "ev_multiple": round(golfer_ev / entry.purchase_price, 2) if entry.purchase_price > 0 else 0,
            "model_win_prob": golfer.model_win_prob,
            "model_top5_prob": golfer.model_top5_prob,
        })

    invested = portfolio.total_invested
    expected_profit = total_ev - invested
    roi_pct = (expected_profit / invested * 100) if invested > 0 else 0
    win_prob_any = round(1.0 - combined_miss_prob, 4)

    # Sort projections by EV descending
    projections.sort(key=lambda p: p["total_ev"], reverse=True)

    return {
        "total_pool": pool,
        "payout_structure": ps,
        "golfer_projections": projections,
        "total_invested": round(invested, 2),
        "total_expected_payout": round(total_ev, 2),
        "expected_profit": round(expected_profit, 2),
        "expected_roi_pct": round(roi_pct, 1),
        "win_probability_any": win_prob_any,
    }
