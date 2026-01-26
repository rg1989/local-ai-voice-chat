"""LLM client for Ollama with streaming support and tool execution."""

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator, Optional

import httpx

from ..config import settings
from .tools import tool_registry, generate_tool_prompt
from .tool_parser import tool_parser


@dataclass
class Message:
    """Chat message."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatHistory:
    """Manages conversation history."""

    messages: list[Message] = field(default_factory=list)
    max_messages: int = 20  # Keep last N messages

    def add_user_message(self, content: str) -> None:
        """Add a user message."""
        self.messages.append(Message(role="user", content=content))
        self._trim()

    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        self.messages.append(Message(role="assistant", content=content))
        self._trim()

    def _trim(self) -> None:
        """Trim history to max messages."""
        if len(self.messages) > self.max_messages:
            # Keep system message if present, then last N-1 messages
            self.messages = self.messages[-self.max_messages :]

    def to_list(self) -> list[dict]:
        """Convert to list of dicts for API."""
        return [{"role": m.role, "content": m.content} for m in self.messages]

    def clear(self) -> None:
        """Clear all messages."""
        self.messages = []


class LLMClient:
    """Client for Ollama LLM with streaming support."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools_enabled: Optional[bool] = None,
    ):
        """Initialize LLM client.

        Args:
            base_url: Ollama API base URL
            model_name: Model name in Ollama
            system_prompt: System prompt for the assistant
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            tools_enabled: Whether to enable tool use
        """
        self.base_url = base_url or settings.llm.base_url
        self.model_name = model_name or settings.llm.model_name
        self._base_system_prompt = system_prompt or settings.llm.system_prompt
        self.temperature = temperature or settings.llm.temperature
        self.max_tokens = max_tokens or settings.llm.max_tokens
        
        # Tool settings
        self.tools_enabled = tools_enabled if tools_enabled is not None else settings.tools.enabled
        
        # Global rules (apply to all conversations)
        self._global_rules: str = ""
        
        # Per-conversation custom rules
        self._custom_rules: str = ""

        self.history = ChatHistory()

        # HTTP clients with longer timeout for streaming
        self._client = httpx.Client(timeout=120.0)
        self._async_client = httpx.AsyncClient(timeout=120.0)
        
        # Context window tracking (populated from Ollama)
        self._context_window: int = 2048  # Default, updated by fetch_context_window
        self._last_prompt_tokens: int = 0  # Actual tokens used (from Ollama response)
        self._context_window_fetched: bool = False
        
        # Configure tool registry with settings
        tool_registry.fetch_timeout = settings.tools.fetch_timeout
        tool_registry.max_content_length = settings.tools.max_content_length
        tool_registry.command_timeout = settings.tools.command_timeout

    @property
    def system_prompt(self) -> str:
        """Build the full system prompt with tools, global rules, and custom rules."""
        prompt = self._base_system_prompt
        
        # Add tool instructions if enabled
        if self.tools_enabled:
            prompt += generate_tool_prompt()
        
        # Add global rules if set (apply to all chats)
        if self._global_rules:
            prompt += f"\n\n## Global Rules:\n{self._global_rules}"
        
        # Add custom rules if set (per-conversation, higher priority)
        if self._custom_rules:
            prompt += f"\n\n## Custom Rules for This Chat:\n{self._custom_rules}"
        
        return prompt

    def set_global_rules(self, rules: str) -> None:
        """Set global rules that apply to all conversations.
        
        Args:
            rules: Global instructions/rules to apply
        """
        self._global_rules = rules

    def get_global_rules(self) -> str:
        """Get the current global rules."""
        return self._global_rules

    def set_custom_rules(self, rules: str) -> None:
        """Set custom rules for the current conversation.
        
        Args:
            rules: Custom instructions/rules to apply
        """
        self._custom_rules = rules

    def get_custom_rules(self) -> str:
        """Get the current custom rules."""
        return self._custom_rules

    def _build_messages(self, user_message: str) -> list[dict]:
        """Build messages list with system prompt and history."""
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history.to_list())
        messages.append({"role": "user", "content": user_message})
        return messages

    def chat(self, user_message: str, stream: bool = False) -> str | Iterator[str]:
        """Send a chat message and get response.

        Args:
            user_message: User's message
            stream: If True, return iterator of tokens

        Returns:
            Full response string or iterator of tokens
        """
        if stream:
            return self._chat_stream(user_message)
        return self._chat_sync(user_message)

    def _chat_sync(self, user_message: str) -> str:
        """Synchronous chat completion."""
        messages = self._build_messages(user_message)

        response = self._client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
        )
        response.raise_for_status()

        result = response.json()
        assistant_message = result.get("message", {}).get("content", "")
        
        # Capture actual token counts from Ollama
        self._last_prompt_tokens = result.get("prompt_eval_count", 0)

        # Update history
        self.history.add_user_message(user_message)
        self.history.add_assistant_message(assistant_message)

        return assistant_message

    def _chat_stream(self, user_message: str) -> Iterator[str]:
        """Streaming chat completion."""
        messages = self._build_messages(user_message)

        full_response = []

        with self._client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
        ) as response:
            response.raise_for_status()

            for line in response.iter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                full_response.append(content)
                                yield content

                        if data.get("done", False):
                            # Capture actual token counts from Ollama
                            self._last_prompt_tokens = data.get("prompt_eval_count", 0)
                            break
                    except json.JSONDecodeError:
                        continue

        # Update history with full response
        self.history.add_user_message(user_message)
        self.history.add_assistant_message("".join(full_response))

    async def chat_async(
        self, user_message: str, stream: bool = False
    ) -> str | AsyncIterator[str]:
        """Async chat completion.

        Args:
            user_message: User's message
            stream: If True, return async iterator of tokens

        Returns:
            Full response string or async iterator of tokens
        """
        if stream:
            return self._chat_stream_async(user_message)
        return await self._chat_sync_async(user_message)

    async def _chat_sync_async(self, user_message: str) -> str:
        """Async synchronous chat completion."""
        messages = self._build_messages(user_message)

        response = await self._async_client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
        )
        response.raise_for_status()

        result = response.json()
        assistant_message = result.get("message", {}).get("content", "")
        
        # Capture actual token counts from Ollama
        self._last_prompt_tokens = result.get("prompt_eval_count", 0)

        # Update history
        self.history.add_user_message(user_message)
        self.history.add_assistant_message(assistant_message)

        return assistant_message

    async def _chat_stream_async(self, user_message: str) -> AsyncIterator[str]:
        """Async streaming chat completion."""
        messages = self._build_messages(user_message)

        full_response = []

        async with self._async_client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                full_response.append(content)
                                yield content

                        if data.get("done", False):
                            # Capture actual token counts from Ollama
                            self._last_prompt_tokens = data.get("prompt_eval_count", 0)
                            break
                    except json.JSONDecodeError:
                        continue

        # Update history with full response
        self.history.add_user_message(user_message)
        self.history.add_assistant_message("".join(full_response))

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()
        self._last_prompt_tokens = 0

    async def execute_tool_calls(self, response_text: str) -> Optional[str]:
        """Check for and execute any tool calls in the response.
        
        Args:
            response_text: The LLM response text to check for tool calls
            
        Returns:
            Combined tool results if any tools were called, None otherwise
        """
        if not self.tools_enabled:
            return None
        
        tool_calls = tool_parser.find_tool_calls(response_text)
        if not tool_calls:
            return None
        
        results = []
        for call in tool_calls:
            print(f"[TOOL] Executing: {call.tool} with args: {call.args}")
            result = await tool_registry.execute(call.tool, call.args)
            
            if result.success:
                results.append(f"[Tool: {call.tool}]\n{result.output}")
            else:
                results.append(f"[Tool: {call.tool}] Error: {result.error}")
        
        return "\n\n".join(results)

    async def chat_with_tools_async(
        self, 
        user_message: str, 
        on_token: Optional[callable] = None,
        max_tool_iterations: int = 3
    ) -> str:
        """Async chat with automatic tool execution.
        
        This method handles the full tool execution loop:
        1. Get LLM response
        2. Check for tool calls
        3. Execute tools
        4. Re-prompt LLM with results
        5. Repeat until no tool calls or max iterations reached
        
        Args:
            user_message: User's message
            on_token: Optional callback for each token (for streaming to UI)
            max_tool_iterations: Maximum number of tool execution rounds
            
        Returns:
            Final response text
        """
        full_response = []
        iterations = 0
        
        # First response from user message
        async for token in await self.chat_async(user_message, stream=True):
            full_response.append(token)
            if on_token:
                await on_token(token)
        
        response_text = "".join(full_response)
        
        # Tool execution loop
        while iterations < max_tool_iterations and self.tools_enabled:
            # Check for tool calls
            tool_results = await self.execute_tool_calls(response_text)
            
            if not tool_results:
                break  # No tool calls, we're done
            
            iterations += 1
            
            # Add tool results as a system message and get new response
            tool_message = f"Tool execution results:\n\n{tool_results}\n\nNow provide a natural response incorporating these results."
            
            # Get follow-up response
            full_response = []
            async for token in await self._chat_stream_async_internal(tool_message, role="system"):
                full_response.append(token)
                if on_token:
                    await on_token(token)
            
            response_text = "".join(full_response)
        
        return response_text

    async def _chat_stream_async_internal(self, message: str, role: str = "user") -> AsyncIterator[str]:
        """Internal streaming chat for tool follow-ups.
        
        This doesn't add to history - it's for injecting tool results.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.history.to_list())
        messages.append({"role": role, "content": message})
        
        async with self._async_client.stream(
            "POST",
            f"{self.base_url}/api/chat",
            json={
                "model": self.model_name,
                "messages": messages,
                "stream": True,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line:
                    try:
                        data = json.loads(line)
                        if "message" in data:
                            content = data["message"].get("content", "")
                            if content:
                                yield content

                        if data.get("done", False):
                            self._last_prompt_tokens = data.get("prompt_eval_count", 0)
                            break
                    except json.JSONDecodeError:
                        continue

    async def check_connection(self) -> bool:
        """Check if Ollama is running and model is available.

        Returns:
            True if connection is successful
        """
        try:
            response = await self._async_client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()

            models = [m.get("name", "") for m in data.get("models", [])]
            # Check if our model is available (handle version suffixes)
            model_base = self.model_name.split(":")[0]
            return any(model_base in m for m in models)
        except Exception:
            return False

    async def fetch_context_window(self) -> int:
        """Query Ollama for the model's context window size.
        
        Returns:
            Context window size in tokens
        """
        try:
            response = await self._async_client.post(
                f"{self.base_url}/api/show",
                json={"model": self.model_name}
            )
            response.raise_for_status()
            data = response.json()
            
            # Try to get from model_info (e.g., "qwen3.context_length")
            model_info = data.get("model_info", {})
            for key, value in model_info.items():
                if key.endswith(".context_length") and isinstance(value, int):
                    self._context_window = value
                    self._context_window_fetched = True
                    print(f"[DEBUG] Context window from model_info: {value} (key: {key})")
                    return value
            
            # Fallback: parse from parameters string "num_ctx XXXX"
            params = data.get("parameters", "")
            print(f"[DEBUG] No context_length in model_info, checking parameters...")
            if "num_ctx" in params:
                for line in params.split("\n"):
                    if "num_ctx" in line:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                self._context_window = int(parts[1])
                                self._context_window_fetched = True
                                return self._context_window
                            except ValueError:
                                pass
        except Exception:
            pass
        
        return self._context_window

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count from text (~4 chars per token for English).
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        return len(text) // 4 + 1

    def estimate_history_tokens(self) -> int:
        """Estimate total tokens in current conversation history.
        
        Returns:
            Estimated total tokens including system prompt
        """
        # System prompt tokens
        total = self.estimate_tokens(self.system_prompt)
        
        # History tokens
        for msg in self.history.messages:
            total += self.estimate_tokens(msg.content)
            # Add overhead for role markers (~4 tokens per message)
            total += 4
        
        return total

    def update_token_estimate_from_history(self) -> None:
        """Update _last_prompt_tokens based on current history.
        
        Call this after loading conversation history to have an accurate
        estimate before the first LLM call.
        """
        self._last_prompt_tokens = self.estimate_history_tokens()

    def get_memory_usage(self) -> dict:
        """Return memory usage stats for the client.
        
        Returns:
            Dict with used_tokens, max_tokens, percentage, is_near_limit
        """
        # Reserve buffer for system prompt and response generation
        buffer = 512
        available = max(1, self._context_window - buffer)
        used = self._last_prompt_tokens
        percentage = min(100, int((used / available) * 100)) if available > 0 else 0
        
        return {
            "used_tokens": used,
            "max_tokens": available,
            "percentage": percentage,
            "is_near_limit": percentage > 80
        }

    def close(self) -> None:
        """Close HTTP clients."""
        self._client.close()

    async def aclose(self) -> None:
        """Close async HTTP client."""
        await self._async_client.aclose()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    async def __aenter__(self) -> "LLMClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.aclose()
