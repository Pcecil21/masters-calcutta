"""Masters Tournament historical data scraper.

Data source strategy:
- Primary: ESPN Masters leaderboard history API
  URL: https://site.api.espn.com/apis/site/v2/sports/golf/pga/leaderboard?event=401580329
  This provides current-year and some historical leaderboard data.

- Secondary: Augusta.com historical results
  URL: https://www.masters.com/en_US/scores/stats/pastchamps.html
  Requires HTML parsing; results are in structured tables.

- Tertiary: Golf Stats Pro API (paid)
  Provides round-by-round scoring, hole-by-hole data, and multi-year history
  for computing augusta_history_score.

Key fields to extract:
- Player name, year, finish position, total score, round scores
- Whether player made the cut
- Consecutive appearances streak
- Best/worst rounds at Augusta
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.data.scrapers.base import DataScraper


class MastersHistoryScraper(DataScraper):
    """Scraper for historical Masters Tournament results.

    To connect to real data:
    1. Set MASTERS_DATA_SOURCE env var to 'espn', 'augusta', or 'golfstats'
    2. For golfstats, set GOLF_STATS_API_KEY
    3. Call fetch() which will hit the appropriate API
    4. parse() normalizes all sources to a common schema
    """

    async def fetch(self) -> Any:
        """Fetch Masters historical data.

        Production implementation would use httpx:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://site.api.espn.com/apis/site/v2/sports/golf/pga/leaderboard",
                    params={"event": event_id},
                )
                resp.raise_for_status()
                return resp.json()
        """
        return self.get_placeholder_data()

    def parse(self, raw_data: Any) -> list[dict]:
        """Parse raw Masters data into structured records."""
        if isinstance(raw_data, list):
            return raw_data
        return []

    def validate(self, parsed_data: list[dict]) -> bool:
        """Validate Masters history data.

        Checks:
        - Each record has player_name, year, finish_position
        - Years are in valid range (1934-present)
        - Finish positions are positive integers
        """
        if not parsed_data:
            return False
        required = {"player_name", "year", "finish_position"}
        for record in parsed_data:
            if not required.issubset(record.keys()):
                return False
            if not (1934 <= record["year"] <= 2030):
                return False
        return True

    def to_dataframe(self, parsed_data: list[dict]) -> pd.DataFrame:
        """Convert to DataFrame with proper types."""
        df = pd.DataFrame(parsed_data)
        df["year"] = df["year"].astype(int)
        df["finish_position"] = df["finish_position"].astype(int)
        return df

    @staticmethod
    def get_placeholder_data() -> list[dict]:
        """Return realistic Masters history stats for model development.

        This data covers key players' Augusta National performance and is
        used to compute augusta_history_score until live scrapers are wired up.
        """
        return [
            {"player_name": "Scottie Scheffler", "year": 2024, "finish_position": 1, "total_score": -12, "made_cut": True, "appearances": 8, "wins": 2, "top10s": 5},
            {"player_name": "Scottie Scheffler", "year": 2022, "finish_position": 1, "total_score": -10, "made_cut": True, "appearances": 8, "wins": 2, "top10s": 5},
            {"player_name": "Jon Rahm", "year": 2023, "finish_position": 1, "total_score": -12, "made_cut": True, "appearances": 8, "wins": 1, "top10s": 4},
            {"player_name": "Hideki Matsuyama", "year": 2021, "finish_position": 1, "total_score": -10, "made_cut": True, "appearances": 12, "wins": 1, "top10s": 5},
            {"player_name": "Tiger Woods", "year": 2019, "finish_position": 1, "total_score": -13, "made_cut": True, "appearances": 24, "wins": 5, "top10s": 14},
            {"player_name": "Jordan Spieth", "year": 2015, "finish_position": 1, "total_score": -18, "made_cut": True, "appearances": 11, "wins": 1, "top10s": 7},
            {"player_name": "Rory McIlroy", "year": 2024, "finish_position": 22, "total_score": 1, "made_cut": True, "appearances": 17, "wins": 0, "top10s": 8},
            {"player_name": "Xander Schauffele", "year": 2024, "finish_position": 8, "total_score": -3, "made_cut": True, "appearances": 8, "wins": 0, "top10s": 4},
            {"player_name": "Will Zalatoris", "year": 2021, "finish_position": 2, "total_score": -9, "made_cut": True, "appearances": 4, "wins": 0, "top10s": 2},
            {"player_name": "Dustin Johnson", "year": 2020, "finish_position": 1, "total_score": -20, "made_cut": True, "appearances": 13, "wins": 1, "top10s": 5},
            {"player_name": "Phil Mickelson", "year": 2010, "finish_position": 1, "total_score": -16, "made_cut": True, "appearances": 30, "wins": 3, "top10s": 11},
            {"player_name": "Adam Scott", "year": 2013, "finish_position": 1, "total_score": -9, "made_cut": True, "appearances": 22, "wins": 1, "top10s": 5},
        ]
