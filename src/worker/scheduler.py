import logging

from src.services.firecrawl_client import run_market_scrape
from src.services.market_features import aggregate_market_features

logger = logging.getLogger(__name__)


def run_scheduled_market_job():
    logger.info("Worker: market scrape job")
    scrape_result = run_market_scrape()
    feature_result = aggregate_market_features()
    return {"scrape": scrape_result, "features": feature_result}
