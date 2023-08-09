"""Base class for AINetwork tools."""
from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

from langchain.tools.ainetwork.utils import authenticate
from langchain.tools.base import BaseTool
from pydantic import Field

if TYPE_CHECKING:
    from ain.ain import Ain
else:
    try:
        # We do this so pydantic can resolve the types when instantiating
        from ain.ain import Ain
    except ImportError:
        pass


class AINBaseTool(BaseTool):
    """Base class for the AINetwork tools."""

    interface: Ain = Field(default_factory=authenticate)
    """The interface object for the AINetwork Blockchain."""

    def _run(self, *args, **kwargs):
        loop = asyncio.get_event_loop()

        if loop.is_running():
            result_container = []

            def thread_target():
                nonlocal result_container
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    result_container.append(new_loop.run_until_complete(self._arun(*args, **kwargs)))
                finally:
                    new_loop.close()

            thread = threading.Thread(target=thread_target)
            thread.start()
            thread.join()
            return result_container[0]

        else:
            result = loop.run_until_complete(self._arun(*args, **kwargs))
            loop.close()
            return result
