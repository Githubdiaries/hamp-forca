from unittest.mock import MagicMock, patch

import pytest

from src.services import firecrawl_client


@pytest.mark.unit
class TestFirecrawlClient:
    def test_run_market_scrape_skips_without_api_key(self, monkeypatch):
        monkeypatch.setattr(firecrawl_client.settings, "firecrawl_api_key", "")
        result = firecrawl_client.run_market_scrape()
        assert result["status"] == "skipped"
        assert "FIRECRAWL_API_KEY" in result["reason"]

    def test_scrape_url_success(self):
        client = MagicMock()
        client.scrape.return_value = {
            "data": {
                "markdown": "# Gift hampers",
                "metadata": {"title": "Hampers", "sourceURL": "https://example.com"},
            }
        }
        doc = firecrawl_client._scrape_url(client, "https://example.com", "seed", {"formats": ["markdown"]})
        assert doc["status"] == "ok"
        assert doc["markdown"] == "# Gift hampers"
        assert doc["source_url"] == "https://example.com"

    def test_scrape_url_handles_errors(self):
        client = MagicMock()
        client.scrape.side_effect = RuntimeError("network down")
        doc = firecrawl_client._scrape_url(client, "https://example.com", "seed", {})
        assert doc["status"] == "error"
        assert "network down" in doc["meta"]["error"]
