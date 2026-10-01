"""
Example job handlers, registered via the @register decorator from registry.py.
Replace/extend these with real work (send an email, resize an image, hit an
external API) as you build the project out.
"""
from __future__ import annotations

import random
import time

from .registry import register


@register("print_message")
def handle_print_message(payload: dict) -> None:
    print(f">>> {payload.get('message', '(no message)')}")


@register("simulate_work")
def handle_simulate_work(payload: dict) -> None:
    """Sleeps to simulate a slow task — useful for watching concurrency."""
    duration = payload.get("duration", 1)
    time.sleep(duration)


@register("flaky_task")
def handle_flaky_task(payload: dict) -> None:
    """
    Fails ~50% of the time on purpose — use this to watch the retry and
    dead-letter behavior in queue.py's `fail()` in action.
    """
    if random.random() < 0.5:
        raise RuntimeError("simulated transient failure")
    print(">>> flaky_task succeeded this time")
