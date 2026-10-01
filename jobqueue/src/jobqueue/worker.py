"""
Worker — polls the queue in a loop, dispatches to the registered handler for
each job's type, and reports success/failure back to the queue.

Run several of these as separate processes (see workers/run_worker.py) to
see the concurrency behavior: BRPOPLPUSH in queue.py is what guarantees two
workers never process the same job twice.
"""
from __future__ import annotations

import logging

from .job import Job
from .queue import JobQueue
from .registry import get_handler

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker")


def run_worker(queue: JobQueue, worker_name: str = "worker-1") -> None:
    log.info("%s starting, waiting for jobs...", worker_name)
    while True:
        job = queue.dequeue(timeout=5)
        if job is None:
            continue  # no job within timeout, poll again
        _process(queue, job, worker_name)


def _process(queue: JobQueue, job: Job, worker_name: str) -> None:
    log.info(
        "%s picked up job %s (%s), attempt %d/%d",
        worker_name, job.id, job.job_type, job.attempts, job.max_attempts,
    )
    try:
        handler = get_handler(job.job_type)
        handler(job.payload)
    except Exception as exc:  # noqa: BLE001 — job handlers are untrusted code
        log.warning("%s job %s failed: %s", worker_name, job.id, exc)
        queue.fail(job, error=str(exc))
    else:
        log.info("%s job %s completed", worker_name, job.id)
        queue.complete(job)
