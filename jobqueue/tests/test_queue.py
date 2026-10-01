"""
Unit tests against a fake in-memory Redis (fakeredis) — no real Redis needed.
This mirrors the "unit test = isolated, fast, no real external dependency"
principle from your interview prep: we're testing OUR queue logic, not
whether Redis itself works.
"""
import sys
from pathlib import Path

import fakeredis
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobqueue.job import Job, JobStatus
from jobqueue.queue import JobQueue


@pytest.fixture
def queue() -> JobQueue:
    q = JobQueue()
    q.r = fakeredis.FakeStrictRedis(decode_responses=True)  # swap real client for fake
    return q


def test_enqueue_then_dequeue_returns_same_job(queue: JobQueue):
    job = Job(job_type="print_message", payload={"message": "hi"})
    queue.enqueue(job)

    dequeued = queue.dequeue(timeout=1)

    assert dequeued is not None
    assert dequeued.id == job.id
    assert dequeued.status == JobStatus.RUNNING
    assert dequeued.attempts == 1


def test_dequeue_on_empty_queue_returns_none(queue: JobQueue):
    assert queue.dequeue(timeout=1) is None


def test_complete_removes_job_from_processing(queue: JobQueue):
    job = Job(job_type="print_message", payload={})
    queue.enqueue(job)
    dequeued = queue.dequeue(timeout=1)

    queue.complete(dequeued)

    assert queue.queue_depth()["processing"] == 0
    assert queue.get_job(job.id).status == JobStatus.DONE


def test_fail_requeues_job_when_attempts_remain(queue: JobQueue):
    job = Job(job_type="flaky_task", payload={}, max_attempts=3)
    queue.enqueue(job)
    dequeued = queue.dequeue(timeout=1)  # attempts -> 1

    queue.fail(dequeued, error="boom")

    assert queue.queue_depth()["pending"] == 1
    assert queue.get_job(job.id).status == JobStatus.PENDING


def test_fail_moves_to_dead_letter_after_max_attempts(queue: JobQueue):
    job = Job(job_type="flaky_task", payload={}, max_attempts=1)
    queue.enqueue(job)
    dequeued = queue.dequeue(timeout=1)  # attempts -> 1, hits max

    queue.fail(dequeued, error="boom")

    assert queue.queue_depth()["dead"] == 1
    assert queue.get_job(job.id).status == JobStatus.DEAD
