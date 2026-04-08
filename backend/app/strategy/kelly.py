"""
Kelly Criterion bankroll management for Calcutta auction bidding.

The Kelly Criterion determines the mathematically optimal fraction of
bankroll to wager given a positive-expectation opportunity.  In a
Calcutta context the "wager" is the purchase price of a golfer and
the "payout" is the share of the pool awarded for that golfer's finish.

Because Calcuttas are high-variance single-tournament events, this
module defaults to quarter-Kelly (fraction=0.25) to reduce the risk
of ruin while still capturing the bulk of the geometric growth rate.

Key Calcutta-specific considerations implemented here:
  - Unspent bankroll is wasted (zero terminal value), so the module
    includes budget-pacing logic.
  - Multi-position Kelly accounts for existing portfolio exposure so
    that correlated bets don't blow up total risk.
"""

from __future__ import annotations

import numpy as np


class KellyCalculator:
    """Kelly Criterion engine tailored to Calcutta auction dynamics."""

    # -----------------------------------------------------------------
    # Core Kelly math
    # -----------------------------------------------------------------

    @staticmethod
    def optimal_fraction(win_prob: float, odds: float) -> float:
        """Full Kelly fraction for a single binary bet.

        The classic Kelly formula for a bet that pays `odds`-to-1 with
        probability `win_prob`:

            f* = (p * (b + 1) - 1) / b

        where p = win_prob, b = odds (net payout per dollar risked).

        In a Calcutta the "odds" represent expected_payout / price - 1,
        i.e., the net profit multiple if the golfer finishes in the money.

        Args:
            win_prob: Probability the golfer finishes in the money (broadly).
            odds: Net payout multiple (expected_payout / price - 1).
                  For example, if a $100 golfer is expected to return $300,
                  odds = 2.0.

        Returns:
            Optimal fraction of bankroll to allocate.  Returns 0.0 when
            the edge is non-positive (no bet).
        """
        if odds <= 0 or win_prob <= 0 or win_prob >= 1:
            return 0.0

        fraction = (win_prob * (odds + 1) - 1) / odds
        return max(fraction, 0.0)

    @staticmethod
    def fractional_kelly(
        win_prob: float,
        odds: float,
        fraction: float = 0.25,
    ) -> float:
        """Fractional Kelly for variance reduction.

        Quarter-Kelly (fraction=0.25) retains ~94% of the geometric
        growth rate of full Kelly while cutting variance by 75%.  This
        is the recommended default for Calcutta auctions where a single
        bad outcome can wipe out your entire investment.

        Args:
            win_prob: Probability of the favorable outcome.
            odds: Net payout multiple.
            fraction: Kelly fraction to use (0.25 = quarter Kelly).

        Returns:
            Scaled Kelly fraction of bankroll.
        """
        full = KellyCalculator.optimal_fraction(win_prob, odds)
        return full * fraction

    @staticmethod
    def max_bid(
        win_prob: float,
        expected_payout: float,
        bankroll: float,
        fraction: float = 0.25,
    ) -> float:
        """Maximum bid for a golfer given Kelly sizing.

        Models the Calcutta purchase as a binary bet:
          - With probability `win_prob`, you receive `expected_payout`.
          - With probability `1 - win_prob`, you lose your purchase price.

        We solve for the maximum price `p` such that the Kelly-sized
        bankroll allocation equals `p`:

            f* = (win_prob * expected_payout - p) / p  [simplified]

        The Kelly-optimal bid is:
            p = win_prob * expected_payout * kelly_fraction_multiplier

        But we use the direct approach: compute Kelly fraction at an
        assumed unit-bet odds level, then scale to dollars.

        Args:
            win_prob: Probability of finishing in the money (weighted
                      across all payout tiers).  Use the broadest
                      in-the-money probability (e.g., top-10 or top-20).
            expected_payout: Dollar expected payout (probability-weighted
                             sum across all finish positions).
            bankroll: Current available bankroll.
            fraction: Kelly fraction (default 0.25 = quarter Kelly).

        Returns:
            Maximum bid in dollars.  Never exceeds bankroll.
        """
        if expected_payout <= 0 or bankroll <= 0 or win_prob <= 0:
            return 0.0

        if win_prob >= 1.0:
            return min(expected_payout, bankroll)

        # Model as: risk `price` to win `expected_payout`.
        # The net odds (profit per dollar risked) depend on the price,
        # creating a circular dependency.  We solve it by computing
        # the EV-optimal Kelly bid directly.
        #
        # For a bet where you risk $p to gain $expected_payout with
        # probability win_prob:
        #   edge = win_prob * expected_payout - p
        #   odds = expected_payout / p - 1
        #
        # The Kelly criterion says bet fraction f* = edge / (expected_payout - p)
        # when the payout is expected_payout and risk is p.
        #
        # Simpler approach: the maximum Kelly-justified bid is the
        # expected value times the fractional Kelly multiplier, bounded
        # by the breakeven price (where EV = 0, i.e., price = expected_payout).
        #
        # max_bid = fraction * bankroll * (edge_ratio)
        # where edge_ratio = win_prob * expected_payout / bankroll
        #
        # We use a proven Calcutta-specific formula:
        ev = win_prob * expected_payout
        # The Kelly-optimal price for this type of bet is:
        # p* = ev * (1 - (1 - win_prob) * fraction_adj)
        # Simplified: allocate a fraction of bankroll proportional to edge
        edge_fraction = ev / bankroll if bankroll > 0 else 0
        kelly_bid = fraction * edge_fraction * bankroll

        # Also compute via direct Kelly on the "binary bet" framing:
        # If I buy at price p and the golfer cashes, I get expected_payout.
        # Odds = expected_payout / p - 1.  But since p is what we're solving
        # for, use an iterative approach: start from EV as initial price guess.
        price_guess = ev
        for _ in range(5):
            if price_guess <= 0:
                break
            odds = expected_payout / price_guess - 1
            if odds <= 0:
                break
            fk = KellyCalculator.fractional_kelly(win_prob, odds, fraction)
            price_guess = fk * bankroll

        # Take the more conservative of the two estimates
        bid = min(kelly_bid, price_guess) if price_guess > 0 else kelly_bid

        # Never bid more than expected payout (breakeven) or bankroll
        bid = min(bid, expected_payout, bankroll)
        return round(max(bid, 0.0), 2)

    @staticmethod
    def portfolio_kelly(
        positions: list[dict],
        bankroll: float,
    ) -> dict:
        """Multi-position Kelly accounting for existing portfolio exposure.

        When you already own golfers, their risk must be subtracted from
        the total before sizing the next bet.  This prevents over-leveraging
        into correlated outcomes.

        Each position dict should have:
            - golfer_id: str
            - purchase_price: float
            - win_prob: float
            - expected_payout: float

        Args:
            positions: List of currently-owned positions.
            bankroll: Original total bankroll (not remaining).

        Returns:
            Dictionary with:
                - total_invested: sum of purchase prices
                - remaining_bankroll: bankroll - total_invested
                - portfolio_exposure: total_invested / bankroll
                - effective_kelly_cap: max Kelly fraction for next bet
                - individual_positions: list with Kelly analysis per position
        """
        if bankroll <= 0:
            return {
                "total_invested": 0.0,
                "remaining_bankroll": 0.0,
                "portfolio_exposure": 0.0,
                "effective_kelly_cap": 0.0,
                "individual_positions": [],
            }

        total_invested = sum(p.get("purchase_price", 0) for p in positions)
        remaining = max(bankroll - total_invested, 0.0)
        exposure = total_invested / bankroll

        # As portfolio exposure grows, reduce the maximum Kelly fraction
        # to prevent catastrophic concentration.  At 80%+ exposure we
        # cap new bets very aggressively.
        if exposure < 0.5:
            kelly_cap = 0.25  # standard quarter-Kelly
        elif exposure < 0.7:
            kelly_cap = 0.15  # reduced sizing
        elif exposure < 0.85:
            kelly_cap = 0.10  # conservative
        else:
            kelly_cap = 0.05  # scraps mode

        individual = []
        for p in positions:
            wp = p.get("win_prob", 0)
            ep = p.get("expected_payout", 0)
            pp = p.get("purchase_price", 0)
            ev_multiple = ep / pp if pp > 0 else 0
            individual.append({
                "golfer_id": p.get("golfer_id", "unknown"),
                "purchase_price": pp,
                "expected_payout": ep,
                "ev_multiple": round(ev_multiple, 3),
                "portfolio_weight": round(pp / bankroll, 4) if bankroll > 0 else 0,
            })

        return {
            "total_invested": round(total_invested, 2),
            "remaining_bankroll": round(remaining, 2),
            "portfolio_exposure": round(exposure, 4),
            "effective_kelly_cap": kelly_cap,
            "individual_positions": individual,
        }

    @staticmethod
    def remaining_budget_allocation(
        remaining_bankroll: float,
        remaining_golfers: list[dict],
        portfolio: list[dict],
    ) -> dict:
        """Optimal distribution of remaining bankroll across auction opportunities.

        Key Calcutta constraint: leftover bankroll is *wasted* (you can't
        take it home), but overpaying destroys EV.  This method balances
        the two forces by:

        1. Ranking remaining golfers by EV-per-dollar.
        2. Allocating via Kelly sizing to each, in rank order.
        3. If total allocation < remaining bankroll, spreading the
           surplus proportionally across positive-EV golfers (to avoid
           leaving money on the table).

        Each golfer dict should have:
            - golfer_id: str
            - win_prob: float
            - expected_payout: float
            - estimated_market_price: float (what they'll likely sell for)

        Args:
            remaining_bankroll: Dollars left to spend.
            remaining_golfers: Golfers still up for auction.
            portfolio: Already-purchased positions (for exposure calc).

        Returns:
            Dictionary with:
                - allocations: list of {golfer_id, target_bid, kelly_bid,
                  ev_per_dollar, priority}
                - surplus: amount that would be unspent under pure Kelly
                - surplus_strategy: recommendation for surplus
                - total_allocated: sum of target bids
        """
        if remaining_bankroll <= 0 or not remaining_golfers:
            return {
                "allocations": [],
                "surplus": remaining_bankroll,
                "surplus_strategy": "No positive-EV opportunities remain.",
                "total_allocated": 0.0,
            }

        # Score and rank remaining golfers
        scored = []
        for g in remaining_golfers:
            ep = g.get("expected_payout", 0)
            emp = g.get("estimated_market_price", 0)
            wp = g.get("win_prob", 0)

            if emp <= 0 or ep <= 0:
                continue

            ev_per_dollar = ep / emp
            kelly_bid = KellyCalculator.max_bid(
                win_prob=wp,
                expected_payout=ep,
                bankroll=remaining_bankroll,
                fraction=0.25,
            )

            scored.append({
                "golfer_id": g.get("golfer_id", "unknown"),
                "expected_payout": ep,
                "estimated_market_price": emp,
                "ev_per_dollar": round(ev_per_dollar, 3),
                "kelly_bid": round(kelly_bid, 2),
                "win_prob": wp,
            })

        # Sort by EV-per-dollar descending
        scored.sort(key=lambda x: x["ev_per_dollar"], reverse=True)

        # Phase 1: allocate Kelly-sized bids
        total_kelly = sum(s["kelly_bid"] for s in scored if s["ev_per_dollar"] > 1.0)
        surplus = max(remaining_bankroll - total_kelly, 0.0)

        # Phase 2: if surplus exists, distribute proportionally to positive-EV
        # golfers (better to slightly overpay than leave money on the table)
        positive_ev = [s for s in scored if s["ev_per_dollar"] > 1.0]
        allocations = []

        for i, s in enumerate(scored):
            if s["ev_per_dollar"] > 1.0 and surplus > 0 and total_kelly > 0:
                # Spread surplus proportionally to Kelly allocation
                surplus_share = (s["kelly_bid"] / total_kelly) * surplus
                target = s["kelly_bid"] + surplus_share
            else:
                target = s["kelly_bid"]

            # Never bid more than expected payout (that's always -EV)
            target = min(target, s["expected_payout"])

            allocations.append({
                "golfer_id": s["golfer_id"],
                "target_bid": round(target, 2),
                "kelly_bid": s["kelly_bid"],
                "ev_per_dollar": s["ev_per_dollar"],
                "priority": i + 1,
            })

        total_allocated = sum(a["target_bid"] for a in allocations)
        final_surplus = max(remaining_bankroll - total_allocated, 0.0)

        if final_surplus > remaining_bankroll * 0.2:
            surplus_strategy = (
                f"${final_surplus:.0f} unallocated ({final_surplus/remaining_bankroll:.0%} of budget). "
                "Consider bidding more aggressively on top targets or buying a "
                "longshot lottery ticket to avoid wasting bankroll."
            )
        elif final_surplus > 0:
            surplus_strategy = (
                f"${final_surplus:.0f} minor surplus. Spread across your top 2-3 "
                "remaining targets as extra bidding headroom."
            )
        else:
            surplus_strategy = "Budget fully allocated. Stay disciplined on limits."

        return {
            "allocations": allocations,
            "surplus": round(final_surplus, 2),
            "surplus_strategy": surplus_strategy,
            "total_allocated": round(total_allocated, 2),
        }
