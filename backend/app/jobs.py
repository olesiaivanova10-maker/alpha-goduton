"""RQ delivery plus SQL durable job records and owner-token Redis locks."""

import os, uuid
from datetime import timedelta
from redis import Redis
from rq import Queue, Retry
from .settings import settings
from .storage import repositories as repo
from .storage.db import transaction
from .storage.models import Job, utc


def redis():
    url = settings().redis_url
    if not url:
        raise RuntimeError("Redis is required to submit jobs")
    return Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3)


def enqueue(kind, payload, company=None):
    r = redis()
    r.ping()
    if kind == "probes" and not r.set("probe-submit", "1", nx=True, ex=60):
        raise RuntimeError("Probe rate limit")
    q = Queue("alpha", connection=r)
    if q.count >= int(os.getenv("MAX_QUEUE_SIZE", "100")):
        raise RuntimeError("Queue is full")
    job_id = uuid.uuid4().hex
    repo.put_job(job_id, "queued", {}, kind, company, payload)
    try:
        q.enqueue(
            "backend.app.jobs.execute",
            job_id,
            job_id=job_id,
            job_timeout=900,
            retry=Retry(max=2, interval=[15, 45]),
            result_ttl=86400,
            failure_ttl=604800,
        )
    except Exception:
        repo.put_job(job_id, "enqueue_failed", {"reason": "queue_unavailable"})
        raise
    return {"job_id": job_id, "status": "queued"}


def execute(job_id):
    r = redis()
    row = repo.get_job(job_id)
    if not row:
        raise ValueError("Job missing")
    if row["status"] in {"completed", "failed"}:
        return
    lock = r.lock("job-lock:" + job_id, timeout=930, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return
    resource = r.lock(
        "resource:" + row["kind"] + ":" + str(row["company_id"] or "global"),
        timeout=930,
        blocking_timeout=5,
    )
    if not resource.acquire(blocking=True):
        lock.release()
        raise RuntimeError("Resource busy")
    try:
        with transaction() as s:
            job = s.get(Job, job_id)
            job.status = "running"
            job.attempts += 1
            job.lease_until = utc() + timedelta(seconds=930)
        payload = row["payload"]
        kind = row["kind"]
        if kind == "rss":
            from .news_ingestion import collect_sources

            rows, status = collect_sources()
            from .news_store import save_news

            save_news(rows, status)
            repo.put_job(
                job_id, "completed", {"items_count": len(rows), "sources": status}
            )
        elif kind == "analyze":
            from .live_feed import generate
            from .agent_service import AgentService
            from agent.orchestrator import AgentOrchestrator
            from .observability import company_context, job_context, request_context

            ct = company_context.set(payload["company_id"])
            jt = job_context.set(job_id)
            rt = request_context.set(job_id)
            try:
                generate(
                    job_id,
                    payload["company_id"],
                    payload["role"],
                    payload["records"],
                    AgentService(AgentOrchestrator()),
                )
            finally:
                company_context.reset(ct)
                job_context.reset(jt)
                request_context.reset(rt)
        elif kind == "index":
            from .rag_service import build_corpus

            version = build_corpus()
            repo.put_job(job_id, "completed", {"corpus_version": version})
        elif kind == "probes":
            from .model_health import check_models

            result = check_models(force=True)
            repo.put_job(job_id, "completed", result)
        else:
            raise ValueError("Unknown job kind")
    except Exception as error:
        repo.put_job(job_id, "retrying", {"error": type(error).__name__})
        raise
    finally:
        with transaction() as s:
            job = s.get(Job, job_id)
            job.lease_until = None
        if resource.owned():
            resource.release()
        if lock.owned():
            lock.release()


def recover():
    """Recover DB-only enqueue failures and expired leases, never a currently owned lock."""
    from sqlalchemy import select, or_, and_

    r = redis()
    q = Queue("alpha", connection=r)
    with transaction() as s:
        rows = s.scalars(
            select(Job).where(
                or_(
                    Job.status.in_(["enqueue_failed", "retrying"]),
                    and_expired(),
                    and_(
                        Job.status == "queued",
                        Job.updated_at < utc() - timedelta(seconds=120),
                    ),
                )
            )
        ).all()
        for job in rows:
            if r.exists("job-lock:" + job.id):
                continue
            if job.attempts >= 3:
                job.status = "failed"
                from .storage.models import Processing, ProcessingEvent

                for state in s.scalars(
                    select(Processing).where(
                        Processing.job_id == job.id, Processing.status == "sent"
                    )
                ):
                    state.status = "error"
                    state.stage = "interrupted"
                    state.reason = (
                        "Обработка прервана; исчерпаны попытки восстановления."
                    )
                    state.updated_at = utc()
                    s.add(
                        ProcessingEvent(
                            news_id=state.news_id,
                            company_id=state.company_id,
                            role=state.role,
                            payload={
                                "status": "error",
                                "stage": "interrupted",
                                "reason": state.reason,
                                "job_id": job.id,
                                "created_at": utc().isoformat(),
                            },
                        )
                    )
                continue
            # Queue replay receives a distinct delivery ID; DB job ID stays stable.
            q.enqueue(
                "backend.app.jobs.execute",
                job.id,
                job_timeout=900,
                job_id="replay-" + uuid.uuid4().hex,
                retry=Retry(max=1, interval=20),
            )
            job.status = "queued"
            job.updated_at = utc()


def and_expired():
    from sqlalchemy import and_

    return and_(Job.status == "running", Job.lease_until < utc())


if __name__ == "__main__":
    from rq import Worker

    Worker([Queue("alpha", connection=redis())], connection=redis()).work(
        with_scheduler=True
    )
