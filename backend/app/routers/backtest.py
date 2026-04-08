"""Backtesting endpoints.

Runs historical simulations to validate the strategy engine against
past Masters results.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas import BacktestRequest, BacktestResult

router = APIRouter(prefix="/backtest", tags=["backtest"])

# ---------------------------------------------------------------------------
# Historical Masters results (simplified for backtesting)
# ---------------------------------------------------------------------------

_HISTORICAL_RESULTS: dict[int, list[dict]] = {
    2024: [
        {"name": "Scottie Scheffler", "finish": 1, "score": -12},
        {"name": "Ludvig Aberg", "finish": 2, "score": -7},
        {"name": "Collin Morikawa", "finish": 3, "score": -6},
        {"name": "Max Homa", "finish": 4, "score": -6},
        {"name": "Tommy Fleetwood", "finish": 5, "score": -5},
        {"name": "Bryson DeChambeau", "finish": 6, "score": -4},
        {"name": "Cameron Smith", "finish": 7, "score": -4},
        {"name": "Xander Schauffele", "finish": 8, "score": -3},
        {"name": "Patrick Cantlay", "finish": 9, "score": -3},
        {"name": "Hideki Matsuyama", "finish": 10, "score": -2},
    ],
    2023: [
        {"name": "Jon Rahm", "finish": 1, "score": -12},
        {"name": "Brooks Koepka", "finish": 2, "score": -8},
        {"name": "Phil Mickelson", "finish": 2, "score": -8},
        {"name": "Jordan Spieth", "finish": 4, "score": -7},
        {"name": "Patrick Reed", "finish": 5, "score": -6},
        {"name": "Russell Henley", "finish": 6, "score": -5},
        {"name": "Sahith Theegala", "finish": 7, "score": -5},
        {"name": "Viktor Hovland", "finish": 8, "score": -4},
        {"name": "Sam Burns", "finish": 9, "score": -3},
        {"name": "Scottie Scheffler", "finish": 10, "score": -3},
    ],
    2022: [
        {"name": "Scottie Scheffler", "finish": 1, "score": -10},
        {"name": "Rory McIlroy", "finish": 2, "score": -7},
        {"name": "Shane Lowry", "finish": 3, "score": -5},
        {"name": "Cameron Smith", "finish": 3, "score": -5},
        {"name": "Collin Morikawa", "finish": 5, "score": -4},
        {"name": "Will Zalatoris", "finish": 6, "score": -3},
        {"name": "Corey Conners", "finish": 7, "score": -3},
        {"name": "Justin Thomas", "finish": 8, "score": -2},
        {"name": "Sungjae Im", "finish": 9, "score": -2},
        {"name": "Cameron Young", "finish": 10, "score": -1},
    ],
    2021: [
        {"name": "Hideki Matsuyama", "finish": 1, "score": -10},
        {"name": "Will Zalatoris", "finish": 2, "score": -9},
        {"name": "Jordan Spieth", "finish": 3, "score": -7},
        {"name": "Xander Schauffele", "finish": 3, "score": -7},
        {"name": "Marc Leishman", "finish": 5, "score": -6},
        {"name": "Justin Rose", "finish": 5, "score": -6},
        {"name": "Corey Conners", "finish": 7, "score": -5},
        {"name": "Tony Finau", "finish": 8, "score": -5},
        {"name": "Jon Rahm", "finish": 9, "score": -4},
        {"name": "Patrick Reed", "finish": 10, "score": -4},
    ],
    2019: [
        {"name": "Tiger Woods", "finish": 1, "score": -13},
        {"name": "Dustin Johnson", "finish": 2, "score": -12},
        {"name": "Brooks Koepka", "finish": 2, "score": -12},
        {"name": "Xander Schauffele", "finish": 2, "score": -12},
        {"name": "Jason Day", "finish": 5, "score": -11},
        {"name": "Tony Finau", "finish": 5, "score": -11},
        {"name": "Webb Simpson", "finish": 5, "score": -11},
        {"name": "Francesco Molinari", "finish": 5, "score": -11},
        {"name": "Patrick Cantlay", "finish": 9, "score": -10},
        {"name": "Rickie Fowler", "finish": 9, "score": -10},
    ],
}

# Simulated pre-tournament model probabilities for backtesting
_HISTORICAL_MODEL_PROBS: dict[int, dict[str, dict]] = {
    2024: {
        "Scottie Scheffler": {"win": 0.22, "top5": 0.55, "top10": 0.72, "odds_price_ratio": 0.85},
        "Rory McIlroy": {"win": 0.09, "top5": 0.35, "top10": 0.50, "odds_price_ratio": 0.70},
        "Ludvig Aberg": {"win": 0.06, "top5": 0.25, "top10": 0.40, "odds_price_ratio": 1.20},
        "Collin Morikawa": {"win": 0.055, "top5": 0.24, "top10": 0.38, "odds_price_ratio": 1.10},
        "Max Homa": {"win": 0.025, "top5": 0.12, "top10": 0.22, "odds_price_ratio": 1.40},
        "Tommy Fleetwood": {"win": 0.03, "top5": 0.14, "top10": 0.25, "odds_price_ratio": 1.15},
        "Xander Schauffele": {"win": 0.08, "top5": 0.32, "top10": 0.48, "odds_price_ratio": 0.95},
    },
    2023: {
        "Jon Rahm": {"win": 0.10, "top5": 0.38, "top10": 0.52, "odds_price_ratio": 1.05},
        "Scottie Scheffler": {"win": 0.15, "top5": 0.45, "top10": 0.60, "odds_price_ratio": 0.90},
        "Rory McIlroy": {"win": 0.09, "top5": 0.34, "top10": 0.48, "odds_price_ratio": 0.88},
        "Brooks Koepka": {"win": 0.04, "top5": 0.18, "top10": 0.30, "odds_price_ratio": 1.30},
        "Jordan Spieth": {"win": 0.05, "top5": 0.22, "top10": 0.35, "odds_price_ratio": 1.25},
    },
    2022: {
        "Scottie Scheffler": {"win": 0.08, "top5": 0.30, "top10": 0.45, "odds_price_ratio": 1.15},
        "Jon Rahm": {"win": 0.10, "top5": 0.38, "top10": 0.52, "odds_price_ratio": 0.95},
        "Cameron Smith": {"win": 0.06, "top5": 0.26, "top10": 0.40, "odds_price_ratio": 1.10},
        "Rory McIlroy": {"win": 0.07, "top5": 0.28, "top10": 0.42, "odds_price_ratio": 0.85},
        "Will Zalatoris": {"win": 0.04, "top5": 0.20, "top10": 0.33, "odds_price_ratio": 1.40},
    },
    2021: {
        "Dustin Johnson": {"win": 0.12, "top5": 0.40, "top10": 0.55, "odds_price_ratio": 0.90},
        "Bryson DeChambeau": {"win": 0.08, "top5": 0.30, "top10": 0.44, "odds_price_ratio": 0.95},
        "Hideki Matsuyama": {"win": 0.04, "top5": 0.18, "top10": 0.30, "odds_price_ratio": 1.35},
        "Jordan Spieth": {"win": 0.06, "top5": 0.25, "top10": 0.38, "odds_price_ratio": 1.20},
        "Xander Schauffele": {"win": 0.05, "top5": 0.22, "top10": 0.35, "odds_price_ratio": 1.10},
    },
    2019: {
        "Tiger Woods": {"win": 0.03, "top5": 0.14, "top10": 0.25, "odds_price_ratio": 1.80},
        "Rory McIlroy": {"win": 0.10, "top5": 0.38, "top10": 0.52, "odds_price_ratio": 0.85},
        "Dustin Johnson": {"win": 0.08, "top5": 0.32, "top10": 0.46, "odds_price_ratio": 0.95},
        "Brooks Koepka": {"win": 0.07, "top5": 0.28, "top10": 0.42, "odds_price_ratio": 1.00},
        "Justin Thomas": {"win": 0.06, "top5": 0.25, "top10": 0.38, "odds_price_ratio": 0.90},
    },
}


def _simulate_auction(
    year: int,
    strategy: str,
    bankroll: float,
) -> BacktestResult:
    """Simulate an auction for a historical year.

    Strategy options:
    - model_ev: buy golfers ranked by model win probability
    - anti_consensus: buy golfers where model > consensus (high odds_price_ratio)
    - balanced: mix of top picks and value picks
    """
    probs = _HISTORICAL_MODEL_PROBS.get(year, {})
    results = _HISTORICAL_RESULTS.get(year, [])
    result_map = {r["name"]: r["finish"] for r in results}

    if not probs:
        return BacktestResult(year=year, strategy=strategy, bankroll=bankroll)

    # Sort golfers by strategy preference
    if strategy == "anti_consensus":
        ranked = sorted(
            probs.items(),
            key=lambda x: x[1].get("odds_price_ratio", 1.0),
            reverse=True,
        )
    elif strategy == "balanced":
        # Weighted score: 60% win prob, 40% value ratio
        ranked = sorted(
            probs.items(),
            key=lambda x: x[1]["win"] * 0.6 + x[1].get("odds_price_ratio", 1.0) * 0.04,
            reverse=True,
        )
    else:  # model_ev
        ranked = sorted(probs.items(), key=lambda x: x[1]["win"], reverse=True)

    # Simulate buying: allocate bankroll proportionally
    total_score = sum(p["win"] for _, p in ranked)
    purchased = []
    remaining = bankroll

    for name, prob in ranked:
        if remaining <= 0:
            break
        # Simulate price as proportional share of bankroll with some noise
        fair_price = (prob["win"] / total_score) * bankroll * 0.9
        bid_price = min(fair_price, remaining * 0.4)
        if bid_price < 5:
            bid_price = min(5, remaining)

        remaining -= bid_price
        purchased.append({
            "name": name,
            "price": round(bid_price, 2),
            "model_win_prob": prob["win"],
            "actual_finish": result_map.get(name, 99),
        })

    # Compute payout using default structure
    pool = bankroll * 3  # simulate 3x pool
    payout_rates = {"1st": 0.50, "2nd": 0.20, "3rd": 0.10, "top5": 0.05, "top10": 0.03}
    total_invested = sum(p["price"] for p in purchased)
    total_payout = 0.0

    for p in purchased:
        finish = p["actual_finish"]
        if finish == 1:
            total_payout += pool * payout_rates["1st"]
        elif finish == 2:
            total_payout += pool * payout_rates["2nd"]
        elif finish == 3:
            total_payout += pool * payout_rates["3rd"]
        elif finish <= 5:
            total_payout += pool * payout_rates["top5"]
        elif finish <= 10:
            total_payout += pool * payout_rates["top10"]

    net_profit = total_payout - total_invested
    roi = (net_profit / total_invested * 100) if total_invested > 0 else 0

    return BacktestResult(
        year=year,
        strategy=strategy,
        bankroll=bankroll,
        golfers_purchased=purchased,
        total_invested=round(total_invested, 2),
        total_payout=round(total_payout, 2),
        net_profit=round(net_profit, 2),
        roi=round(roi, 1),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/years", response_model=list[int])
async def available_years() -> list[int]:
    """Return years with historical data available for backtesting."""
    return sorted(_HISTORICAL_RESULTS.keys(), reverse=True)


@router.post("/run", response_model=BacktestResult)
async def run_backtest(req: BacktestRequest) -> BacktestResult:
    """Run a backtest simulation against a historical year."""
    if req.year not in _HISTORICAL_RESULTS:
        raise HTTPException(
            status_code=404,
            detail=f"No historical data for {req.year}. Available: {sorted(_HISTORICAL_RESULTS.keys())}",
        )
    if req.strategy not in ("model_ev", "anti_consensus", "balanced"):
        raise HTTPException(
            status_code=400,
            detail="Strategy must be one of: model_ev, anti_consensus, balanced",
        )
    return _simulate_auction(req.year, req.strategy, req.bankroll)
