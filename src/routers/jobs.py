from fastapi import APIRouter

from src.schemas import JobResponse
from src.services.firecrawl_client import run_market_scrape
from src.services.market_features import aggregate_market_features

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/scrape-market", response_model=JobResponse)
def scrape_market():
    result = run_market_scrape()
    feature_result = aggregate_market_features()
    return JobResponse(
        status="ok",
        message="Market scrape completed",
        details={"scrape": result, "features": feature_result},
    )


@router.post("/aggregate-market-features", response_model=JobResponse)
def aggregate_features():
    result = aggregate_market_features()
    return JobResponse(status="ok", message="Market features aggregated", details=result)


@router.post("/retrain", response_model=JobResponse)
def retrain():
    from ml.train import run_training

    result = run_training()
    return JobResponse(status=result.get("status", "ok"), message=result.get("message", ""), details=result)


@router.post("/forecast", response_model=JobResponse)
def forecast():
    from ml.infer import run_inference

    result = run_inference()
    return JobResponse(status=result.get("status", "ok"), message=result.get("message", ""), details=result)
