"""Durable database snapshot with an expendable short-lived Redis cache."""

import json
from pathlib import Path
from .news_ingestion import NewsRecord
from .storage import repositories as repo
from .settings import settings

PATH = Path("backend/data/news.json")  # legacy import tooling only


def save_news(records, status):
    repo.put_news(records, status)
    if settings().redis_url:
        try:
            from .jobs import redis

            redis().delete("news-snapshot")
        except Exception:
            pass


def load_news():
    cache = None
    if settings().redis_url:
        try:
            from .jobs import redis

            raw = redis().get("news-snapshot")
            if raw:
                cache = json.loads(raw)
        except Exception:
            pass
    values = cache["items"] if cache else repo.all_news()
    status = cache["status"] if cache else repo.source_status()
    records = []
    for data in values:
        try:
            records.append(NewsRecord.model_validate(data))
        except ValueError:
            continue  # Legacy card metadata can lack article content.
    if cache is None and settings().redis_url:
        try:
            from .jobs import redis

            redis().set(
                "news-snapshot",
                json.dumps(
                    {
                        "items": [r.model_dump(mode="json") for r in records],
                        "status": status,
                    }
                ),
                ex=60,
            )
        except Exception:
            pass  # Cache loss never erases persistent records.
    return records, status
