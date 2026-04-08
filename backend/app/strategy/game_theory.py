"""
Game theory and bidder behavior modeling for Calcutta auctions.

Models the systematic biases of casual auction participants to identify
market inefficiencies.  Most Calcutta pools are dominated by recreational
bettors who exhibit predictable behavioral patterns:

  - Fame premium: big names (Scottie, Rory, Tiger) get bid up 20-40%
    above fair value because people want to "own" them.
  - Recency bias: a golfer who won last week gets overbid 15-25%.
  - Narrative premium: comeback stories and Augusta lore drive overbidding.
  - Obscurity discount: lesser-known international players get underbid
    20-30% because casual fans don't recognize them.
  - Longshot neglect: golfers outside the top 30 get systematically
    underbid because casual bidders concentrate capital on favorites.

Exploiting these inefficiencies is the primary edge in a Calcutta.
"""

from __future__ import annotations

from typing import Optional

import numpy as np


# Tier thresholds for fame classification
_MARQUEE_NAMES = {
    "tiger_woods", "rory_mcilroy", "scottie_scheffler", "jon_rahm",
    "jordan_spieth", "bryson_dechambeau", "phil_mickelson", "justin_thomas",
    "brooks_koepka", "dustin_johnson", "collin_morikawa",
}

# World ranking tiers
_TIER_ELITE = 10      # top 10 OWGR
_TIER_CONTENDER = 30  # 11-30
_TIER_MIDFIELD = 50   # 31-50
_TIER_LONGSHOT = 999  # 51+


class BidderModel:
    """Models auction participant behavior and detects market inefficiencies.

    This is the core game-theory engine.  It predicts what casual bidders
    will pay for each golfer, then compares that to model-fair-value to
    find mispriced golfers.
    """

    def __init__(
        self,
        fame_premium: float = 0.30,
        recency_premium: float = 0.20,
        narrative_premium: float = 0.15,
        obscurity_discount: float = 0.25,
        longshot_discount: float = 0.20,
    ) -> None:
        """Initialize bidder behavior parameters.

        All premium/discount values are expressed as fractions of fair value.
        For example, fame_premium=0.30 means marquee names sell for ~30%
        above model-fair-value on average.

        Args:
            fame_premium: Overbid factor for household-name golfers.
            recency_premium: Overbid factor for recent tournament winners.
            narrative_premium: Overbid factor for compelling storylines.
            obscurity_discount: Underbid factor for lesser-known players.
            longshot_discount: Underbid factor for golfers outside top 30.
        """
        self.fame_premium = fame_premium
        self.recency_premium = recency_premium
        self.narrative_premium = narrative_premium
        self.obscurity_discount = obscurity_discount
        self.longshot_discount = longshot_discount

    def _classify_golfer(self, golfer: dict) -> dict:
        """Classify a golfer's behavioral factors.

        Args:
            golfer: Golfer data dict with keys like world_ranking, name/id,
                    recent_form_score, masters_appearances, etc.

        Returns:
            Dict of behavioral factor classifications and magnitudes.
        """
        golfer_id = golfer.get("id", golfer.get("golfer_id", "")).lower()
        name = golfer.get("name", "").lower()
        ranking = golfer.get("world_ranking", 50)
        form_score = golfer.get("recent_form_score", 50.0)
        masters_apps = golfer.get("masters_appearances", 0)
        masters_wins = golfer.get("masters_wins", 0)

        factors = {
            "is_marquee": False,
            "fame_factor": 0.0,
            "recency_factor": 0.0,
            "narrative_factor": 0.0,
            "obscurity_factor": 0.0,
            "longshot_factor": 0.0,
        }

        # Fame: marquee name or top-5 world ranking
        if golfer_id in _MARQUEE_NAMES or any(n in name for n in ["tiger", "rory", "scottie", "spieth"]):
            factors["is_marquee"] = True
            factors["fame_factor"] = self.fame_premium
        elif ranking <= 5:
            factors["fame_factor"] = self.fame_premium * 0.6

        # Recency: high recent form score suggests recent wins/contention
        if form_score >= 85:
            factors["recency_factor"] = self.recency_premium
        elif form_score >= 70:
            factors["recency_factor"] = self.recency_premium * 0.5

        # Narrative: past Masters winners, Augusta history, comeback stories
        if masters_wins >= 1:
            factors["narrative_factor"] = self.narrative_premium * min(masters_wins, 3) / 2
        elif masters_apps >= 10:
            factors["narrative_factor"] = self.narrative_premium * 0.4

        # Obscurity: high world ranking number + low Masters appearances
        if ranking > _TIER_CONTENDER and masters_apps <= 3:
            factors["obscurity_factor"] = self.obscurity_discount
        elif ranking > _TIER_MIDFIELD and masters_apps <= 5:
            factors["obscurity_factor"] = self.obscurity_discount * 0.6

        # Longshot: outside top 30
        if ranking > _TIER_CONTENDER:
            # Discount scales with how far outside top 30
            scale = min((ranking - _TIER_CONTENDER) / 40.0, 1.0)
            factors["longshot_factor"] = self.longshot_discount * scale

        return factors

    def predict_market_price(
        self,
        golfer: dict,
        pool_size: float,
        num_bidders: int,
    ) -> dict:
        """Predict the likely market clearing price for a golfer.

        Starts from model-fair-value (expected payout) and adjusts for
        behavioral premiums/discounts to estimate what casual bidders
        will actually pay.

        Args:
            golfer: Golfer data including model probabilities and metadata.
            pool_size: Total auction pool in dollars.
            num_bidders: Number of bidders in the auction.

        Returns:
            Dictionary with:
                - fair_value: model-based fair price (expected payout)
                - predicted_price: what the market will likely pay
                - premium_pct: total premium/discount as percentage
                - factors: breakdown of behavioral factors
                - efficiency: predicted_price / fair_value
        """
        # Fair value = expected payout based on model probabilities
        win_prob = golfer.get("model_win_prob", golfer.get("win_prob", 0.0))
        top5_prob = golfer.get("model_top5_prob", golfer.get("top5_prob", 0.0))
        top10_prob = golfer.get("model_top10_prob", golfer.get("top10_prob", 0.0))

        # Simplified expected payout (using standard structure)
        fair_value = pool_size * (
            win_prob * 0.50
            + max(top5_prob - win_prob, 0) * 0.085  # avg of 2nd-5th payouts
            + max(top10_prob - top5_prob, 0) * 0.016  # avg of 6th-10th payouts
        )

        if fair_value <= 0:
            return {
                "fair_value": 0.0,
                "predicted_price": 0.0,
                "premium_pct": 0.0,
                "factors": {},
                "efficiency": 0.0,
            }

        factors = self._classify_golfer(golfer)

        # Net premium: positive means overbid, negative means underbid
        premium = (
            factors["fame_factor"]
            + factors["recency_factor"]
            + factors["narrative_factor"]
            - factors["obscurity_factor"]
            - factors["longshot_factor"]
        )

        # More bidders = more competition = higher prices overall
        # Each additional bidder above 8 adds ~2% to expected price
        bidder_premium = max((num_bidders - 8) * 0.02, 0.0)
        premium += bidder_premium

        predicted_price = fair_value * (1.0 + premium)

        # Floor at some minimum (even the worst golfer has nonzero cost)
        min_price = pool_size * 0.002  # $2 per $1000 pool
        predicted_price = max(predicted_price, min_price)

        return {
            "fair_value": round(fair_value, 2),
            "predicted_price": round(predicted_price, 2),
            "premium_pct": round(premium * 100, 1),
            "factors": factors,
            "efficiency": round(predicted_price / fair_value, 3) if fair_value > 0 else 0,
        }

    def identify_inefficiencies(
        self,
        golfers: list[dict],
        pool_size: float,
        num_bidders: int = 12,
    ) -> list[dict]:
        """Rank golfers by expected market mispricing.

        Positive mispricing = golfer is likely to sell BELOW fair value
        (buy opportunity).  Negative = likely to sell ABOVE fair value
        (let someone else overpay).

        Args:
            golfers: List of golfer data dicts.
            pool_size: Total auction pool.
            num_bidders: Number of auction participants.

        Returns:
            List of dicts sorted by mispricing magnitude (best values first),
            each containing golfer_id, fair_value, predicted_price,
            mispricing, mispricing_pct, and recommendation.
        """
        results = []

        for g in golfers:
            prediction = self.predict_market_price(g, pool_size, num_bidders)
            fv = prediction["fair_value"]
            pp = prediction["predicted_price"]

            if fv <= 0:
                continue

            # Mispricing: positive = undervalued (market price < fair value)
            mispricing = fv - pp
            mispricing_pct = (mispricing / fv) * 100 if fv > 0 else 0

            if mispricing_pct > 15:
                recommendation = "STRONG BUY - significantly undervalued"
            elif mispricing_pct > 5:
                recommendation = "BUY - moderately undervalued"
            elif mispricing_pct > -5:
                recommendation = "FAIR - priced near value"
            elif mispricing_pct > -15:
                recommendation = "AVOID - moderately overvalued"
            else:
                recommendation = "STRONG AVOID - significantly overvalued"

            results.append({
                "golfer_id": g.get("id", g.get("golfer_id", "unknown")),
                "name": g.get("name", "Unknown"),
                "fair_value": fv,
                "predicted_price": pp,
                "mispricing": round(mispricing, 2),
                "mispricing_pct": round(mispricing_pct, 1),
                "recommendation": recommendation,
                "factors": prediction["factors"],
            })

        # Sort: largest positive mispricing first (best buys)
        results.sort(key=lambda x: x["mispricing_pct"], reverse=True)
        return results

    def second_order_adjustment(
        self,
        golfer: dict,
        sharp_bidder_count: int,
        pool_size: float = 10000.0,
        num_bidders: int = 12,
    ) -> float:
        """Adjust predicted price for the presence of other sharp bidders.

        When other sophisticated bidders are in the pool, the obvious
        value plays get competed away.  Each additional sharp bidder
        compresses the edge on undervalued golfers by ~15-20%, because
        they're looking at the same signals.

        Conversely, overvalued golfers stay overvalued because casual
        bidders still drive those prices.

        Args:
            golfer: Golfer data dict.
            sharp_bidder_count: Number of other sophisticated bidders
                (excluding yourself).
            pool_size: Total auction pool.
            num_bidders: Total bidders.

        Returns:
            Adjusted predicted market price.
        """
        base = self.predict_market_price(golfer, pool_size, num_bidders)
        fair_value = base["fair_value"]
        predicted = base["predicted_price"]

        if fair_value <= 0:
            return predicted

        # If the golfer is undervalued, sharp bidders compress the edge
        if predicted < fair_value:
            compression = 1 - (0.18 * min(sharp_bidder_count, 4))
            compression = max(compression, 0.2)  # at least 20% edge remains
            gap = fair_value - predicted
            adjusted = predicted + gap * (1 - compression)
        else:
            # Overvalued golfers: sharp bidders don't push price higher,
            # but they also don't really bring it down (casual bidders
            # dominate the high end).
            adjusted = predicted

        return round(adjusted, 2)

    def meta_strategy(
        self,
        auction_state: dict,
        my_portfolio: list[dict],
        sharp_bidder_portfolios: Optional[dict[str, list[dict]]] = None,
    ) -> dict:
        """Portfolio-aware strategy adjustments based on game state.

        Considers:
        - What I already own (avoid correlated bets)
        - What sharp bidders already own (their remaining demand)
        - Auction phase (early = be patient, late = be aggressive)
        - Budget pacing (ahead/behind on spending)

        Args:
            auction_state: Current auction state with keys like phase,
                remaining_bankroll, total_pool, golfers_remaining.
            my_portfolio: List of golfers I've already purchased.
            sharp_bidder_portfolios: Optional mapping of bidder_name ->
                list of golfers they've purchased.

        Returns:
            Strategy recommendation dict with:
                - aggression_level: 0.0-1.0 (0=very patient, 1=very aggressive)
                - target_tier: which tier of golfers to target next
                - budget_guidance: spend faster/slower/on-pace
                - sharp_bidder_intel: what sharp bidders are likely targeting
                - key_recommendation: one-sentence strategy summary
        """
        phase = auction_state.get("current_phase", auction_state.get("phase", "early"))
        remaining_bankroll = auction_state.get("remaining_bankroll", 0)
        total_pool = auction_state.get("total_pool", 10000)
        golfers_remaining = auction_state.get("golfers_remaining", [])
        num_remaining = len(golfers_remaining) if isinstance(golfers_remaining, list) else golfers_remaining

        # Portfolio analysis
        total_invested = sum(p.get("purchase_price", 0) for p in my_portfolio)
        num_owned = len(my_portfolio)
        has_elite = any(
            p.get("model_win_prob", 0) > 0.05 or p.get("world_ranking", 99) <= 10
            for p in my_portfolio
        )
        has_mid = any(
            0.01 < p.get("model_win_prob", 0) <= 0.05
            for p in my_portfolio
        )

        # Aggression level based on phase and budget
        budget_ratio = remaining_bankroll / total_pool if total_pool > 0 else 0

        if phase == "early":
            aggression = 0.3
            target_tier = "Wait for value. Let casual bidders overpay for marquee names."
        elif phase == "middle":
            aggression = 0.5
            target_tier = "Mid-tier contenders (world ranking 15-35) - best value zone."
        elif phase == "late":
            aggression = 0.7
            target_tier = "Longshots and sleepers - fill portfolio gaps cheaply."
        else:  # final
            aggression = 0.9
            target_tier = "Buy everything with positive EV. Don't leave money on the table."

        # Adjust aggression for budget pacing
        if phase in ("late", "final") and budget_ratio > 0.4:
            aggression = min(aggression + 0.2, 1.0)
            budget_guidance = (
                f"OVERFUNDED: {budget_ratio:.0%} of pool remaining as budget. "
                "Bid aggressively -- unspent money is wasted."
            )
        elif phase in ("early", "middle") and budget_ratio < 0.15:
            aggression = max(aggression - 0.2, 0.1)
            budget_guidance = (
                f"UNDERFUNDED: only {budget_ratio:.0%} of pool left as budget. "
                "Be very selective -- save for must-have targets."
            )
        else:
            budget_guidance = f"On pace. {budget_ratio:.0%} of pool available."

        # Adjust for portfolio composition
        if not has_elite and phase in ("middle", "late"):
            aggression = min(aggression + 0.15, 1.0)
            target_tier = (
                "PRIORITY: You have no elite golfer. Target a top-15 player "
                "as your anchor -- a portfolio without upside can't win big."
            )

        # Sharp bidder intelligence
        sharp_intel = "No data on other sharp bidders."
        if sharp_bidder_portfolios:
            sharp_needs = []
            for bidder, their_portfolio in sharp_bidder_portfolios.items():
                their_invested = sum(p.get("purchase_price", 0) for p in their_portfolio)
                has_their_elite = any(
                    p.get("model_win_prob", 0) > 0.05 for p in their_portfolio
                )
                if not has_their_elite:
                    sharp_needs.append(f"{bidder} still needs an elite anchor")
                elif their_invested < total_pool * 0.05:
                    sharp_needs.append(f"{bidder} has dry powder - expect competition")

            if sharp_needs:
                sharp_intel = " | ".join(sharp_needs)
            else:
                sharp_intel = "Sharp bidders appear well-positioned. Expect less competition for remaining golfers."

        # Key recommendation
        if phase == "final" and remaining_bankroll > 50:
            key_rec = (
                f"SPEND YOUR MONEY. You have ${remaining_bankroll:.0f} left with "
                f"{num_remaining} golfers remaining. Buy the best available EV."
            )
        elif not has_elite and num_owned < 3:
            key_rec = (
                "Build a barbell: one elite anchor (worth overpaying slightly) "
                "plus multiple undervalued mid-tier/longshot plays."
            )
        elif num_owned >= 5:
            key_rec = (
                f"Portfolio is filling up ({num_owned} golfers). "
                "Only bid on clear mispricing from here."
            )
        else:
            key_rec = (
                f"Phase: {phase}. Aggression: {aggression:.0%}. "
                "Stick to model valuations, don't chase."
            )

        return {
            "aggression_level": round(aggression, 2),
            "target_tier": target_tier,
            "budget_guidance": budget_guidance,
            "sharp_bidder_intel": sharp_intel,
            "key_recommendation": key_rec,
            "portfolio_summary": {
                "num_owned": num_owned,
                "total_invested": round(total_invested, 2),
                "has_elite": has_elite,
                "has_mid_tier": has_mid,
                "remaining_bankroll": round(remaining_bankroll, 2),
            },
        }
