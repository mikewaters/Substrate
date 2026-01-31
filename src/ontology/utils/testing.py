from pyparsing import wraps
from typing import Any
import asyncio


def dual_mode(method):
    """Allow async methods to be used from sync contexts when no loop is running."""

    @wraps(method)
    def wrapper(self, *args: Any, **kwargs: Any):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return method(self, *args, **kwargs)

        return asyncio.run(method(self, *args, **kwargs))

    return wrapper
