"""Betting odds aggregation scraper.

Data source strategy:
- Primary: The Odds API (free tier: 500 requests/month)
  URL: https://api.the-odds-api.com/v4/sports/golf_masters_tournament_winner/odds
  Provides odds from DraftKings, FanDuel, BetMGM, Caesars, etc.
  API key required: ODDS_API_KEY env var.

- Secondary: OddsShark / VegasInsider scraping
  URL: https://www.vegasinsider.com/golf/odds/futures/
  Requires HTML parsing; less reliable but free.

- Tertiary: Pinnacle API (sharp odds, best for consensus)
  Pinnacle lines are considered the sharpest in the market.

Key outputs:
- Decimal odds from multiple sportsbooks
- Average/consensus odds across books
- Implied probability from consensus
- Line movement tracking (odds change over time)
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from typing import Any

import httpx
import pandas as pd

from app.data.scrapers.base import DataScraper
from app.models.probability import implied_probability_from_odds, remove_vig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The Odds API integration
# ---------------------------------------------------------------------------

_ODDS_API_BASE = "https://api.the-odds-api.com/v4/sports/golf_masters_tournament_winner/odds/"


class TheOddsAPIScraper(DataScraper):
    """Live scraper that pulls Masters outright winner odds from The Odds API.

    Requires an API key (free tier: 500 requests/month).
    Set via constructor arg or ODDS_API_KEY environment variable.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("ODDS_API_KEY", "")

    async def fetch(self) -> Any:
        """Fetch current betting odds from The Odds API.

        Returns the raw JSON response (list of bookmaker data) or an empty
        list on failure.
        """
        if not self.api_key:
            logger.warning("No ODDS_API_KEY set -- cannot fetch live odds")
            return []

        params = {
            "apiKey": self.api_key,
            "regions": "us",
            "markets": "outrights",
            "oddsFormat": "american",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(_ODDS_API_BASE, params=params)
                resp.raise_for_status()
                data = resp.json()
                # Log remaining quota from response headers
                remaining = resp.headers.get("x-requests-remaining", "?")
                used = resp.headers.get("x-requests-used", "?")
                logger.info(
                    "The Odds API call succeeded -- requests used: %s, remaining: %s",
                    used,
                    remaining,
                )
                return data
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 401:
                logger.error("The Odds API: invalid API key")
            elif status == 429:
                logger.error("The Odds API: rate limit exceeded (500/month free tier)")
            else:
                logger.error("The Odds API HTTP error: %s", status)
            return []
        except httpx.RequestError as exc:
            logger.error("The Odds API request failed: %s", exc)
            return []

    def parse(self, raw_data: Any) -> list[dict]:
        """Parse The Odds API response into flat records.

        Each record: {player_name, american_odds, implied_prob, bookmaker}
        """
        if not isinstance(raw_data, list):
            return []

        records: list[dict] = []
        for event in raw_data:
            bookmakers = event.get("bookmakers", [])
            for book in bookmakers:
                bookmaker_name = book.get("title", "unknown")
                markets = book.get("markets", [])
                for market in markets:
                    if market.get("key") != "outrights":
                        continue
                    for outcome in market.get("outcomes", []):
                        name = outcome.get("name", "")
                        price = outcome.get("price")
                        if name and price is not None:
                            try:
                                odds_int = int(price)
                                imp = implied_probability_from_odds(odds_int)
                            except (ValueError, TypeError):
                                continue
                            records.append(
                                {
                                    "player_name": name,
                                    "american_odds": odds_int,
                                    "implied_prob": imp,
                                    "bookmaker": bookmaker_name,
                                }
                            )
        return records

    def validate(self, parsed_data: list[dict]) -> bool:
        """Validate parsed odds records."""
        if not parsed_data:
            return False
        for rec in parsed_data:
            if not rec.get("player_name") or rec.get("implied_prob") is None:
                return False
            if not (0 < rec["implied_prob"] < 1):
                return False
        return True

    def to_dataframe(self, parsed_data: list[dict]) -> pd.DataFrame:
        """Convert to DataFrame with columns: name, american_odds, implied_prob, bookmaker."""
        if not parsed_data:
            return pd.DataFrame(columns=["name", "american_odds", "implied_prob", "bookmaker"])
        df = pd.DataFrame(parsed_data)
        df = df.rename(columns={"player_name": "name"})
        return df[["name", "american_odds", "implied_prob", "bookmaker"]]


# ---------------------------------------------------------------------------
# Consensus odds helper
# ---------------------------------------------------------------------------


async def get_consensus_odds(api_key: str | None = None) -> dict[str, float]:
    """Fetch live odds and return vig-removed consensus win probabilities.

    Returns:
        dict mapping golfer_name -> consensus_win_prob (float in [0,1]).
        Empty dict if the API key is missing or the request fails.
    """
    scraper = TheOddsAPIScraper(api_key=api_key)
    raw = await scraper.fetch()
    parsed = scraper.parse(raw)

    if not parsed:
        logger.warning("get_consensus_odds: no odds data available")
        return {}

    # Average implied probs across bookmakers per golfer
    golfer_probs: dict[str, list[float]] = defaultdict(list)
    for rec in parsed:
        golfer_probs[rec["player_name"]].append(rec["implied_prob"])

    avg_implied: dict[str, float] = {
        name: sum(probs) / len(probs) for name, probs in golfer_probs.items()
    }

    # Remove vig: scale so probabilities sum to 1.0
    names = list(avg_implied.keys())
    raw_probs = [avg_implied[n] for n in names]

    try:
        true_probs = remove_vig(raw_probs)
    except ValueError:
        logger.error("get_consensus_odds: vig removal failed")
        return {}

    return {name: prob for name, prob in zip(names, true_probs)}


# ---------------------------------------------------------------------------
# Legacy placeholder scraper (kept for backwards compatibility)
# ---------------------------------------------------------------------------


class BettingOddsScraper(DataScraper):
    """Scraper for golf tournament betting odds.

    To connect to real data:
    1. Set ODDS_API_KEY env var
    2. fetch() calls The Odds API for Masters outright winner odds
    3. parse() averages across sportsbooks for consensus
    4. Implied probability = 1 / decimal_odds (after vig removal)

    The Odds API integration:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.the-odds-api.com/v4/sports/golf_masters_tournament_winner/odds",
                params={
                    "apiKey": os.environ["ODDS_API_KEY"],
                    "regions": "us",
                    "markets": "outrights",
                    "oddsFormat": "decimal",
                },
            )
            return resp.json()
    """

    async def fetch(self) -> Any:
        """Fetch current betting odds from multiple sportsbooks."""
        return self.get_placeholder_data()

    def parse(self, raw_data: Any) -> list[dict]:
        """Parse odds data, averaging across books."""
        if isinstance(raw_data, list):
            return raw_data
        return []

    def validate(self, parsed_data: list[dict]) -> bool:
        """Validate odds data.

        Checks:
        - Each record has player_name and decimal_odds
        - Odds are positive numbers > 1.0
        - Implied probabilities sum to roughly 1.0 (with vig)
        """
        if not parsed_data:
            return False
        total_implied = 0.0
        for record in parsed_data:
            if "player_name" not in record or "decimal_odds" not in record:
                return False
            if record["decimal_odds"] < 1.0:
                return False
            total_implied += 1.0 / record["decimal_odds"]
        # With vig, total implied should be 1.0 to ~1.3
        return 0.8 <= total_implied <= 1.5

    def to_dataframe(self, parsed_data: list[dict]) -> pd.DataFrame:
        """Convert to DataFrame with implied probability column."""
        df = pd.DataFrame(parsed_data)
        if "decimal_odds" in df.columns:
            df["implied_prob"] = 1.0 / df["decimal_odds"]
        return df

    @staticmethod
    def get_placeholder_data() -> list[dict]:
        """Return realistic betting odds for model development."""
        return [
            {"player_name": "Scottie Scheffler", "decimal_odds": 5.0, "draftkings": 4.8, "fanduel": 5.0, "betmgm": 5.2},
            {"player_name": "Xander Schauffele", "decimal_odds": 10.0, "draftkings": 9.5, "fanduel": 10.0, "betmgm": 10.5},
            {"player_name": "Rory McIlroy", "decimal_odds": 12.0, "draftkings": 11.0, "fanduel": 12.0, "betmgm": 13.0},
            {"player_name": "Jon Rahm", "decimal_odds": 14.0, "draftkings": 13.0, "fanduel": 14.0, "betmgm": 15.0},
            {"player_name": "Collin Morikawa", "decimal_odds": 16.0, "draftkings": 15.0, "fanduel": 16.0, "betmgm": 17.0},
            {"player_name": "Ludvig Aberg", "decimal_odds": 18.0, "draftkings": 17.0, "fanduel": 18.0, "betmgm": 19.0},
            {"player_name": "Bryson DeChambeau", "decimal_odds": 20.0, "draftkings": 19.0, "fanduel": 20.0, "betmgm": 21.0},
            {"player_name": "Jordan Spieth", "decimal_odds": 40.0, "draftkings": 35.0, "fanduel": 40.0, "betmgm": 45.0},
            {"player_name": "Tiger Woods", "decimal_odds": 100.0, "draftkings": 80.0, "fanduel": 100.0, "betmgm": 120.0},
        ]
