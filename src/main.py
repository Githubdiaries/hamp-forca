import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from src.routers import ingest, jobs
from src.schemas import HealthResponse
from src.services.firecrawl_client import run_market_scrape
from src.services.market_features import aggregate_market_features

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def _scheduled_market_pipeline():
    logger.info("Running scheduled market scrape")
    run_market_scrape()
    aggregate_market_features()


def _scheduled_train_and_forecast():
    from ml.infer import run_inference
    from ml.train import run_training

    logger.info("Running scheduled retrain and forecast")
    run_training()
    run_inference()


def create_app(*, enable_scheduler: bool = True) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if enable_scheduler:
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
            scheduler.add_job(_scheduled_market_pipeline, "cron", hour=2, minute=0, id="market_scrape")
            scheduler.add_job(_scheduled_train_and_forecast, "cron", hour=3, minute=0, day=1, id="monthly_forecast")
            scheduler.start()
            logger.info("Scheduler started")
        try:
            yield
        finally:
            if enable_scheduler and scheduler.running:
                scheduler.shutdown(wait=False)

    application = FastAPI(title="Hamper Forecast API", version="1.0.0", lifespan=lifespan)
    application.include_router(ingest.router)
    application.include_router(jobs.router)

    @application.get("/", response_class=HTMLResponse)
    def home():
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="utf-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <title>Hamper Forecast</title>
          <style>
            body { font-family: system-ui, sans-serif; max-width: 640px; margin: 3rem auto; padding: 0 1rem; color: #1a1a1a; }
            h1 { font-size: 1.5rem; }
            a { color: #2563eb; }
            .card { border: 1px solid #e5e7eb; border-radius: 8px; padding: 1rem 1.25rem; margin: 1rem 0; }
            .primary { background: #eff6ff; border-color: #bfdbfe; }
          </style>
        </head>
        <body>
          <h1>Hamper Forecast</h1>
          <p>This port serves the <strong>API</strong>, not the charts. Use the links below.</p>
          <div class="card primary">
            <strong>Dashboard UI (Grafana)</strong><br />
            <a href="http://localhost:3000/d/hamper-profit-forecast/hamper-profit-forecast" target="_blank">
              Open Hamper Profit Forecast dashboard
            </a><br />
            <small>Login: admin / admin</small>
          </div>
          <div class="card">
            <strong>API docs (Swagger)</strong><br />
            <a href="/docs">/docs</a>
          </div>
          <div class="card">
            <strong>Health check</strong><br />
            <a href="/health">/health</a>
          </div>
        </body>
        </html>
        """

    @application.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse()

    return application


app = create_app()


def main():
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
