"""Conversation storage with JSON file persistence."""

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


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
        )


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

        # Sort by updated_at, newest first
        conversations.sort(key=lambda c: c.updated_at, reverse=True)
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
