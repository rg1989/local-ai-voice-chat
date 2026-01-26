"""LLM client for Ollama with streaming support."""

import json
from dataclasses import dataclass, field
from typing import AsyncIterator, Iterator, Optional

import httpx

from ..config import settings


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
    ):
        """Initialize LLM client.

        Args:
            base_url: Ollama API base URL
            model_name: Model name in Ollama
            system_prompt: System prompt for the assistant
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
        """
        self.base_url = base_url or settings.llm.base_url
        self.model_name = model_name or settings.llm.model_name
        self.system_prompt = system_prompt or settings.llm.system_prompt
        self.temperature = temperature or settings.llm.temperature
        self.max_tokens = max_tokens or settings.llm.max_tokens

        self.history = ChatHistory()

        # HTTP clients with longer timeout for streaming
        self._client = httpx.Client(timeout=120.0)
        self._async_client = httpx.AsyncClient(timeout=120.0)

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
                            break
                    except json.JSONDecodeError:
                        continue

        # Update history with full response
        self.history.add_user_message(user_message)
        self.history.add_assistant_message("".join(full_response))

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history.clear()

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
