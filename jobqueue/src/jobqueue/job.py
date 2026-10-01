"""
Job model — this is the Command pattern: an action turned into a data object
that can be serialized, queued, retried, and logged independently of whoever
triggered it or whoever eventually executes it.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    DEAD = "dead"  # exhausted retries — lives in the dead-letter queue


@dataclass
class Job:
    job_type: str                      # e.g. "send_email", "resize_image"
    payload: dict[str, Any]            # arguments the handler needs
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    attempts: int = 0
    max_attempts: int = 3
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    error: str | None = None

    def to_json(self) -> str:
        d = asdict(self)
        d["status"] = self.status.value
        return json.dumps(d)

    @classmethod
    def from_json(cls, raw: str) -> "Job":
        d = json.loads(raw)
        d["status"] = JobStatus(d["status"])
        return cls(**d)
