"""Small deterministic news normalizer used before the AI pipeline."""

import hashlib
import re
from datetime import datetime


def normalize_news(item: dict) -> dict:
    title = re.sub(r"\s+", " ", str(item.get("title", "")).strip())
    body = re.sub(r"\s+", " ", str(item.get("body", "")).strip())
    if not title or not body:
        raise ValueError("Новость должна содержать title и body")
    source = str(item.get("source_name") or "СМИ").strip()
    published_at = item.get("published_at")
    if published_at:
        datetime.fromisoformat(str(published_at).replace("Z", "+00:00"))
    news_id = item.get("news_id") or hashlib.sha256(f"{title}|{source}".encode()).hexdigest()[:16]
    return {
        "news_id": str(news_id),
        "title": title,
        "body": body,
        "published_at": published_at,
        "source_name": source,
        "source_url": item.get("source_url"),
    }
