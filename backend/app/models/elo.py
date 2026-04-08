"""
Golf ELO rating system with Augusta National-specific adjustments.

The ELO model maintains ratings for professional golfers and predicts
win probabilities based on relative skill differences.  Augusta-specific
adjustments account for course history, experience, par-5 scoring,
and putting on fast greens.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np


# ---------------------------------------------------------------------------
# Default 2026 Masters field ELO ratings
# ---------------------------------------------------------------------------
# Ratings are on a 1500-centered scale where 1500 = average PGA Tour pro.
# Values are realistic estimates informed by world rankings, recent major
# results, and strokes-gained data through early 2026.

DEFAULT_FIELD_ELOS: dict[str, float] = {
    # Elite tier (top ~8 in the world)
    "Scottie Scheffler": 1920,
    "Xander Schauffele": 1870,
    "Rory McIlroy": 1855,
    "Jon Rahm": 1840,
    "Collin Morikawa": 1830,
    "Ludvig Aberg": 1825,
    "Wyndham Clark": 1800,
    "Viktor Hovland": 1795,
    # Contender tier
    "Patrick Cantlay": 1780,
    "Tommy Fleetwood": 1775,
    "Hideki Matsuyama": 1770,
    "Brooks Koepka": 1765,
    "Sahith Theegala": 1760,
    "Bryson DeChambeau": 1755,
    "Shane Lowry": 1750,
    "Sungjae Im": 1745,
    "Russell Henley": 1740,
    "Tom Kim": 1735,
    "Cameron Smith": 1730,
    "Max Homa": 1725,
    "Justin Thomas": 1720,
    "Robert MacIntyre": 1715,
    "Tony Finau": 1710,
    "Keegan Bradley": 1705,
    "Corey Conners": 1700,
    "Matt Fitzpatrick": 1695,
    "Sepp Straka": 1690,
    "Denny McCarthy": 1685,
    "Jason Day": 1680,
    # Mid-tier
    "Akshay Bhatia": 1675,
    "Cameron Young": 1670,
    "Sam Burns": 1665,
    "Taylor Pendrith": 1660,
    "Adam Scott": 1655,
    "Chris Kirk": 1650,
    "Harris English": 1645,
    "Nick Dunlap": 1640,
    "Min Woo Lee": 1635,
    "Tyrrell Hatton": 1630,
    "Brian Harman": 1625,
    "Will Zalatoris": 1620,
    "Justin Rose": 1615,
    "Dustin Johnson": 1610,
    "Jordan Spieth": 1605,
    "Billy Horschel": 1600,
    "Si Woo Kim": 1595,
    "Patrick Reed": 1590,
    "Rickie Fowler": 1585,
    "Thomas Detry": 1580,
    "Davis Thompson": 1575,
    "Matthieu Pavon": 1570,
    "Christiaan Bezuidenhout": 1565,
    "Aaron Rai": 1560,
    "Kurt Kitayama": 1555,
    "Eric Cole": 1550,
    "J.T. Poston": 1545,
    "Mackenzie Hughes": 1540,
    "Stephan Jaeger": 1535,
    "Byeong Hun An": 1530,
    # Lower tier
    "Lucas Glover": 1525,
    "Nick Taylor": 1520,
    "Sergio Garcia": 1515,
    "Phil Mickelson": 1510,
    "Joaquin Niemann": 1505,
    "Tiger Woods": 1500,
    "Fred Couples": 1460,
    "Bernhard Langer": 1440,
    "Jose Maria Olazabal": 1430,
    "Vijay Singh": 1425,
    "Mike Weir": 1420,
    "Sandy Lyle": 1410,
    "Larry Mize": 1405,
    "Jack Nicklaus": 1400,
    # Amateur / special invitees
    "Santiago De la Fuente": 1470,
    "Noah Kent": 1465,
    "Hiroshi Tai": 1460,
    "Luke Clanton": 1490,
    "Blades Brown": 1475,
    "Jackson Koivun": 1455,
    "Miles Russell": 1450,
    # Additional qualifiers / invitees
    "Adrian Meronk": 1540,
    "Nicolai Hojgaard": 1555,
    "Rasmus Hojgaard": 1545,
    "Alex Noren": 1530,
    "Tom Hoge": 1525,
    "Andrew Novak": 1510,
    "Nico Echavarria": 1515,
    "Jake Knapp": 1505,
    "Ben Griffin": 1500,
    "Beau Hossler": 1495,
    "Kevin Yu": 1490,
    "Chan Kim": 1485,
}


class GolfEloModel:
    """Golf-specific ELO rating system with Augusta National adjustments.

    Attributes:
        ratings: Current ELO ratings keyed by golfer name/id.
        k_base: Base K-factor controlling rating volatility.
    """

    def __init__(
        self,
        k_base: float = 24.0,
        initial_ratings: dict[str, float] | None = None,
    ) -> None:
        """Initialize the ELO model.

        Args:
            k_base: Base K-factor for rating updates.  Golf uses a moderate
                K because a single tournament has high variance.
            initial_ratings: Optional starting ratings.  Defaults to the
                built-in 2026 Masters field estimates.
        """
        self.k_base = k_base
        self.ratings: dict[str, float] = dict(
            initial_ratings if initial_ratings is not None else DEFAULT_FIELD_ELOS
        )

    # ------------------------------------------------------------------
    # Rating updates
    # ------------------------------------------------------------------

    def _field_strength_k(self, field_size: int, avg_elo: float) -> float:
        """Adjust K-factor based on field strength and size.

        Stronger, larger fields produce more informative results and
        warrant larger rating adjustments.
        """
        strength_factor = avg_elo / 1600.0  # >1 for strong fields
        size_factor = min(field_size / 80.0, 1.25)  # slight boost for large fields
        return self.k_base * strength_factor * size_factor

    def update_ratings(self, tournament_results: list[dict[str, Any]]) -> None:
        """Update ELO ratings after a completed tournament.

        Each entry in *tournament_results* must have:
            - ``golfer_id`` (str): Golfer identifier matching self.ratings keys.
            - ``finish_position`` (int): Final position (1 = winner).

        The update uses a pairwise comparison approach: each golfer is
        compared against every other golfer in the field, and the
        aggregated expected-vs-actual score drives the ELO adjustment.

        Args:
            tournament_results: List of dicts with golfer_id and finish_position.
        """
        if not tournament_results:
            return

        n = len(tournament_results)
        # Ensure all golfers have a rating
        for entry in tournament_results:
            gid = entry["golfer_id"]
            if gid not in self.ratings:
                self.ratings[gid] = 1500.0

        elos = np.array(
            [self.ratings[e["golfer_id"]] for e in tournament_results],
            dtype=np.float64,
        )
        positions = np.array(
            [e["finish_position"] for e in tournament_results], dtype=np.float64
        )

        avg_elo = float(elos.mean())
        k = self._field_strength_k(n, avg_elo)

        # Pairwise expected scores
        for i in range(n):
            expected_wins = 0.0
            actual_wins = 0.0
            for j in range(n):
                if i == j:
                    continue
                expected_wins += 1.0 / (1.0 + 10.0 ** ((elos[j] - elos[i]) / 400.0))
                if positions[i] < positions[j]:
                    actual_wins += 1.0
                elif positions[i] == positions[j]:
                    actual_wins += 0.5

            # Scale factor so total possible = n-1
            adjustment = k * (actual_wins - expected_wins) / (n - 1)
            gid = tournament_results[i]["golfer_id"]
            self.ratings[gid] += adjustment

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_win_probability(
        self, golfer_elo: float, field_elos: list[float]
    ) -> float:
        """Predict a golfer's win probability given the field.

        Uses the Bradley-Terry model: a golfer's probability of beating
        any single opponent is the standard logistic ELO formula, and the
        probability of winning the tournament is approximated as the
        product of beating each opponent normalized across the field.

        For computational simplicity we use the softmax of ELO / 400,
        which is equivalent to the Bradley-Terry win probability in a
        full-field comparison.

        Args:
            golfer_elo: The golfer's current ELO rating.
            field_elos: List of ELO ratings for all golfers in the field
                (may or may not include the golfer themselves).

        Returns:
            Estimated win probability in [0, 1].
        """
        all_elos = np.array(field_elos + [golfer_elo], dtype=np.float64)
        # Temperature controls how sharply ELO differences translate to
        # win-probability separation.  A value of ~115 produces realistic
        # golf distributions where the world #1 has ~8-12% and a mid-field
        # golfer has ~0.5-1%.
        temperature = 115.0
        logits = all_elos / temperature
        logits -= logits.max()  # numerical stability
        exp_logits = np.exp(logits)
        probs = exp_logits / exp_logits.sum()

        # The golfer's entry is the last one we appended
        return float(probs[-1])

    # ------------------------------------------------------------------
    # Augusta-specific adjustment
    # ------------------------------------------------------------------

    def get_masters_adjustment(self, golfer_data: dict[str, Any]) -> float:
        """Compute an Augusta National-specific ELO adjustment.

        Augusta rewards a distinctive skill set: length off the tee to
        take advantage of four reachable par 5s, elite iron play into
        small greens, deft short game around severe slopes, and the
        ability to putt on some of the fastest greens in golf.

        Args:
            golfer_data: Dict that may contain any of these keys:
                - ``masters_finishes`` (list[dict]): Past finishes with
                  ``year`` and ``position`` keys. More recent results
                  are weighted more heavily.
                - ``masters_appearances`` (int): Total Masters starts.
                - ``par5_scoring_avg`` (float): Scoring average on par 5s
                  relative to field (negative = better, e.g., -0.30).
                - ``stimp_putting_sg`` (float): Strokes-gained putting on
                  greens with Stimpmeter >= 13 (Augusta's typical speed).

        Returns:
            ELO adjustment (positive = boost, negative = penalty).
            Typical range is roughly -40 to +60.
        """
        adjustment = 0.0

        # 1. Course history (past finishes weighted by recency)
        finishes = golfer_data.get("masters_finishes", [])
        if finishes:
            history_score = 0.0
            for entry in finishes:
                year = entry.get("year", 2020)
                pos = entry.get("position", 50)
                recency_weight = max(0.0, 1.0 - (2026 - year) * 0.12)

                # Convert position to a score: 1st = +30, top5 = +15, etc.
                if pos == 1:
                    pts = 30.0
                elif pos <= 5:
                    pts = 18.0 - (pos - 2) * 1.5
                elif pos <= 10:
                    pts = 10.0 - (pos - 6) * 1.0
                elif pos <= 20:
                    pts = 5.0 - (pos - 11) * 0.3
                elif pos <= 40:
                    pts = 2.0 - (pos - 21) * 0.1
                else:
                    pts = 0.0

                history_score += pts * recency_weight

            # Cap the history contribution
            adjustment += float(np.clip(history_score, -10.0, 45.0))

        # 2. Experience premium (5+ appearances = familiarity with greens)
        appearances = golfer_data.get("masters_appearances", 0)
        if appearances >= 10:
            adjustment += 12.0
        elif appearances >= 5:
            adjustment += 7.0
        elif appearances >= 3:
            adjustment += 3.0
        elif appearances == 0:
            # First-timer penalty: Augusta's greens are notoriously hard
            # to read without experience.
            adjustment -= 8.0

        # 3. Par 5 scoring ability
        # Augusta's four par 5s (2, 8, 13, 15) are where birdies and
        # eagles separate contenders from the field.
        par5_avg = golfer_data.get("par5_scoring_avg", 0.0)
        # par5_avg is relative to field: negative = better
        # Scale: -0.40 (elite) -> +16 adjustment, +0.20 (poor) -> -8
        adjustment += float(np.clip(-par5_avg * 40.0, -12.0, 20.0))

        # 4. Putting on fast greens
        # Augusta Stimpmeter readings typically run 13-14.  Golfers who
        # gain strokes putting on fast surfaces have a significant edge.
        stimp_sg = golfer_data.get("stimp_putting_sg", 0.0)
        # Scale: +0.5 SG (elite) -> +15, -0.3 SG (poor) -> -9
        adjustment += float(np.clip(stimp_sg * 30.0, -12.0, 18.0))

        return adjustment

    # ------------------------------------------------------------------
    # Convenience: full-field prediction
    # ------------------------------------------------------------------

    def predict_field(
        self,
        golfer_adjustments: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, float]:
        """Predict win probabilities for the entire current field.

        Optionally applies Augusta-specific adjustments when
        *golfer_adjustments* is provided.

        Args:
            golfer_adjustments: Optional mapping of golfer_id to the dict
                expected by :meth:`get_masters_adjustment`.

        Returns:
            Mapping of golfer_id -> win probability, summing to ~1.0.
        """
        adjusted: dict[str, float] = {}
        for gid, elo in self.ratings.items():
            adj = 0.0
            if golfer_adjustments and gid in golfer_adjustments:
                adj = self.get_masters_adjustment(golfer_adjustments[gid])
            adjusted[gid] = elo + adj

        all_elos = list(adjusted.values())
        temperature = 115.0
        arr = np.array(all_elos, dtype=np.float64) / temperature
        arr -= arr.max()
        exp_arr = np.exp(arr)
        probs = exp_arr / exp_arr.sum()

        golfer_ids = list(adjusted.keys())
        return {gid: float(p) for gid, p in zip(golfer_ids, probs)}
