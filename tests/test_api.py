from datetime import date
from io import BytesIO
from pathlib import Path

import pytest

from tests.conftest import requires_postgres, seed_company_monthly


@pytest.mark.unit
class TestHealth:
    def test_health_endpoint(self, app_client):
        response = app_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.integration
@requires_postgres
class TestIngestApi:
    def test_ingest_company_monthly_json(self, client, db_session):
        payload = {
            "rows": [
                {
                    "period": "2024-01-01",
                    "sales_volume": 440,
                    "revenue": 13200,
                    "profit": 3300,
                    "currency": "GBP",
                    "notes": "January",
                }
            ]
        }
        response = client.post("/ingest/company-monthly", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["details"]["count"] == 1

        from src.models import CompanyMonthly

        row = db_session.query(CompanyMonthly).one()
        assert row.profit == 3300
        assert row.period == date(2024, 1, 1)

    def test_ingest_company_monthly_json_upserts(self, client, db_session):
        payload = {
            "rows": [
                {
                    "period": "2024-01-01",
                    "sales_volume": 440,
                    "revenue": 13200,
                    "profit": 3300,
                    "currency": "GBP",
                }
            ]
        }
        client.post("/ingest/company-monthly", json=payload)
        payload["rows"][0]["profit"] = 3500
        response = client.post("/ingest/company-monthly", json=payload)

        assert response.status_code == 200
        from src.models import CompanyMonthly

        row = db_session.query(CompanyMonthly).one()
        assert row.profit == 3500

    def test_ingest_csv_upload(self, client, db_session):
        csv_content = (
            "period,sales_volume,revenue,profit,currency,notes\n"
            "2024-02-01,395,11850,2950,GBP,February\n"
        ).encode("utf-8")
        response = client.post(
            "/ingest/company-monthly/csv",
            files={"file": ("monthly.csv", BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["details"]["count"] == 1

    def test_ingest_csv_rejects_invalid_row(self, client):
        csv_content = b"period,sales_volume,revenue,profit,currency,notes\nbad-date,1,2,3,GBP,x\n"
        response = client.post(
            "/ingest/company-monthly/csv",
            files={"file": ("monthly.csv", BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 400

    def test_ingest_csv_rejects_empty_file(self, client):
        csv_content = b"period,sales_volume,revenue,profit,currency,notes\n"
        response = client.post(
            "/ingest/company-monthly/csv",
            files={"file": ("monthly.csv", BytesIO(csv_content), "text/csv")},
        )
        assert response.status_code == 400
        assert "no data rows" in response.json()["detail"].lower()

    def test_ingest_products(self, client, db_session):
        payload = {
            "rows": [
                {"name": "Luxury Christmas Hamper", "category": "Seasonal"},
                {"name": "Corporate Gift Box", "category": "Corporate"},
            ]
        }
        response = client.post("/ingest/products", json=payload)
        assert response.status_code == 200
        assert response.json()["details"]["count"] == 2

        from src.models import Product

        assert db_session.query(Product).count() == 2


@pytest.mark.integration
@requires_postgres
class TestJobsApiWithoutMl:
    def test_scrape_market_without_api_key(self, client, monkeypatch):
        from src.config import settings

        monkeypatch.setattr(settings, "firecrawl_api_key", "")
        response = client.post("/jobs/scrape-market")
        assert response.status_code == 200
        body = response.json()
        assert body["details"]["scrape"]["status"] == "skipped"

    def test_aggregate_market_features_endpoint(self, client, db_session):
        response = client.post("/jobs/aggregate-market-features")
        assert response.status_code == 200
        assert response.json()["details"]["periods"] == 0

    def test_retrain_skips_with_insufficient_history(self, client, db_session):
        seed_company_monthly(db_session, months=6)
        response = client.post("/jobs/retrain")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "skipped"
        assert "Insufficient history" in body["message"]

    def test_forecast_naive_fallback(self, client, db_session):
        seed_company_monthly(db_session, months=6)
        response = client.post("/jobs/forecast")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["details"]["method"] == "naive_seasonal"
        assert body["details"]["forecasts_written"] == 12

        from src.models import Forecast

        assert db_session.query(Forecast).count() == 12

    def test_forecast_skips_when_no_data(self, client):
        response = client.post("/jobs/forecast")
        assert response.status_code == 200
        assert response.json()["status"] == "skipped"


@pytest.mark.ml
@requires_postgres
class TestMlPipelineApi:
    @pytest.fixture(autouse=True)
    def require_tensorflow(self):
        pytest.importorskip("tensorflow")

    def test_full_pipeline_train_and_forecast(self, client, db_session, model_dir: Path):
        sample_csv = Path("data/sample_company_monthly.csv")
        with sample_csv.open("rb") as handle:
            response = client.post(
                "/ingest/company-monthly/csv",
                files={"file": ("sample.csv", handle, "text/csv")},
            )
        assert response.status_code == 200

        train_response = client.post("/jobs/retrain")
        assert train_response.status_code == 200
        train_body = train_response.json()
        assert train_body["status"] == "ok"
        assert (model_dir / "current.keras").exists()

        forecast_response = client.post("/jobs/forecast")
        assert forecast_response.status_code == 200
        forecast_body = forecast_response.json()
        assert forecast_body["status"] == "ok"
        assert forecast_body["details"]["method"] == "lstm"
        assert forecast_body["details"]["forecasts_written"] == 12

        from src.models import Forecast, ModelRun

        assert db_session.query(ModelRun).count() >= 1
        profits = (
            db_session.query(Forecast)
            .filter(Forecast.metric == "profit")
            .order_by(Forecast.target_month.asc())
            .all()
        )
        assert len(profits) == 6
        assert all(row.point_estimate > 0 for row in profits)
