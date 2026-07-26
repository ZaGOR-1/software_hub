"""Deterministic bridges for exercising async code from synchronous tests."""

import asyncio
from collections.abc import Coroutine
from concurrent.futures import ThreadPoolExecutor
from typing import Any


def run_coroutine[ResultT](coroutine: Coroutine[Any, Any, ResultT]) -> ResultT:
    """Run a coroutine on an isolated thread even if the caller already owns an event loop."""

    def execute() -> ResultT:
        return asyncio.run(coroutine)

    with ThreadPoolExecutor(
        max_workers=1,
        thread_name_prefix="software-hub-test-async",
    ) as executor:
        return executor.submit(execute).result()
