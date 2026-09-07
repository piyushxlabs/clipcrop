"""Async subprocess execution utility with Windows event-loop resilience.

Guarantees non-blocking async execution for ffmpeg and ffprobe across
all platforms, automatically handling Windows SelectorEventLoop limitations
(such as during uvicorn --reload) by dispatching to asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Sequence


async def run_async_subprocess(
    cmd: Sequence[str],
) -> tuple[int, bytes, bytes]:
    """Execute a subprocess asynchronously without blocking the event loop.

    Returns:
        tuple of (returncode, stdout_bytes, stderr_bytes)
    """
    str_cmd = [str(arg) for arg in cmd]
    loop = asyncio.get_running_loop()

    # Determine if current event loop supports asyncio subprocess transports
    supports_subprocess = not (
        sys.platform == "win32"
        and isinstance(loop, getattr(asyncio, "SelectorEventLoop", ()))
    )

    if supports_subprocess:
        try:
            proc = await asyncio.create_subprocess_exec(
                *str_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode if proc.returncode is not None else 0, stdout, stderr
        except NotImplementedError:
            pass

    # Threaded non-blocking fallback for loops lacking native subprocess support
    def _sync_runner() -> tuple[int, bytes, bytes]:
        res = subprocess.run(
            str_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return res.returncode, res.stdout, res.stderr

    return await asyncio.to_thread(_sync_runner)
