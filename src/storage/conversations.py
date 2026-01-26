"""Conversation storage with JSON file persistence."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Any


@dataclass
class InteractionLog:
    """Detailed log of a single interaction (user input -> assistant response)."""
    
    id: str
    timestamp: str  # ISO format - when interaction started
    
    # Input details
    input_type: str  # "voice" or "text"
    audio_duration_ms: Optional[int] = None  # Duration of audio if voice input
    audio_samples: Optional[int] = None  # Number of audio samples
    
    # Transcription details (for voice input)
    transcription_text: Optional[str] = None  # What STT produced
    transcription_duration_ms: Optional[int] = None  # How long transcription took
    
    # What was sent to LLM
    llm_model: str = ""
    llm_system_prompt: str = ""  # Full system prompt including tools/rules
    llm_history: list[dict] = field(default_factory=list)  # Messages in history
    llm_user_message: str = ""  # The user message sent
    
    # LLM response details
    llm_response_text: str = ""  # Full response
    llm_response_duration_ms: Optional[int] = None  # How long LLM took
    llm_prompt_tokens: Optional[int] = None  # Tokens used in prompt
    llm_response_tokens: Optional[int] = None  # Tokens in response
    
    # Tool execution (if any)
    tool_calls: list[dict] = field(default_factory=list)  # [{tool, args, result, duration_ms}]
    
    # TTS details
    tts_enabled: bool = True
    tts_voice: str = ""
    tts_duration_ms: Optional[int] = None
    
    # Overall timing
    total_duration_ms: Optional[int] = None
    
    # Errors (if any)
    errors: list[str] = field(default_factory=list)
    
    @classmethod
    def create(cls, input_type: str = "voice") -> "InteractionLog":
        """Create a new interaction log."""
        return cls(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            input_type=input_type,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "InteractionLog":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            input_type=data.get("input_type", "voice"),
            audio_duration_ms=data.get("audio_duration_ms"),
            audio_samples=data.get("audio_samples"),
            transcription_text=data.get("transcription_text"),
            transcription_duration_ms=data.get("transcription_duration_ms"),
            llm_model=data.get("llm_model", ""),
            llm_system_prompt=data.get("llm_system_prompt", ""),
            llm_history=data.get("llm_history", []),
            llm_user_message=data.get("llm_user_message", ""),
            llm_response_text=data.get("llm_response_text", ""),
            llm_response_duration_ms=data.get("llm_response_duration_ms"),
            llm_prompt_tokens=data.get("llm_prompt_tokens"),
            llm_response_tokens=data.get("llm_response_tokens"),
            tool_calls=data.get("tool_calls", []),
            tts_enabled=data.get("tts_enabled", True),
            tts_voice=data.get("tts_voice", ""),
            tts_duration_ms=data.get("tts_duration_ms"),
            total_duration_ms=data.get("total_duration_ms"),
            errors=data.get("errors", []),
        )
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(f"[{datetime.now().isoformat()}] {error}")
    
    def add_tool_call(self, tool: str, args: dict, result: str, duration_ms: int, success: bool = True) -> None:
        """Add a tool call record."""
        self.tool_calls.append({
            "tool": tool,
            "args": args,
            "result": result[:500] if len(result) > 500 else result,  # Truncate long results
            "duration_ms": duration_ms,
            "success": success,
        })


@dataclass
class StoredMessage:
    """A stored chat message."""

    id: str
    role: str  # "user" or "assistant"
    content: str
    timestamp: str  # ISO format

    @classmethod
    def create(cls, role: str, content: str) -> "StoredMessage":
        """Create a new message with auto-generated id and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now().isoformat(),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "StoredMessage":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            role=data["role"],
            content=data["content"],
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class Conversation:
    """A conversation with messages."""

    id: str
    title: str
    created_at: str  # ISO format
    updated_at: str  # ISO format
    messages: list[StoredMessage] = field(default_factory=list)
    custom_rules: str = ""  # Per-chat custom instructions/rules
    interaction_logs: list[InteractionLog] = field(default_factory=list)  # Detailed debug logs

    @classmethod
    def create(cls, title: str = "New Conversation") -> "Conversation":
        """Create a new conversation with auto-generated id and timestamps."""
        now = datetime.now().isoformat()
        return cls(
            id=str(uuid.uuid4()),
            title=title,
            created_at=now,
            updated_at=now,
            messages=[],
            custom_rules="",
            interaction_logs=[],
        )

    def add_message(self, role: str, content: str) -> StoredMessage:
        """Add a message to the conversation."""
        message = StoredMessage.create(role, content)
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()

        # Auto-generate title from first user message
        if self.title == "New Conversation" and role == "user" and content.strip():
            # Use first 50 chars of first user message as title
            self.title = content.strip()[:50]
            if len(content.strip()) > 50:
                self.title += "..."

        return message

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "messages": [m.to_dict() for m in self.messages],
            "custom_rules": self.custom_rules,
            "interaction_logs": [log.to_dict() for log in self.interaction_logs],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            title=data.get("title", "Untitled"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            messages=[StoredMessage.from_dict(m) for m in data.get("messages", [])],
            custom_rules=data.get("custom_rules", ""),
            interaction_logs=[InteractionLog.from_dict(log) for log in data.get("interaction_logs", [])],
        )
    
    def add_interaction_log(self, log: "InteractionLog") -> None:
        """Add an interaction log to the conversation."""
        self.interaction_logs.append(log)
        self.updated_at = datetime.now().isoformat()


class ConversationStorage:
    """Manages conversation persistence to JSON files."""

    def __init__(self, storage_dir: Optional[Path] = None):
        """Initialize storage.

        Args:
            storage_dir: Directory to store conversations.
                        Defaults to ~/.cache/voice-chatbot/conversations/
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".cache" / "voice-chatbot" / "conversations"

        self.storage_dir = storage_dir
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def _get_file_path(self, conversation_id: str) -> Path:
        """Get the file path for a conversation."""
        return self.storage_dir / f"{conversation_id}.json"

    def save(self, conversation: Conversation) -> None:
        """Save a conversation to disk."""
        file_path = self._get_file_path(conversation.id)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(conversation.to_dict(), f, indent=2, ensure_ascii=False)

    def load(self, conversation_id: str) -> Optional[Conversation]:
        """Load a conversation from disk."""
        file_path = self._get_file_path(conversation_id)
        if not file_path.exists():
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return Conversation.from_dict(data)
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading conversation {conversation_id}: {e}")
            return None

    def delete(self, conversation_id: str) -> bool:
        """Delete a conversation from disk."""
        file_path = self._get_file_path(conversation_id)
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def list_all(self) -> list[Conversation]:
        """List all conversations, sorted by updated_at (newest first)."""
        conversations = []

        for file_path in self.storage_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    conversations.append(Conversation.from_dict(data))
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error loading {file_path}: {e}")
                continue

        # Sort by last message timestamp (or created_at if no messages), newest first
        def get_sort_time(conv: Conversation) -> str:
            if conv.messages:
                return conv.messages[-1].timestamp
            return conv.created_at
        
        conversations.sort(key=get_sort_time, reverse=True)
        return conversations

    def list_summaries(self) -> list[dict]:
        """List conversation summaries (without full message content)."""
        summaries = []

        for conv in self.list_all():
            last_message = None
            if conv.messages:
                last_msg = conv.messages[-1]
                # Truncate last message preview
                preview = last_msg.content[:100]
                if len(last_msg.content) > 100:
                    preview += "..."
                last_message = {
                    "role": last_msg.role,
                    "preview": preview,
                    "timestamp": last_msg.timestamp,
                }

            summaries.append({
                "id": conv.id,
                "title": conv.title,
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
                "message_count": len(conv.messages),
                "last_message": last_message,
                "custom_rules": conv.custom_rules,
            })

        return summaries

    def create(self, title: str = "New Conversation") -> Conversation:
        """Create and save a new conversation."""
        conversation = Conversation.create(title)
        self.save(conversation)
        return conversation

    def add_message(
        self, conversation_id: str, role: str, content: str
    ) -> Optional[StoredMessage]:
        """Add a message to a conversation and save."""
        conversation = self.load(conversation_id)
        if conversation is None:
            return None

        message = conversation.add_message(role, content)
        self.save(conversation)
        return message

    def clear_messages(self, conversation_id: str) -> bool:
        """Clear all messages from a conversation."""
        conversation = self.load(conversation_id)
        if conversation is None:
            return False

        conversation.messages = []
        conversation.updated_at = datetime.now().isoformat()
        self.save(conversation)
        return True

    def update_custom_rules(self, conversation_id: str, custom_rules: str) -> bool:
        """Update custom rules for a conversation.
        
        Args:
            conversation_id: The conversation ID
            custom_rules: The new custom rules text
            
        Returns:
            True if successful, False if conversation not found
        """
        conversation = self.load(conversation_id)
        if conversation is None:
            return False

        conversation.custom_rules = custom_rules
        conversation.updated_at = datetime.now().isoformat()
        self.save(conversation)
        return True

    def get_custom_rules(self, conversation_id: str) -> Optional[str]:
        """Get custom rules for a conversation.
        
        Args:
            conversation_id: The conversation ID
            
        Returns:
            Custom rules string or None if conversation not found
        """
        conversation = self.load(conversation_id)
        if conversation is None:
            return None
        return conversation.custom_rules

    def add_interaction_log(self, conversation_id: str, log: InteractionLog) -> bool:
        """Add an interaction log to a conversation.
        
        Args:
            conversation_id: The conversation ID
            log: The interaction log to add
            
        Returns:
            True if successful, False if conversation not found
        """
        conversation = self.load(conversation_id)
        if conversation is None:
            return False
        
        conversation.add_interaction_log(log)
        self.save(conversation)
        return True

    def get_interaction_logs(self, conversation_id: str, limit: int = 50) -> list[InteractionLog]:
        """Get interaction logs for a conversation.
        
        Args:
            conversation_id: The conversation ID
            limit: Maximum number of logs to return (newest first)
            
        Returns:
            List of interaction logs
        """
        conversation = self.load(conversation_id)
        if conversation is None:
            return []
        
        # Return newest first, limited
        return list(reversed(conversation.interaction_logs[-limit:]))
