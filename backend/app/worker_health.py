import os
from datetime import datetime, timezone
from rq import Worker
from .jobs import redis


def healthy():
    worker = Worker.find_by_key(
        "rq:worker:" + os.getenv("HOSTNAME", "alpha-worker"), connection=redis()
    )
    if not worker or not worker.last_heartbeat:
        return False
    stamp = worker.last_heartbeat
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - stamp).total_seconds() < worker.worker_ttl + 60


if __name__ == "__main__":
    raise SystemExit(0 if healthy() else 1)
