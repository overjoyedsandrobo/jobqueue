"""
Handler registry — this is the Strategy pattern: each job_type maps to an
interchangeable handler function. The worker doesn't know or care what a
"send_email" job actually does internally; it just looks up the right
strategy by name and calls it. Adding a new job type means registering a
new function — the worker loop itself never changes. That's Open/Closed
in practice, not just a definition.
"""
from __future__ import annotations

from typing import Any, Callable

HandlerFn = Callable[[dict[str, Any]], None]

_registry: dict[str, HandlerFn] = {}


def register(job_type: str):
    """Decorator: @register("send_email") def handler(payload): ..."""

    def decorator(fn: HandlerFn) -> HandlerFn:
        _registry[job_type] = fn
        return fn

    return decorator


def get_handler(job_type: str) -> HandlerFn:
    if job_type not in _registry:
        raise ValueError(f"No handler registered for job_type '{job_type}'")
    return _registry[job_type]
