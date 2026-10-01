"""
Run this in multiple terminals to see concurrent workers pull from the same
queue without ever double-processing a job:

    python workers/run_worker.py worker-1
    python workers/run_worker.py worker-2
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from jobqueue import handlers  # noqa: F401 — import registers all handlers
from jobqueue.queue import JobQueue
from jobqueue.worker import run_worker

if __name__ == "__main__":
    name = sys.argv[1] if len(sys.argv) > 1 else "worker-1"
    queue = JobQueue()
    run_worker(queue, worker_name=name)
