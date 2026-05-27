import os
import tempfile
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path

import pytest

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://hamper:hamper_secret@localhost:5433/hamper_forecast_test",
)
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ.setdefault("FIRECRAWL_API_KEY", "test-key")
os.environ.setdefault("TRAIN_EPOCHS", "2")
os.environ.setdefault("MIN_TRAINING_ROWS", "18")
os.environ.setdefault("LSTM_WINDOW", "12")
os.environ.setdefault("FORECAST_HORIZON", "6")

if "MODEL_DIR" not in os.environ:
    os.environ["MODEL_DIR"] = tempfile.mkdtemp(prefix="hamper_test_models_")


def _import_tensorflow():
    try:
        import tensorflow  # noqa: F401

        return True
    except ImportError:
        return False


HAS_TENSORFLOW = _import_tensorflow()


@lru_cache(maxsize=1)
def postgres_available() -> bool:
    from sqlalchemy import create_engine, text

    def reachable(url: str) -> bool:
        try:
            engine = create_engine(url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    if reachable(TEST_DATABASE_URL):
        return True

    admin_url = TEST_DATABASE_URL.rsplit("/", 1)[0] + "/postgres"
    if not reachable(admin_url):
        return False

    db_name = TEST_DATABASE_URL.rsplit("/", 1)[-1]
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": db_name},
        ).scalar()
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    return reachable(TEST_DATABASE_URL)


requires_postgres = pytest.mark.integration
requires_tensorflow = pytest.mark.ml
requires_ml = pytest.mark.ml


def pytest_collection_modifyitems(config, items):
    pg_ok = None
    for item in items:
        needs_postgres = "integration" in item.keywords or "ml" in item.keywords
        needs_tensorflow = "ml" in item.keywords

        if needs_postgres:
            if pg_ok is None:
                try:
                    pg_ok = postgres_available()
                except ModuleNotFoundError:
                    pg_ok = False
            if not pg_ok:
                item.add_marker(
                    pytest.mark.skip(reason=f"PostgreSQL not reachable at {TEST_DATABASE_URL}")
                )

        if needs_tensorflow and not HAS_TENSORFLOW:
            item.add_marker(pytest.mark.skip(reason="TensorFlow is not installed"))


@pytest.fixture(scope="session")
def model_dir() -> Path:
    path = Path(os.environ["MODEL_DIR"])
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.fixture(scope="function")
def db_engine():
    if not postgres_available():
        pytest.skip(f"PostgreSQL not reachable at {TEST_DATABASE_URL}")

    from src.database import reset_db

    reset_db()
    from src.database import engine

    return engine


@pytest.fixture(scope="function")
def db_session(db_engine):
    from sqlalchemy.orm import sessionmaker

    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = testing_session()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def app_client():
    from fastapi.testclient import TestClient

    from src.main import create_app

    with TestClient(create_app(enable_scheduler=False)) as test_client:
        yield test_client


@pytest.fixture(scope="function")
def client(db_session):
    from fastapi.testclient import TestClient

    from src.database import get_db
    from src.main import create_app

    app = create_app(enable_scheduler=False)

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def seed_company_monthly(db, months: int = 24, start_year: int = 2023) -> None:
    from src.models import CompanyMonthly

    for idx in range(months):
        month = (idx % 12) + 1
        year = start_year + (idx // 12)
        period = date(year, month, 1)
        seasonal = 1.0 + (0.5 if month == 12 else 0.0)
        db.add(
            CompanyMonthly(
                period=period,
                sales_volume=400 * seasonal,
                revenue=12000 * seasonal,
                profit=3000 * seasonal,
                currency="GBP",
                created_at=datetime.now(timezone.utc),
            )
        )
    db.commit()


def seed_market_documents(db) -> None:
    from src.models import MarketDocument

    db.add(
        MarketDocument(
            source_url="https://example.com/hampers",
            scraped_at=datetime(2024, 12, 15, tzinfo=timezone.utc),
            title="Christmas gift hamper trends",
            markdown="Luxury gift hamper demand rises at christmas with corporate gifting.",
            query_tag="christmas_retail",
            status="ok",
            firecrawl_job_meta={"type": "test"},
        )
    )
    db.commit()
