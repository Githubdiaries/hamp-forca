import re
from collections import defaultdict
from datetime import date, datetime, timezone

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.database import SessionLocal
from src.models import MarketDocument, MarketFeaturesMonthly

KEYWORDS = {
    "gift": "gift_hits",
    "hamper": "hamper_hits",
    "luxury": "luxury_hits",
    "discount": "discount_hits",
}


def _month_start(value: datetime) -> date:
    return value.date().replace(day=1)


def _score_text(text: str) -> dict[str, float | int]:
    lowered = (text or "").lower()
    hits = {field: len(re.findall(rf"\b{re.escape(kw)}\b", lowered)) for kw, field in KEYWORDS.items()}
    total = sum(hits.values())
    avg_score = total / max(len(lowered.split()), 1)
    return {"doc_count": 1, "avg_keyword_score": avg_score, **hits}


def aggregate_market_features(db: Session | None = None) -> dict:
    own_session = db is None
    db = db or SessionLocal()
    try:
        docs = db.query(MarketDocument).filter(MarketDocument.status == "ok").all()
        buckets: dict[date, list[dict]] = defaultdict(list)
        for doc in docs:
            if not doc.markdown:
                continue
            period = _month_start(doc.scraped_at)
            buckets[period].append(_score_text(doc.markdown))

        upserted = 0
        for period, scores in buckets.items():
            doc_count = len(scores)
            avg_keyword_score = sum(s["avg_keyword_score"] for s in scores) / doc_count
            totals = {field: sum(s[field] for s in scores) for field in KEYWORDS.values()}
            stmt = insert(MarketFeaturesMonthly).values(
                period=period,
                doc_count=doc_count,
                avg_keyword_score=avg_keyword_score,
                gift_hits=totals["gift_hits"],
                hamper_hits=totals["hamper_hits"],
                luxury_hits=totals["luxury_hits"],
                discount_hits=totals["discount_hits"],
                updated_at=datetime.now(timezone.utc),
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["period"],
                set_={
                    "doc_count": doc_count,
                    "avg_keyword_score": avg_keyword_score,
                    "gift_hits": totals["gift_hits"],
                    "hamper_hits": totals["hamper_hits"],
                    "luxury_hits": totals["luxury_hits"],
                    "discount_hits": totals["discount_hits"],
                    "updated_at": datetime.now(timezone.utc),
                },
            )
            db.execute(stmt)
            upserted += 1
        db.commit()
        return {"status": "ok", "periods": upserted}
    finally:
        if own_session:
            db.close()
