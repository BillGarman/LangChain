import asyncio
import functools
from typing import Any, Dict, List, Optional, Union

from langchain.callbacks.base import BaseCallbackHandler, BaseCallbackManager
from langchain.schema import AgentAction, AgentFinish, LLMResult


class CallbackManager(BaseCallbackManager):
    """Callback manager that can be used to handle callbacks from langchain."""

    def __init__(self, handlers: List[BaseCallbackHandler]) -> None:
        """Initialize callback manager."""
        self.handlers: List[BaseCallbackHandler] = handlers

    def _handle_event(
        self,
        event_name: str,
        ignore_condition_name: Optional[str],
        verbose: bool,
        *args: Any,
        **kwargs: Any
    ) -> None:
        for handler in self.handlers:
            if ignore_condition_name is None or not getattr(
                handler, ignore_condition_name
            ):
                if verbose or handler.always_verbose:
                    getattr(handler, event_name)(*args, **kwargs)

    def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when LLM starts running."""
        self._handle_event(
            "on_llm_start", "ignore_llm", verbose, serialized, prompts, **kwargs
        )

    def on_llm_new_token(
        self, token: str, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when LLM generates a new token."""
        self._handle_event("on_llm_new_token", "ignore_llm", verbose, token, **kwargs)

    def on_llm_end(
        self, response: LLMResult, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when LLM ends running."""
        self._handle_event("on_llm_end", "ignore_llm", verbose, response, **kwargs)

    def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when LLM errors."""
        self._handle_event("on_llm_error", "ignore_llm", verbose, error, **kwargs)

    def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when chain starts running."""
        self._handle_event(
            "on_chain_start", "ignore_chain", verbose, serialized, inputs, **kwargs
        )

    def on_chain_end(
        self, outputs: Dict[str, Any], verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when chain ends running."""
        self._handle_event("on_chain_end", "ignore_chain", verbose, outputs, **kwargs)

    def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when chain errors."""
        self._handle_event("on_chain_error", "ignore_chain", verbose, error, **kwargs)

    def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        self._handle_event(
            "on_tool_start", "ignore_agent", verbose, serialized, input_str, **kwargs
        )

    def on_agent_action(
        self, action: AgentAction, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        self._handle_event("on_agent_action", "ignore_agent", verbose, action, **kwargs)

    def on_tool_end(self, output: str, verbose: bool = False, **kwargs: Any) -> None:
        """Run when tool ends running."""
        self._handle_event("on_tool_end", "ignore_agent", verbose, output, **kwargs)

    def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when tool errors."""
        self._handle_event("on_tool_error", "ignore_agent", verbose, error, **kwargs)

    def on_text(self, text: str, verbose: bool = False, **kwargs: Any) -> None:
        """Run on additional input from chains and agents."""
        self._handle_event("on_text", None, verbose, text, **kwargs)

    def on_agent_finish(
        self, finish: AgentFinish, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run on agent end."""
        self._handle_event("on_agent_finish", "ignore_agent", verbose, finish, **kwargs)

    def add_handler(self, handler: BaseCallbackHandler) -> None:
        """Add a handler to the callback manager."""
        self.handlers.append(handler)

    def remove_handler(self, handler: BaseCallbackHandler) -> None:
        """Remove a handler from the callback manager."""
        self.handlers.remove(handler)

    def set_handlers(self, handlers: List[BaseCallbackHandler]) -> None:
        """Set handlers as the only handlers on the callback manager."""
        self.handlers = handlers


async def _ahandle_event_for_handler(
    handler: BaseCallbackHandler,
    event_name: str,
    ignore_condition_name: Optional[str],
    verbose: bool,
    *args: Any,
    **kwargs: Any
) -> None:
    if ignore_condition_name is None or not getattr(handler, ignore_condition_name):
        if verbose or handler.always_verbose:
            event = getattr(handler, event_name)
            if asyncio.iscoroutinefunction(event):
                await event(*args, **kwargs)
            else:
                await asyncio.get_event_loop().run_in_executor(
                    None, functools.partial(event, *args, **kwargs)
                )


class AsyncCallbackManager(BaseCallbackManager):
    """Async callback manager that can be used to handle callbacks from LangChain."""

    @property
    def is_async(self) -> bool:
        """Return whether the handler is async."""
        return True

    def __init__(self, handlers: List[BaseCallbackHandler]) -> None:
        """Initialize callback manager."""
        self.handlers: List[BaseCallbackHandler] = handlers

    async def _handle_event(
        self,
        event_name: str,
        ignore_condition_name: Optional[str],
        verbose: bool,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Generic event handler for AsyncCallbackManager."""
        await asyncio.gather(
            *(
                _ahandle_event_for_handler(
                    handler, event_name, ignore_condition_name, verbose, *args, **kwargs
                )
                for handler in self.handlers
            )
        )

    async def on_llm_start(
        self,
        serialized: Dict[str, Any],
        prompts: List[str],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when LLM starts running."""
        await self._handle_event(
            "on_llm_start", "ignore_llm", verbose, serialized, prompts, **kwargs
        )

    async def on_llm_new_token(
        self, token: str, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run on new LLM token. Only available when streaming is enabled."""
        await self._handle_event(
            "on_llm_new_token", "ignore_llm", verbose, token, **kwargs
        )

    async def on_llm_end(
        self, response: LLMResult, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when LLM ends running."""
        await self._handle_event(
            "on_llm_end", "ignore_llm", verbose, response, **kwargs
        )

    async def on_llm_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when LLM errors."""
        await self._handle_event("on_llm_error", "ignore_llm", verbose, error, **kwargs)

    async def on_chain_start(
        self,
        serialized: Dict[str, Any],
        inputs: Dict[str, Any],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when chain starts running."""
        await self._handle_event(
            "on_chain_start", "ignore_chain", verbose, serialized, inputs, **kwargs
        )

    async def on_chain_end(
        self, outputs: Dict[str, Any], verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when chain ends running."""
        await self._handle_event(
            "on_chain_end", "ignore_chain", verbose, outputs, **kwargs
        )

    async def on_chain_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when chain errors."""
        await self._handle_event(
            "on_chain_error", "ignore_chain", verbose, error, **kwargs
        )

    async def on_tool_start(
        self,
        serialized: Dict[str, Any],
        input_str: str,
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when tool starts running."""
        await self._handle_event(
            "on_tool_start", "ignore_agent", verbose, serialized, input_str, **kwargs
        )

    async def on_tool_end(
        self, output: str, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when tool ends running."""
        await self._handle_event(
            "on_tool_end", "ignore_agent", verbose, output, **kwargs
        )

    async def on_tool_error(
        self,
        error: Union[Exception, KeyboardInterrupt],
        verbose: bool = False,
        **kwargs: Any
    ) -> None:
        """Run when tool errors."""
        await self._handle_event(
            "on_tool_error", "ignore_agent", verbose, error, **kwargs
        )

    async def on_text(self, text: str, verbose: bool = False, **kwargs: Any) -> None:
        """Run when text is printed."""
        await self._handle_event("on_text", None, verbose, text, **kwargs)

    async def on_agent_action(
        self, action: AgentAction, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run on agent action."""
        await self._handle_event(
            "on_agent_action", "ignore_agent", verbose, action, **kwargs
        )

    async def on_agent_finish(
        self, finish: AgentFinish, verbose: bool = False, **kwargs: Any
    ) -> None:
        """Run when agent finishes."""
        await self._handle_event(
            "on_agent_finish", "ignore_agent", verbose, finish, **kwargs
        )

    def add_handler(self, handler: BaseCallbackHandler) -> None:
        """Add a handler to the callback manager."""
        self.handlers.append(handler)

    def remove_handler(self, handler: BaseCallbackHandler) -> None:
        """Remove a handler from the callback manager."""
        self.handlers.remove(handler)

    def set_handlers(self, handlers: List[BaseCallbackHandler]) -> None:
        """Set handlers as the only handlers on the callback manager."""
        self.handlers = handlers
