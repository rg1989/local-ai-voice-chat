"""Streaming sentencizer for chunked TTS processing."""

import re
from dataclasses import dataclass
from typing import AsyncIterator, Callable, Iterator, Optional


@dataclass
class SentenceChunk:
    """A chunk of text representing a sentence or partial sentence."""

    text: str
    is_complete: bool  # Whether this is a complete sentence
    is_final: bool  # Whether this is the final chunk


class StreamingSentencizer:
    """Buffers streaming tokens and yields complete sentences for TTS.

    This enables the TTS to start speaking before the LLM has finished
    generating the full response, significantly reducing perceived latency.
    """

    # Sentence-ending punctuation (high priority)
    SENTENCE_ENDINGS = {'.', '!', '?'}
    
    # Clause-ending punctuation (lower priority, for earlier TTS)
    CLAUSE_ENDINGS = {',', ':', ';', '—', '–'}

    # Patterns that should NOT trigger sentence end (abbreviations, etc.)
    ABBREVIATIONS = {
        'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'sr.', 'jr.',
        'vs.', 'etc.', 'e.g.', 'i.e.', 'no.', 'nos.',
        'st.', 'ave.', 'blvd.', 'rd.', 'apt.', 'dept.',
        'inc.', 'ltd.', 'corp.', 'co.',
        'a.m.', 'p.m.', 'a.d.', 'b.c.',
        'ph.d.', 'm.d.', 'b.a.', 'm.a.',
        'u.s.', 'u.k.', 'u.n.',
    }

    def __init__(
        self,
        min_sentence_length: int = 10,
        min_clause_length: int = 30,  # Minimum chars for clause break
        max_buffer_length: int = 500,
        on_sentence: Optional[Callable[[str], None]] = None,
    ):
        """Initialize sentencizer.

        Args:
            min_sentence_length: Minimum characters before yielding a sentence
            min_clause_length: Minimum characters before yielding on clause break
            max_buffer_length: Force yield if buffer exceeds this length
            on_sentence: Optional callback when a sentence is complete
        """
        self.min_sentence_length = min_sentence_length
        self.min_clause_length = min_clause_length
        self.max_buffer_length = max_buffer_length
        self.on_sentence = on_sentence

        self._buffer = ""

    def _is_abbreviation(self, text: str) -> bool:
        """Check if text ends with a common abbreviation."""
        text_lower = text.lower().strip()
        for abbrev in self.ABBREVIATIONS:
            if text_lower.endswith(abbrev):
                return True
        return False

    def _is_sentence_end(self, char: str, buffer: str) -> bool:
        """Check if character ends a sentence in context."""
        if char not in self.SENTENCE_ENDINGS:
            return False

        # Don't break on abbreviations
        if self._is_abbreviation(buffer + char):
            return False

        # Don't break on decimal numbers (e.g., "3.14")
        if char == '.' and buffer:
            # Check if previous char is a digit and would be followed by digit
            if buffer[-1].isdigit():
                return False

        return True

    def _find_sentence_boundary(self, text: str) -> Optional[int]:
        """Find the position of the last sentence boundary.

        Returns:
            Index after the sentence-ending punctuation, or None
        """
        for i in range(len(text) - 1, -1, -1):
            if self._is_sentence_end(text[i], text[:i]):
                # Return position after the punctuation
                return i + 1
        return None

    def _find_clause_boundary(self, text: str) -> Optional[int]:
        """Find the position of the last clause boundary (comma, colon, etc.).

        Returns:
            Index after the clause-ending punctuation, or None
        """
        for i in range(len(text) - 1, -1, -1):
            if text[i] in self.CLAUSE_ENDINGS:
                # Make sure there's a space after (natural break point)
                if i + 1 < len(text) and text[i + 1] == ' ':
                    return i + 1
                elif i + 1 == len(text):
                    return i + 1
        return None

    def add_token(self, token: str) -> Optional[str]:
        """Add a token and return complete sentence if available.

        Args:
            token: Token from LLM stream

        Returns:
            Complete sentence if one is ready, None otherwise
        """
        self._buffer += token

        # First priority: Check for sentence boundary
        boundary = self._find_sentence_boundary(self._buffer)

        if boundary and boundary >= self.min_sentence_length:
            sentence = self._buffer[:boundary].strip()
            self._buffer = self._buffer[boundary:].lstrip()

            if self.on_sentence and sentence:
                self.on_sentence(sentence)

            return sentence

        # Second priority: Check for clause boundary (for earlier TTS on long text)
        if len(self._buffer) >= self.min_clause_length:
            clause_boundary = self._find_clause_boundary(self._buffer)
            if clause_boundary and clause_boundary >= self.min_clause_length:
                clause = self._buffer[:clause_boundary].strip()
                self._buffer = self._buffer[clause_boundary:].lstrip()

                if self.on_sentence and clause:
                    self.on_sentence(clause)

                return clause

        # Force yield if buffer is too long (find last space)
        if len(self._buffer) > self.max_buffer_length:
            last_space = self._buffer.rfind(' ', 0, self.max_buffer_length)
            if last_space > self.min_sentence_length:
                sentence = self._buffer[:last_space].strip()
                self._buffer = self._buffer[last_space:].lstrip()

                if self.on_sentence and sentence:
                    self.on_sentence(sentence)

                return sentence

        return None

    def flush(self) -> Optional[str]:
        """Flush remaining buffer content.

        Returns:
            Remaining text or None
        """
        if self._buffer.strip():
            sentence = self._buffer.strip()
            self._buffer = ""

            if self.on_sentence and sentence:
                self.on_sentence(sentence)

            return sentence
        return None

    def reset(self) -> None:
        """Reset the buffer."""
        self._buffer = ""

    def process_stream(self, tokens: Iterator[str]) -> Iterator[str]:
        """Process a stream of tokens and yield sentences.

        Args:
            tokens: Iterator of tokens

        Yields:
            Complete sentences
        """
        for token in tokens:
            sentence = self.add_token(token)
            if sentence:
                yield sentence

        # Flush remaining
        final = self.flush()
        if final:
            yield final

    async def process_stream_async(
        self, tokens: AsyncIterator[str]
    ) -> AsyncIterator[str]:
        """Process an async stream of tokens and yield sentences.

        Args:
            tokens: Async iterator of tokens

        Yields:
            Complete sentences
        """
        async for token in tokens:
            sentence = self.add_token(token)
            if sentence:
                yield sentence

        # Flush remaining
        final = self.flush()
        if final:
            yield final

    @property
    def buffer_content(self) -> str:
        """Get current buffer content."""
        return self._buffer

    @property
    def buffer_length(self) -> int:
        """Get current buffer length."""
        return len(self._buffer)


def split_into_sentences(text: str) -> list[str]:
    """Split text into sentences.

    Args:
        text: Text to split

    Returns:
        List of sentences
    """
    # Simple regex-based sentence splitting
    # Handles common cases but not perfect
    sentence_pattern = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_pattern, text)
    return [s.strip() for s in sentences if s.strip()]
