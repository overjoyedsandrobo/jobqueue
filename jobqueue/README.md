# jobqueue — a mini job queue, built from scratch

A learning project: a Redis-backed job queue and worker system, similar in
spirit to Celery/RQ, built up in phases to deliberately exercise algorithms,
concurrency, NoSQL, and design patterns in a real (not toy) setting.

## Why this project

Most CRUD API tutorials don't force you to touch: priority queues, retry
backoff, race conditions between concurrent workers, or Redis as anything
more than a cache. This project's whole point is a producer/consumer system
where those things are unavoidable, not optional extras.

## Phase 1 — Done (this code)

- `Job` — the unit of work as a data object (Command pattern: an action
  turned into something you can serialize, queue, retry, and log).
- `JobQueue` — Redis-backed FIFO queue using `BRPOPLPUSH` for atomic,
  blocking dequeue. This is the actual answer to "how do two workers avoid
  grabbing the same job" — read the comments in `src/jobqueue/queue.py`,
  it's worth understanding this mechanism cold.
- `registry.py` — a `@register("job_type")` decorator mapping job types to
  handler functions (Strategy pattern: the worker doesn't know or care what
  a job actually does, it just looks up the right handler).
- `worker.py` — the poll loop: dequeue → dispatch to handler → report
  success/failure back to the queue.
- Retry + dead-letter queue: a failing job gets requeued up to
  `max_attempts`, then moves to `queue:dead`.
- Unit tests against `fakeredis` (no real Redis needed to run them) —
  demonstrates the "test your own logic in isolation" principle for real.

### Try it

```bash
docker compose up -d          # starts Redis
pip install -r requirements.txt

# terminal 1
python workers/run_worker.py worker-1

# terminal 2 (optional — run a second worker to see concurrency)
python workers/run_worker.py worker-2

# terminal 3
python submit_jobs.py
```

Watch the worker terminal(s) — jobs get picked up, `flaky_task` jobs will
sometimes fail and retry, and if you run two workers you'll see them split
the work between them without ever processing the same job twice.

Run tests: `pytest tests/ -v`

## Roadmap — what to build next, in order

### Phase 2 — Priority + scheduled jobs
Replace the plain list with a Redis **sorted set** (`ZADD`/`ZRANGEBYSCORE`),
where the score is either a priority number or a "run at" timestamp. This is
where you actually implement a scheduling algorithm instead of plain FIFO —
a worker should check "is there a due job?" instead of "is there any job?".

**What to build:** `enqueue_at(job, run_at: datetime)`, a worker loop that
only picks up jobs whose scheduled time has passed.

### Phase 3 — Real retry backoff
Right now, `fail()` requeues immediately. Add exponential backoff: on
attempt N, delay the retry by `base_delay * 2^N` (plus jitter, to avoid many
failed jobs retrying in lockstep — a real production concern, look up
"thundering herd" when you get here). This plugs directly into the Phase 2
scheduled-job mechanism — a delayed retry *is* a scheduled job.

### Phase 4 — True concurrency inside a worker
Right now each worker processes one job at a time. Make a single worker
process **multiple jobs concurrently** using `asyncio` (convert handlers to
`async def`) or a `ThreadPoolExecutor` for I/O-bound handlers. This is where
you'll want to revisit the difference between `threading`, `multiprocessing`,
and `asyncio` — pick based on whether your example handlers are CPU-bound or
I/O-bound, and be ready to explain why you chose what you chose.

### Phase 5 — Visibility: a FastAPI dashboard
Build a small FastAPI app on top of `JobQueue`:
- `POST /jobs` — submit a job
- `GET /jobs/{id}` — check status
- `GET /queue/depth` — pending/processing/dead counts
- A WebSocket endpoint pushing live status updates via Redis **pub/sub**
  (`PUBLISH`/`SUBSCRIBE`) when a job's status changes — genuinely useful
  WebSocket practice, not a toy example.

### Phase 6 — Polish for the portfolio
- Dockerize the whole stack (Redis + N workers + the API) in one
  `docker-compose.yml`
- Integration tests against a real Redis (not just fakeredis) — mirrors the
  two-tier testing approach from your other project
- GitHub Actions CI: lint → unit tests → integration tests against a Redis
  service container → build
- A "Design Decisions" section in the README explaining the tradeoffs you
  hit — future-you (and any interviewer) will get more out of that than
  the code itself

## Stretch ideas, once the core is solid
- **Idempotency keys** — prevent the same logical job from being enqueued
  twice (e.g., a hash of the payload as a dedup key)
- **Job dependencies/DAGs** — "run job B only after job A succeeds" (this is
  genuinely what tools like Airflow do, at a much bigger scale)
- **Rate limiting per job type** — token bucket algorithm, implemented
  yourself, using Redis as the shared counter across workers
- **Priority starvation handling** — what stops low-priority jobs from
  waiting forever if high-priority jobs keep arriving?
