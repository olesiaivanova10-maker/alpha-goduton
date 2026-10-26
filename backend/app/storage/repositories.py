"""Shared transactional repositories for API and workers."""

import hashlib, json, re
from sqlalchemy import select, delete
from .db import transaction
from .models import (
    News,
    Source,
    Insight,
    Citation,
    Feedback,
    Job,
    Processing,
    ProcessingEvent,
    utc,
)


def digest_payload(value):
    return hashlib.sha256(
        (value.get("title", "") + value.get("body", "")).encode()
    ).hexdigest()


def serial(value):
    return json.loads(json.dumps(value, default=lambda x: x.isoformat()))


def put_news(records, status=None):
    with transaction() as s:
        for record in records:
            r = (
                record.model_dump(mode="json")
                if hasattr(record, "model_dump")
                else dict(record)
            )
            key = r["news_id"]
            row = s.get(News, key)
            fingerprint = (
                r.get("content_hash")
                or hashlib.sha256((r["title"] + r.get("body", "")).encode()).hexdigest()
            )
            group = hashlib.sha256(
                re.sub(r"\W+", " ", r["title"].casefold()).strip().encode()
            ).hexdigest()
            if row is None:
                s.add(
                    News(
                        id=key,
                        title=r["title"],
                        payload=serial(r),
                        fingerprint=fingerprint,
                        possible_duplicate_group=group,
                    )
                )
            else:
                # Preserve full original data when importing a minimal historical card.
                row.payload = serial({**row.payload, **r})
                row.title = r["title"]
                row.fingerprint = row.payload.get("content_hash") or digest_payload(
                    row.payload
                )
                row.possible_duplicate_group = group
        from ..news_ingestion import SOURCES

        for name in (status or {}).get("loaded", []):
            row = s.get(Source, name)
            health = {"ok": True, "count": status.get("counts", {}).get(name, 0)}
            if row:
                row.health = health
                row.updated_at = utc()
            else:
                s.add(
                    Source(id=name, name=name, url=SOURCES.get(name, ""), health=health)
                )
        for failure in (status or {}).get("failed", []):
            name = failure.get("source", "unknown")
            row = s.get(Source, name)
            health = {"ok": False, "error": "source_unavailable"}
            if row:
                row.health = health
                row.updated_at = utc()
            else:
                s.add(
                    Source(
                        id=name, name=name, url=failure.get("url", ""), health=health
                    )
                )


def all_news(limit=10000):
    with transaction() as s:
        return [
            r.payload
            for r in s.scalars(
                select(News).order_by(News.created_at.desc()).limit(limit)
            )
        ]


def source_status():
    with transaction() as s:
        sources = s.scalars(select(Source)).all()
        return {
            "loaded": [r.name for r in sources if r.health.get("ok")],
            "failed": [
                {"source": r.name, "error": "source_unavailable"}
                for r in sources
                if not r.health.get("ok")
            ],
            "counts": {
                r.name: r.health.get("count", 0) for r in sources if r.health.get("ok")
            },
        }


def save_insight(company, role, event, version, status="verified"):
    audit = event.get("audit", {})
    if status not in {"verified", "degraded", "rejected"}:
        raise ValueError("Invalid insight status")
    if status in {"verified", "degraded"} and (
        audit.get("is_valid") is not True
        or audit.get("hallucination_detected") is not False
    ):
        raise ValueError("Invalid audit cannot publish insight")
    news_id = event["news_id"]
    with transaction() as s:
        revision = event.get("news_version") or s.get(News, news_id).fingerprint
        event = {**event, "news_version": revision}
        row = s.get(Insight, event["card_id"])
        if row is None:
            row = Insight(
                id=event["card_id"],
                news_id=news_id,
                company_id=company,
                role=role,
                version=version,
                status=status,
                content_version=revision,
                event=serial(event),
                audit=serial(audit),
            )
            s.add(row)
            s.flush()
        else:
            row.event = serial(event)
            row.audit = serial(audit)
            row.status = status
            row.version = version
            row.content_version = revision
        s.execute(delete(Citation).where(Citation.insight_id == row.id))
        for source in (
            event.get("six_questions", {})
            .get("q6_basis_of_conclusion", {})
            .get("sources", [])
        ):
            s.add(Citation(insight_id=row.id, payload=source))


def insight(card_id):
    with transaction() as s:
        row = s.get(Insight, card_id)
        return row.event if row and row.status in {"verified", "degraded"} else None


def feed(company, role, version=None, limit=100, offset=0):
    with transaction() as s:
        q = (
            select(Insight)
            .join(News, Insight.news_id == News.id)
            .where(
                Insight.content_version == News.fingerprint,
                Insight.company_id == company,
                Insight.role == role,
                Insight.status.in_(["verified", "degraded"]),
            )
        )
        if version:
            q = q.where(Insight.version == version)
        return [
            r.event
            for r in s.scalars(
                q.order_by(Insight.created_at.desc()).limit(limit).offset(offset)
            )
        ]


def put_job(job_id, status, detail, kind="analyze", company=None, payload=None):
    with transaction() as s:
        row = s.get(Job, job_id)
        if row:
            row.status = status
            row.detail = serial(detail)
            row.updated_at = utc()
        else:
            s.add(
                Job(
                    id=job_id,
                    kind=kind,
                    company_id=company,
                    payload=payload or {},
                    status=status,
                    detail=serial(detail),
                )
            )


def get_job(job_id):
    with transaction() as s:
        row = s.get(Job, job_id)
        return (
            {
                "job_id": row.id,
                "status": row.status,
                "detail": row.detail,
                "company_id": row.company_id,
                "kind": row.kind,
                "payload": row.payload,
            }
            if row
            else None
        )


def transition(
    news_id, company, role, status, stage, reason, job_id=None, card_id=None
):
    now = utc()
    value = dict(
        news_id=news_id,
        company_id=company,
        role=role,
        status=status,
        stage=stage,
        reason=reason,
        job_id=job_id,
        card_id=card_id,
        updated_at=now.isoformat(),
    )
    with transaction() as s:
        if job_id and not s.get(Job, job_id):
            s.add(
                Job(
                    id=job_id,
                    kind="analyze",
                    company_id=company,
                    status="running",
                    payload={},
                    detail={},
                )
            )
            s.flush()
        row = s.get(Processing, (news_id, company, role))
        if row:
            for k, v in value.items():
                if k != "updated_at":
                    setattr(row, k, v)
            row.updated_at = now
        else:
            s.add(Processing(**{**value, "updated_at": now}))
        s.add(
            ProcessingEvent(
                news_id=news_id, company_id=company, role=role, payload=value
            )
        )


def history(news_id, company, role):
    with transaction() as s:
        return [
            r.payload
            for r in s.scalars(
                select(ProcessingEvent)
                .where(
                    ProcessingEvent.news_id == news_id,
                    ProcessingEvent.company_id == company,
                    ProcessingEvent.role == role,
                )
                .order_by(ProcessingEvent.id)
            )
        ]


def feedback_add(insight_id, company, rating, comment=None):
    if not 1 <= rating <= 5:
        raise ValueError("rating должен быть от 1 до 5")
    with transaction() as s:
        row = s.get(Insight, insight_id)
        if (
            not row
            or row.company_id != company
            or row.status not in {"verified", "degraded"}
        ):
            raise ValueError("Доступный опубликованный инсайт не найден")
        item = Feedback(
            insight_id=insight_id, company_id=company, rating=rating, comment=comment
        )
        s.add(item)
        s.flush()
        return {
            "id": item.id,
            "insight_id": insight_id,
            "company_id": company,
            "rating": rating,
            "comment": comment,
            "created_at": item.created_at.isoformat(),
        }


def feedback_metrics(companies=None):
    with transaction() as s:
        q = select(Feedback.rating)
        if companies is not None:
            q = q.where(Feedback.company_id.in_(companies))
        values = list(s.scalars(q))
        return {
            "count": len(values),
            "average_rating": round(sum(values) / len(values), 2) if values else None,
            "positive_share": round(sum(v >= 4 for v in values) / len(values), 2)
            if values
            else None,
        }


def feed_counts(company, role, version):
    with transaction() as s:
        values = s.scalars(
            select(Insight.event)
            .join(News, Insight.news_id == News.id)
            .where(
                Insight.content_version == News.fingerprint,
                Insight.company_id == company,
                Insight.role == role,
                Insight.version == version,
                Insight.status.in_(["verified", "degraded"]),
            )
        )
        events = list(values)
        return len(events), sum(
            bool(e.get("relevance", {}).get("is_critical")) for e in events
        )
