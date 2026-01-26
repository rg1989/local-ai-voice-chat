"""Memory storage with JSON file persistence for cross-chat context sharing."""

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
import re


@dataclass
class MemoryEntry:
    """A stored memory that persists across all conversations."""

    id: str
    content: str  # The memory content
    created_at: str  # ISO format timestamp
    source_conversation_id: Optional[str]  # Which chat it came from (if any)
    tags: list[str]  # Optional categorization tags

    @classmethod
    def create(
        cls,
        content: str,
        source_conversation_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> "MemoryEntry":
        """Create a new memory with auto-generated id and timestamp."""
        return cls(
            id=str(uuid.uuid4()),
            content=content,
            created_at=datetime.now().isoformat(),
            source_conversation_id=source_conversation_id,
            tags=tags or [],
        )

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryEntry":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            content=data["content"],
            created_at=data.get("created_at", datetime.now().isoformat()),
            source_conversation_id=data.get("source_conversation_id"),
            tags=data.get("tags", []),
        )


class MemoryStorage:
    """Manages persistent memory storage to a single JSON file."""

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize storage.

        Args:
            storage_path: Path to the memories JSON file.
                         Defaults to ~/.cache/voice-chatbot/memories.json
        """
        if storage_path is None:
            storage_dir = Path.home() / ".cache" / "voice-chatbot"
            storage_dir.mkdir(parents=True, exist_ok=True)
            storage_path = storage_dir / "memories.json"

        self.storage_path = storage_path
        self._memories: list[MemoryEntry] = []
        self._load()

    def _load(self) -> None:
        """Load memories from disk."""
        if not self.storage_path.exists():
            self._memories = []
            return

        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._memories = [MemoryEntry.from_dict(m) for m in data.get("memories", [])]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading memories: {e}")
            self._memories = []

    def _save(self) -> None:
        """Save memories to disk."""
        data = {"memories": [m.to_dict() for m in self._memories]}
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def add(
        self,
        content: str,
        source_conversation_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> MemoryEntry:
        """Add a new memory.

        Args:
            content: The memory content to store
            source_conversation_id: The conversation ID where this memory was created
            tags: Optional list of tags for categorization

        Returns:
            The created MemoryEntry
        """
        memory = MemoryEntry.create(
            content=content,
            source_conversation_id=source_conversation_id,
            tags=tags,
        )
        self._memories.append(memory)
        self._save()
        return memory

    def get_all(self) -> list[MemoryEntry]:
        """Get all memories, sorted by creation date (newest first).

        Returns:
            List of all memory entries
        """
        return sorted(self._memories, key=lambda m: m.created_at, reverse=True)

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a specific memory by ID.

        Args:
            memory_id: The memory ID to retrieve

        Returns:
            The MemoryEntry or None if not found
        """
        for memory in self._memories:
            if memory.id == memory_id:
                return memory
        return None

    def delete(self, memory_id: str) -> bool:
        """Delete a memory by ID.

        Args:
            memory_id: The memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        for i, memory in enumerate(self._memories):
            if memory.id == memory_id:
                self._memories.pop(i)
                self._save()
                return True
        return False

    def update(self, memory_id: str, content: str, tags: Optional[list[str]] = None) -> Optional[MemoryEntry]:
        """Update an existing memory.

        Args:
            memory_id: The memory ID to update
            content: New content
            tags: New tags (None to keep existing)

        Returns:
            The updated MemoryEntry or None if not found
        """
        for memory in self._memories:
            if memory.id == memory_id:
                memory.content = content
                if tags is not None:
                    memory.tags = tags
                self._save()
                return memory
        return None

    def search(self, query: str) -> list[MemoryEntry]:
        """Search memories by content and tags.

        Args:
            query: The search query (case-insensitive)

        Returns:
            List of matching memory entries, sorted by relevance
        """
        if not query or not query.strip():
            return self.get_all()

        query = query.strip().lower()
        escaped_query = re.escape(query)
        pattern = re.compile(escaped_query, re.IGNORECASE)

        matches = []
        for memory in self._memories:
            # Check content match
            content_match = pattern.search(memory.content)
            
            # Check tag matches
            tag_match = any(pattern.search(tag) for tag in memory.tags)
            
            if content_match or tag_match:
                # Calculate a simple relevance score
                score = 0
                if content_match:
                    # Exact match in content gets higher score
                    score += 10
                    # Bonus for match at start
                    if memory.content.lower().startswith(query):
                        score += 5
                if tag_match:
                    score += 3
                
                matches.append((memory, score))

        # Sort by score (descending), then by creation date (newest first)
        matches.sort(key=lambda x: (x[1], x[0].created_at), reverse=True)
        return [m[0] for m in matches]

    def get_context_string(self, max_memories: int = 20) -> str:
        """Format memories for inclusion in LLM system prompt.

        Args:
            max_memories: Maximum number of memories to include

        Returns:
            Formatted string of memories for the system prompt
        """
        memories = self.get_all()[:max_memories]
        
        if not memories:
            return "No memories stored yet."

        lines = []
        for memory in memories:
            tags_str = f" [{', '.join(memory.tags)}]" if memory.tags else ""
            lines.append(f"- {memory.content}{tags_str}")

        return "\n".join(lines)

    def clear_all(self) -> int:
        """Clear all memories.

        Returns:
            Number of memories deleted
        """
        count = len(self._memories)
        self._memories = []
        self._save()
        return count


# Global instance for easy access
memory_storage = MemoryStorage()
