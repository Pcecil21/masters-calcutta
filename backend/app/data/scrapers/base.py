"""Abstract base class for all data scrapers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import pandas as pd


class DataScraper(ABC):
    """Base class for all external data scrapers.

    Subclasses implement the four-stage pipeline:
    1. fetch()    - retrieve raw data from the source
    2. parse()    - transform raw data into structured dicts
    3. validate() - check data quality and completeness
    4. to_dataframe() - return a clean pandas DataFrame

    Usage:
        scraper = MastersHistoryScraper()
        raw = await scraper.fetch()
        parsed = scraper.parse(raw)
        if scraper.validate(parsed):
            df = scraper.to_dataframe(parsed)
    """

    @abstractmethod
    async def fetch(self) -> Any:
        """Fetch raw data from the external source.

        Returns:
            Raw data in whatever format the source provides (HTML, JSON, etc.)

        Raises:
            httpx.HTTPStatusError: If the HTTP request fails.
            ConnectionError: If the source is unreachable.
        """
        ...

    @abstractmethod
    def parse(self, raw_data: Any) -> list[dict]:
        """Parse raw data into a list of structured dictionaries.

        Args:
            raw_data: Output from fetch().

        Returns:
            List of dicts, each representing one record (golfer/stat/odds row).
        """
        ...

    @abstractmethod
    def validate(self, parsed_data: list[dict]) -> bool:
        """Validate parsed data for quality and completeness.

        Args:
            parsed_data: Output from parse().

        Returns:
            True if data passes all validation checks.

        Raises:
            ValueError: If critical data quality issues are found.
        """
        ...

    @abstractmethod
    def to_dataframe(self, parsed_data: list[dict]) -> pd.DataFrame:
        """Convert validated data to a pandas DataFrame.

        Args:
            parsed_data: Output from parse(), after validate() returns True.

        Returns:
            Clean DataFrame ready for model consumption.
        """
        ...
