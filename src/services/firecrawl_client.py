import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from src.config import settings
from src.database import SessionLocal
from src.models import MarketDocument

logger = logging.getLogger(__name__)

KEYWORDS = ["gift", "hamper", "luxury", "discount", "christmas", "easter", "corporate"]


def _load_config() -> dict:
    path = Path(settings.market_sources_path)
    if not path.exists():
        path = Path("config/market_sources.yaml")
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _keyword_score(text: str) -> dict[str, int]:
    lowered = text.lower()
    hits = {kw: len(re.findall(rf"\b{re.escape(kw)}\b", lowered)) for kw in KEYWORDS}
    hits["total"] = sum(hits.values())
    return hits


def _save_document(
    db: Session,
    *,
    source_url: str,
    title: str | None,
    markdown: str | None,
    query_tag: str | None,
    status: str,
    meta: dict,
) -> None:
    scraped_at = datetime.now(timezone.utc)
    stmt = insert(MarketDocument).values(
        source_url=source_url,
        scraped_at=scraped_at,
        title=title,
        markdown=markdown,
        query_tag=query_tag,
        status=status,
        firecrawl_job_meta=meta,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["source_url", "scraped_at"])
    db.execute(stmt)


def _get_firecrawl_client():
    api_key = settings.firecrawl_api_key
    try:
        from firecrawl import Firecrawl

        return Firecrawl(api_key=api_key), "v2"
    except ImportError:
        pass
    from firecrawl import FirecrawlApp

    return FirecrawlApp(api_key=api_key), "v1"


def _scrape_url(client, url: str, tag: str, scrape_options: dict) -> dict:
    try:
        if hasattr(client, "scrape"):
            result = client.scrape(url, params=scrape_options)
        elif hasattr(client, "scrape_url"):
            result = client.scrape_url(url, params=scrape_options)
        else:
            raise RuntimeError("Unsupported Firecrawl client")
        data = result if isinstance(result, dict) else getattr(result, "__dict__", {})
        if hasattr(result, "markdown"):
            markdown = result.markdown
            metadata = getattr(result, "metadata", {}) or {}
            title = metadata.get("title") if isinstance(metadata, dict) else None
            source_url = metadata.get("sourceURL") or metadata.get("source_url") or url
        else:
            payload = data.get("data", data) if isinstance(data, dict) else {}
            markdown = payload.get("markdown")
            metadata = payload.get("metadata", {}) or {}
            title = metadata.get("title")
            source_url = metadata.get("sourceURL") or metadata.get("source_url") or url
        return {
            "source_url": source_url,
            "title": title,
            "markdown": markdown,
            "query_tag": tag,
            "status": "ok" if markdown else "empty",
            "meta": {"type": "scrape", "url": url},
        }
    except Exception as exc:
        logger.exception("Failed to scrape %s", url)
        return {
            "source_url": url,
            "title": None,
            "markdown": None,
            "query_tag": tag,
            "status": "error",
            "meta": {"type": "scrape", "error": str(exc), "url": url},
        }


def _search_and_scrape(client, query: str, tag: str, limit: int, scrape_options: dict) -> list[dict]:
    documents: list[dict] = []
    try:
        if hasattr(client, "search"):
            search_result = client.search(query, limit=limit)
        else:
            search_result = client.search(query, params={"limit": limit})
        if isinstance(search_result, dict):
            items = search_result.get("data", search_result.get("results", []))
        else:
            items = getattr(search_result, "data", []) or []
        for item in items:
            if isinstance(item, dict):
                url = item.get("url") or item.get("link")
                markdown = item.get("markdown")
                title = item.get("title")
                metadata = item.get("metadata", {}) or {}
            else:
                url = getattr(item, "url", None)
                markdown = getattr(item, "markdown", None)
                title = getattr(item, "title", None)
                metadata = {}
            if not url and not markdown:
                continue
            if url and not markdown:
                documents.append(_scrape_url(client, url, tag, scrape_options))
            else:
                documents.append(
                    {
                        "source_url": url or f"search:{query}",
                        "title": title,
                        "markdown": markdown,
                        "query_tag": tag,
                        "status": "ok" if markdown else "empty",
                        "meta": {"type": "search", "query": query},
                    }
                )
    except Exception as exc:
        logger.exception("Search failed for query %s", query)
        documents.append(
            {
                "source_url": f"search:{query}",
                "title": None,
                "markdown": None,
                "query_tag": tag,
                "status": "error",
                "meta": {"type": "search", "query": query, "error": str(exc)},
            }
        )
    return documents


def run_market_scrape() -> dict:
    if not settings.firecrawl_api_key:
        return {"status": "skipped", "reason": "FIRECRAWL_API_KEY not set", "saved": 0}

    from firecrawl import FirecrawlApp

    config = _load_config()
    scrape_options = config.get("scrape_options", {"formats": ["markdown"]})
    client, _ = _get_firecrawl_client()

    documents: list[dict] = []
    for item in config.get("seed_urls", []):
        documents.append(_scrape_url(client, item["url"], item.get("tag", "seed"), scrape_options))

    for item in config.get("search_queries", []):
        documents.extend(
            _search_and_scrape(
                client,
                item["query"],
                item.get("tag", "search"),
                item.get("limit", 5),
                scrape_options,
            )
        )

    saved = 0
    db = SessionLocal()
    try:
        for doc in documents:
            _save_document(
                db,
                source_url=doc["source_url"],
                title=doc.get("title"),
                markdown=doc.get("markdown"),
                query_tag=doc.get("query_tag"),
                status=doc.get("status", "ok"),
                meta=doc.get("meta", {}),
            )
            saved += 1
        db.commit()
    finally:
        db.close()

    return {
        "status": "ok",
        "saved": saved,
        "documents": len(documents),
        "errors": sum(1 for d in documents if d.get("status") == "error"),
    }
