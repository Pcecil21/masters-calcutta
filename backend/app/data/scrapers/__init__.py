"""Data scrapers for external golf data sources."""

from app.data.scrapers.base import DataScraper
from app.data.scrapers.betting_odds import BettingOddsScraper
from app.data.scrapers.masters_history import MastersHistoryScraper
from app.data.scrapers.pga_stats import PGAStatsScraper
from app.data.scrapers.rankings import RankingsScraper

__all__ = [
    "DataScraper",
    "BettingOddsScraper",
    "MastersHistoryScraper",
    "PGAStatsScraper",
    "RankingsScraper",
]
