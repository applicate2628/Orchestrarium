"""Shared draining for adapter-owned async cleanup, not process supervision."""
from __future__ import annotations

import asyncio
from typing import TypeVar

_Result = TypeVar("_Result")


async def drain_owned(task: asyncio.Task[_Result]) -> _Result:
    """Retain an owned outcome despite repeated cancellation of its caller.

    The existing process owner enforces resource/deadline bounds. This helper
    cannot settle a process or manufacture a result if the owned task is cancelled.
    """
    while True:
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            if task.done():
                return task.result()
