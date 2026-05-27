from unittest.mock import MagicMock, patch

import pytest

from src.services import firecrawl_client
from tests.conftest import requires_postgres


@pytest.mark.integration
@requires_postgres
class TestFirecrawlIntegration:
    @patch.object(firecrawl_client, "_get_firecrawl_client")
    def test_run_market_scrape_persists_documents(self, mock_client_factory, db_session, monkeypatch):
        monkeypatch.setattr(firecrawl_client.settings, "firecrawl_api_key", "test-key")
        client = MagicMock()
        client.scrape.return_value = {
            "data": {
                "markdown": "Luxury christmas gift hamper for corporate gifting.",
                "metadata": {"title": "Trends", "sourceURL": "https://example.com/trends"},
            }
        }
        client.search.return_value = {"data": []}
        mock_client_factory.return_value = (client, "v2")

        result = firecrawl_client.run_market_scrape()
        assert result["status"] == "ok"
        assert result["saved"] >= 1

        from src.models import MarketDocument

        docs = db_session.query(MarketDocument).all()
        assert len(docs) >= 1
        assert any(doc.markdown and "hamper" in doc.markdown.lower() for doc in docs)
