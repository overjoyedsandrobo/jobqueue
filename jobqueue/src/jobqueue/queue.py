"""
Redis-backed job queue.

Phase 1 design notes (read these — they're the actual learning content):

- We use a Redis LIST as a FIFO queue: LPUSH to add, BRPOP to take.
- BRPOP is ATOMIC and BLOCKING. This is the answer to "how do two workers
  avoid grabbing the same job" — Redis guarantees that if two workers call
  BRPOP on the same key at the same moment, only one of them gets any given
  element. No locking code needed on our side; Redis's single-threaded
  command execution gives us this for free. This is worth being able to
  explain out loud: it's a real answer to a real distributed-systems race
  condition, not just "we added a lock."
- We keep a separate Redis HASH (`jobs:data`) mapping job_id -> full job
  JSON, so the queue itself only ever needs to carry lightweight job IDs,
  not full payloads, and so job status can be looked up/updated by ID from
  anywhere (a status API endpoint, a retry handler, etc.) without scanning
  the queue.
- A job moves through Redis keys as it moves through its lifecycle:
    queue:pending   -> queue:processing  -> done (removed / archived)
                                          -> queue:pending (retry)
                                          -> queue:dead (exhausted retries)
  This "move between named lists" pattern is exactly how simple, production
  job queues like RQ actually track state — worth recognizing when you read
  their source later.
"""
from __future__ import annotations

import redis

from .job import Job, JobStatus

PENDING_KEY = "queue:pending"
PROCESSING_KEY = "queue:processing"
DEAD_KEY = "queue:dead"
JOB_DATA_KEY = "jobs:data"  # hash: job_id -> job JSON


class JobQueue:
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.r = redis.from_url(redis_url, decode_responses=True)

    # ---- Producer side --------------------------------------------------

    def enqueue(self, job: Job) -> str:
        """Add a job to the pending queue. Returns the job id."""
        self.r.hset(JOB_DATA_KEY, job.id, job.to_json())
        self.r.lpush(PENDING_KEY, job.id)
        return job.id

    # ---- Worker side ------------------------------------------------------

    def dequeue(self, timeout: int = 5) -> Job | None:
        """
        Atomically move a job id from pending -> processing and return the
        full Job. Blocks up to `timeout` seconds waiting for work.
        BRPOPLPUSH is itself atomic: the pop from `pending` and the push
        onto `processing` happen as one indivisible Redis operation, so a
        crash between "popped" and "marked as processing" can't happen —
        there's no gap for a job to be silently lost.
        """
        job_id = self.r.brpoplpush(PENDING_KEY, PROCESSING_KEY, timeout=timeout)
        if job_id is None:
            return None
        raw = self.r.hget(JOB_DATA_KEY, job_id)
        if raw is None:
            # Data hash entry missing (shouldn't normally happen) — drop it
            self.r.lrem(PROCESSING_KEY, 1, job_id)
            return None
        job = Job.from_json(raw)
        job.status = JobStatus.RUNNING
        job.attempts += 1
        self._save(job)
        return job

    def complete(self, job: Job) -> None:
        job.status = JobStatus.DONE
        self._save(job)
        self.r.lrem(PROCESSING_KEY, 1, job.id)

    def fail(self, job: Job, error: str) -> None:
        """
        Called when a job's handler raises. Retries if attempts remain,
        otherwise moves it to the dead-letter queue.
        """
        job.error = error
        self.r.lrem(PROCESSING_KEY, 1, job.id)

        if job.attempts >= job.max_attempts:
            job.status = JobStatus.DEAD
            self._save(job)
            self.r.lpush(DEAD_KEY, job.id)
        else:
            job.status = JobStatus.PENDING
            self._save(job)
            self.r.lpush(PENDING_KEY, job.id)  # Phase 3 will add backoff delay here

    # ---- Introspection ------------------------------------------------

    def get_job(self, job_id: str) -> Job | None:
        raw = self.r.hget(JOB_DATA_KEY, job_id)
        return Job.from_json(raw) if raw else None

    def queue_depth(self) -> dict[str, int]:
        return {
            "pending": self.r.llen(PENDING_KEY),
            "processing": self.r.llen(PROCESSING_KEY),
            "dead": self.r.llen(DEAD_KEY),
        }

    def _save(self, job: Job) -> None:
        self.r.hset(JOB_DATA_KEY, job.id, job.to_json())
