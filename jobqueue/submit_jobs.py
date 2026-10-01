"""
Submit some example jobs to the queue. Run a worker first (or after — jobs
just wait in `queue:pending` either way):

    python submit_jobs.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from jobqueue.job import Job
from jobqueue.queue import JobQueue

if __name__ == "__main__":
    queue = JobQueue()

    jobs = [
        Job(job_type="print_message", payload={"message": "Hello from job 1"}),
        Job(job_type="print_message", payload={"message": "Hello from job 2"}),
        Job(job_type="simulate_work", payload={"duration": 2}),
        Job(job_type="flaky_task", payload={}),
        Job(job_type="flaky_task", payload={}),
        Job(job_type="flaky_task", payload={}),
    ]

    for job in jobs:
        job_id = queue.enqueue(job)
        print(f"Enqueued {job.job_type} -> {job_id}")

    print("\nQueue depth:", queue.queue_depth())
