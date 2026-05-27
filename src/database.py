from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from src.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from src.models import (  # noqa: F401 — register models with metadata
        CompanyMonthly,
        Forecast,
        MarketDocument,
        MarketFeaturesMonthly,
        ModelRun,
        Product,
    )

    Base.metadata.create_all(bind=engine)


def reset_db() -> None:
    from src.models import (  # noqa: F401
        CompanyMonthly,
        Forecast,
        MarketDocument,
        MarketFeaturesMonthly,
        ModelRun,
        Product,
    )

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
