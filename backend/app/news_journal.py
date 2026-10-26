"""Developer catalogue backed by the same database as worker processing."""

from sqlalchemy import select, func, and_
from .storage import repositories as repo
from .storage.db import transaction
from .storage.models import News, Processing

STATUSES = {"loaded", "sent", "rejected", "published", "error"}
register = repo.put_news
history = repo.history


def transition(
    news_id, company_id, role, status, stage, reason, job_id=None, card_id=None
):
    if status not in STATUSES:
        raise ValueError("Unknown journal status")
    repo.transition(news_id, company_id, role, status, stage, reason, job_id, card_id)


def bootstrap(records):
    # Explicit migration handles old SQLite/JSON. API startup must not interrupt workers.
    if records:
        register(records)


def listing(company_id, role, status=None, search="", limit=50, offset=0):
    with transaction() as s:
        join = and_(
            Processing.news_id == News.id,
            Processing.company_id == company_id,
            Processing.role == role,
        )
        state = func.coalesce(Processing.status, "loaded")
        q = select(News, Processing).outerjoin(Processing, join)
        if search:
            q = q.where(
                News.title.ilike("%" + search + "%") | News.id.ilike("%" + search + "%")
            )
        summary = {}
        for row in s.execute(q):
            k = row[1].status if row[1] else "loaded"
            summary[k] = summary.get(k, 0) + 1
        if status:
            q = q.where(state == status)
        total = s.scalar(select(func.count()).select_from(q.subquery()))
        rows = s.execute(
            q.order_by(
                func.coalesce(Processing.updated_at, News.created_at).desc(), News.id
            )
            .limit(limit)
            .offset(offset)
        ).all()
        items = []
        for news, p in rows:
            items.append(
                {
                    "news_id": news.id,
                    "title": news.title,
                    "source_name": news.payload.get("source_name", ""),
                    "source_url": news.payload.get("source_url", ""),
                    "published_at": news.payload.get("published_at"),
                    "loaded_at": news.created_at.isoformat(),
                    "status": p.status if p else "loaded",
                    "stage": p.stage if p else "ingestion",
                    "reason": p.reason
                    if p
                    else "Загружена; для этой компании ещё не отправлена модели.",
                    "job_id": p.job_id if p else None,
                    "card_id": p.card_id if p else None,
                    "updated_at": (p.updated_at if p else news.created_at).isoformat(),
                }
            )
        return {
            "company_id": company_id,
            "role": role,
            "summary": summary,
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": items,
        }
