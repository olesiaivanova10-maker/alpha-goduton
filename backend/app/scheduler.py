"""One owner-token lease elects the ingestion scheduler across replicas."""

import os, time, random
from .jobs import redis, enqueue, recover


def tick():
    r = redis()
    interval = int(os.getenv("RSS_REFRESH_SECONDS", "900"))
    lock = r.lock("scheduler-tick", timeout=55, blocking_timeout=0)
    if not lock.acquire(blocking=False):
        return
    try:
        recover()
        if not r.exists("rss-scheduled"):
            enqueue("rss", {})
            r.set("rss-scheduled", "1", ex=interval)
    finally:
        if lock.owned():
            lock.release()


if __name__ == "__main__":
    while True:
        try:
            tick()
            redis().set("scheduler-heartbeat", "1", ex=90)
        except Exception as e:
            print(
                __import__("json").dumps(
                    {"event": "scheduler_failure", "error": type(e).__name__}
                ),
                flush=True,
            )
        time.sleep(30 + random.random() * 5)
