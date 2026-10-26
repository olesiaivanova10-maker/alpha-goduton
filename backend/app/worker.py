"""RQ worker that refreshes discovery registration after a Redis restart."""

import os
from rq import Worker, Queue, worker_registration
from .jobs import redis


class ResilientWorker(Worker):
    def heartbeat(self, timeout=None, pipeline=None):
        super().heartbeat(timeout=timeout, pipeline=pipeline)
        worker_registration.register(self, pipeline=pipeline)


if __name__ == "__main__":
    connection = redis()
    ResilientWorker(
        [Queue("alpha", connection=connection)],
        connection=connection,
        name=os.getenv("HOSTNAME", "alpha-worker"),
    ).work(with_scheduler=True)
