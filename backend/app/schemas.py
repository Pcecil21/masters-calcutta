"""Pydantic models for the Masters Calcutta Auction system."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Golfer(BaseModel):
    """Full golfer profile with model probabilities and consensus data."""

    id: str
    name: str
    world_ranking: int
    odds_to_win: float = Field(description="Decimal odds to win the tournament")
    masters_appearances: int = 0
    masters_wins: int = 0
    masters_top10s: int = 0
    recent_form_score: float = Field(
        default=0.0, description="0-100 score based on last 8 tournament results"
    )
    augusta_history_score: float = Field(
        default=0.0, description="0-100 score based on Augusta National performance history"
    )
    current_season_stats: dict = Field(default_factory=dict)

    # Model-generated probabilities
    model_win_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    model_top5_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    model_top10_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    model_top20_prob: float = Field(default=0.0, ge=0.0, le=1.0)
    model_cut_prob: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Probability of making the cut"
    )

    # Consensus / market data
    consensus_win_prob: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Implied win prob from betting odds"
    )

    # Derived value scores
    ev_score: float = Field(
        default=0.0, description="Expected value score combining all finish probabilities"
    )
    anti_consensus_score: float = Field(
        default=0.0,
        description="Model win prob minus consensus win prob; positive = undervalued",
    )


class AuctionConfig(BaseModel):
    """Configuration payload for setting up the auction."""

    total_pool: float = Field(gt=0, description="Total auction pool size in dollars")
    my_bankroll: float = Field(gt=0, description="My available bankroll")
    num_bidders: int = Field(default=12, ge=1)
    estimated_pool: float = Field(default=0.0, ge=0, description="Optional initial pool estimate before bids flow")
    payout_structure: dict = Field(
        default_factory=lambda: {
            "1st": 0.50,
            "2nd": 0.20,
            "3rd": 0.12,
            "4th": 0.05,
            "5th": 0.05,
            "6th": 0.016,
            "7th": 0.016,
            "8th": 0.016,
            "9th": 0.016,
            "10th": 0.016,
        },
        description="Payout percentages keyed by finish position/tier",
    )


class AuctionState(BaseModel):
    """Current state of the auction."""

    total_pool: float = 0.0
    my_bankroll: float = 0.0
    remaining_bankroll: float = 0.0
    golfers_sold: list[str] = Field(default_factory=list, description="List of golfer IDs sold")
    golfers_remaining: list[str] = Field(
        default_factory=list, description="List of golfer IDs not yet sold"
    )
    current_phase: str = Field(
        default="pre_auction",
        description="pre_auction | early (top 20) | middle (21-50) | late (51+) | complete",
    )


class BidRequest(BaseModel):
    """Incoming bid submission."""

    golfer_id: str
    buyer: str = Field(description="'me' for self, or other buyer's name")
    price: float = Field(gt=0)


class BidRecord(BaseModel):
    """Recorded bid with timestamp."""

    golfer_id: str
    buyer: str
    price: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PortfolioEntry(BaseModel):
    """A single golfer in my portfolio."""

    golfer_id: str
    purchase_price: float
    model_win_prob: float
    model_top5_prob: float
    expected_value: float = Field(description="Dollar EV based on payout structure")
    ev_multiple: float = Field(description="expected_value / purchase_price")


class Portfolio(BaseModel):
    """Full portfolio analysis."""

    entries: list[PortfolioEntry] = Field(default_factory=list)
    total_invested: float = 0.0
    total_expected_value: float = 0.0
    expected_roi: float = Field(default=0.0, description="(total_ev - invested) / invested")
    risk_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="0=safe diversified, 100=all-in on one golfer"
    )


class StrategyRecommendation(BaseModel):
    """Bid strategy recommendation for a golfer."""

    golfer_id: str
    max_bid: float
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    alert_level: str = Field(
        description="must_bid | good_value | fair | overpriced | avoid"
    )


class PriceCheckRequest(BaseModel):
    """Real-time price check during live auction."""

    golfer_id: str
    current_price: float = Field(gt=0)


class PriceCheckResponse(BaseModel):
    """Result of a live price check."""

    golfer_id: str
    golfer_name: str
    current_price: float
    expected_payout: float
    ev: float
    ev_multiple: float
    max_bid: float
    verdict: str = Field(description="BID | PASS | MARGINAL")
    message: str


class QuickSheetEntry(BaseModel):
    """Single row in the auction cheat sheet."""

    golfer_id: str
    name: str
    max_bid: float
    breakeven_price: float
    alert_level: str


class Alert(BaseModel):
    """Real-time alert during auction."""

    golfer_id: str
    message: str
    alert_type: str = Field(description="must_bid | value_alert | budget_warning | portfolio_gap")
    priority: int = Field(ge=1, le=5, description="1=highest priority, 5=lowest")
    current_price: Optional[float] = None
    recommended_max: Optional[float] = None


class BacktestRequest(BaseModel):
    """Request to run a historical backtest."""

    year: int
    strategy: str = Field(
        default="model_ev", description="model_ev | anti_consensus | balanced"
    )
    bankroll: float = Field(default=1000.0, gt=0)


class BacktestResult(BaseModel):
    """Results from a historical backtest."""

    year: int
    strategy: str
    bankroll: float
    golfers_purchased: list[dict] = Field(default_factory=list)
    total_invested: float = 0.0
    total_payout: float = 0.0
    net_profit: float = 0.0
    roi: float = 0.0
