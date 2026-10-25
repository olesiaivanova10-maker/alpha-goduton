"""Prototype feedback store. Replace with a database in production."""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone


@dataclass
class Feedback:
    insight_id: str
    company_id: str
    rating: int
    comment: str | None = None
    created_at: str = ""


_items: list[Feedback] = []


def add_feedback(insight_id: str, company_id: str, rating: int, comment: str | None = None) -> dict:
    if rating not in range(1, 6):
        raise ValueError("rating должен быть от 1 до 5")
    item = Feedback(insight_id, company_id, rating, comment, datetime.now(timezone.utc).isoformat())
    _items.append(item)
    return asdict(item)


def feedback_metrics() -> dict:
    ratings = [item.rating for item in _items]
    return {
        "count": len(ratings),
        "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        "positive_share": round(sum(r >= 4 for r in ratings) / len(ratings), 2) if ratings else None,
    }
