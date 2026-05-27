from datetime import date

import pytest

from src.routers.ingest import parse_period


@pytest.mark.unit
class TestParsePeriod:
    def test_iso_date(self):
        assert parse_period("2024-01-15") == date(2024, 1, 1)

    def test_year_month(self):
        assert parse_period("2024-03") == date(2024, 3, 1)

    def test_month_year_slash(self):
        assert parse_period("03/2024") == date(2024, 3, 1)

    def test_day_month_year_slash(self):
        assert parse_period("15/01/2024") == date(2024, 1, 1)

    def test_invalid_format_raises(self):
        with pytest.raises(ValueError, match="Unrecognized date format"):
            parse_period("not-a-date")

    def test_strips_whitespace(self):
        assert parse_period("  2024-06  ") == date(2024, 6, 1)
