from datetime import datetime, timezone

import pytest

from src.services.market_features import aggregate_market_features
from tests.conftest import requires_postgres, seed_market_documents


@pytest.mark.integration
@requires_postgres
class TestMarketFeatures:
    def test_aggregate_keyword_hits_from_documents(self, db_session):
        seed_market_documents(db_session)
        result = aggregate_market_features(db_session)
        assert result["status"] == "ok"
        assert result["periods"] == 1

        from src.models import MarketFeaturesMonthly

        features = db_session.query(MarketFeaturesMonthly).one()
        assert features.period.year == 2024
        assert features.period.month == 12
        assert features.doc_count == 1
        assert features.gift_hits >= 1
        assert features.hamper_hits >= 1
        assert features.luxury_hits >= 1

    def test_aggregate_with_no_documents(self, db_session):
        result = aggregate_market_features(db_session)
        assert result == {"status": "ok", "periods": 0}

    def test_upsert_updates_existing_period(self, db_session):
        from src.models import MarketDocument, MarketFeaturesMonthly

        seed_market_documents(db_session)
        aggregate_market_features(db_session)

        db_session.add(
            MarketDocument(
                source_url="https://example.com/hampers-2",
                scraped_at=datetime(2024, 12, 20, tzinfo=timezone.utc),
                title="More hampers",
                markdown="Another luxury gift hamper discount for christmas.",
                query_tag="christmas_retail",
                status="ok",
                firecrawl_job_meta={"type": "test"},
            )
        )
        db_session.commit()

        result = aggregate_market_features(db_session)
        assert result["periods"] == 1
        features = db_session.query(MarketFeaturesMonthly).one()
        assert features.doc_count == 2
        assert features.gift_hits >= 2
