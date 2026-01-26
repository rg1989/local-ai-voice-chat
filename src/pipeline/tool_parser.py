"""Parser for detecting and extracting tool calls from LLM output."""

import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedToolCall:
    """A parsed tool call from LLM output."""
    
    tool: str
    args: dict
    raw_match: str  # The full <tool_call>...</tool_call> block
    start_pos: int  # Start position in text
    end_pos: int    # End position in text


class ToolCallParser:
    """Parser for extracting tool calls from LLM responses."""
    
    # Pattern to match <tool_call>...</tool_call> blocks
    TOOL_CALL_PATTERN = re.compile(
        r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
        re.DOTALL | re.IGNORECASE
    )
    
    # Alternative patterns for flexibility
    ALT_PATTERNS = [
        # Markdown code block style
        re.compile(r'```tool_call\s*(\{.*?\})\s*```', re.DOTALL),
        # JSON block with tool key
        re.compile(r'```json\s*(\{"tool":\s*"[^"]+",\s*"args":\s*\{.*?\}\})\s*```', re.DOTALL),
        # Raw JSON with tool key (no wrapper) - matches {"tool": "...", "args": {...}}
        re.compile(r'(\{"tool":\s*"[^"]+",\s*"args":\s*\{[^}]*\}\})', re.DOTALL),
        # Raw JSON with args first
        re.compile(r'(\{"args":\s*\{[^}]*\},\s*"tool":\s*"[^"]+"\})', re.DOTALL),
    ]
    
    def __init__(self):
        self._buffer = ""
    
    def find_tool_calls(self, text: str) -> list[ParsedToolCall]:
        """Find all tool calls in the given text.
        
        Args:
            text: The text to search for tool calls
            
        Returns:
            List of parsed tool calls found in the text
        """
        tool_calls = []
        
        # Try main pattern first
        for match in self.TOOL_CALL_PATTERN.finditer(text):
            parsed = self._parse_match(match, match.group(1))
            if parsed:
                tool_calls.append(parsed)
        
        # If no matches, try alternative patterns
        if not tool_calls:
            for pattern in self.ALT_PATTERNS:
                for match in pattern.finditer(text):
                    parsed = self._parse_match(match, match.group(1))
                    if parsed:
                        tool_calls.append(parsed)
        
        return tool_calls
    
    def _parse_match(self, match: re.Match, json_str: str) -> Optional[ParsedToolCall]:
        """Parse a regex match into a ParsedToolCall."""
        try:
            # Clean the JSON string
            json_str = json_str.strip()
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Validate structure
            if "tool" not in data:
                return None
            
            return ParsedToolCall(
                tool=data["tool"],
                args=data.get("args", {}),
                raw_match=match.group(0),
                start_pos=match.start(),
                end_pos=match.end()
            )
        except json.JSONDecodeError:
            # Try to fix common JSON issues
            fixed = self._try_fix_json(json_str)
            if fixed:
                try:
                    data = json.loads(fixed)
                    if "tool" in data:
                        return ParsedToolCall(
                            tool=data["tool"],
                            args=data.get("args", {}),
                            raw_match=match.group(0),
                            start_pos=match.start(),
                            end_pos=match.end()
                        )
                except json.JSONDecodeError:
                    pass
            return None
    
    def _try_fix_json(self, json_str: str) -> Optional[str]:
        """Try to fix common JSON formatting issues."""
        # Replace single quotes with double quotes
        fixed = json_str.replace("'", '"')
        
        # Remove trailing commas before closing braces
        fixed = re.sub(r',\s*}', '}', fixed)
        fixed = re.sub(r',\s*]', ']', fixed)
        
        # Add missing quotes around unquoted keys
        fixed = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)
        
        return fixed
    
    def has_tool_call(self, text: str) -> bool:
        """Check if text contains any tool call.
        
        Args:
            text: The text to check
            
        Returns:
            True if a tool call is found
        """
        return bool(self.TOOL_CALL_PATTERN.search(text)) or \
               any(p.search(text) for p in self.ALT_PATTERNS)
    
    def has_partial_tool_call(self, text: str) -> bool:
        """Check if text contains a partial (incomplete) tool call.
        
        This is useful during streaming to detect if a tool call is being formed.
        
        Args:
            text: The text to check
            
        Returns:
            True if a partial tool call is detected
        """
        # Check for opening tag without closing
        if "<tool_call>" in text.lower() and "</tool_call>" not in text.lower():
            return True
        
        # Check for opening code block
        if "```tool_call" in text.lower() and text.count("```") % 2 == 1:
            return True
        
        # Check for partial raw JSON tool call
        if '{"tool":' in text and not text.rstrip().endswith('}'):
            return True
        
        return False
    
    def remove_tool_calls(self, text: str) -> str:
        """Remove all tool calls from text, returning the clean text.
        
        Args:
            text: The text to clean
            
        Returns:
            Text with tool calls removed
        """
        # Remove main pattern
        cleaned = self.TOOL_CALL_PATTERN.sub('', text)
        
        # Remove alternative patterns
        for pattern in self.ALT_PATTERNS:
            cleaned = pattern.sub('', cleaned)
        
        # Clean up extra whitespace
        cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
        
        return cleaned.strip()
    
    def convert_tool_calls_for_speech(self, text: str) -> str:
        """Convert tool calls to speech-friendly announcements.
        
        Replaces raw tool call syntax with a friendly "Using tool: [tool_name]."
        announcement suitable for text-to-speech.
        
        Args:
            text: The text containing tool calls
            
        Returns:
            Text with tool calls replaced by speech-friendly announcements
        """
        result = text
        
        # Find all tool calls and replace with friendly text
        tool_calls = self.find_tool_calls(text)
        
        # Sort by position in reverse order to replace from end to start
        # This preserves positions of earlier matches
        tool_calls.sort(key=lambda tc: tc.start_pos, reverse=True)
        
        for tool_call in tool_calls:
            # Replace the raw tool call with a friendly announcement
            announcement = f"Using tool: {tool_call.tool}."
            result = result[:tool_call.start_pos] + announcement + result[tool_call.end_pos:]
        
        # Clean up extra whitespace
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        return result.strip()
    
    def extract_text_before_tool_call(self, text: str) -> tuple[str, Optional[str]]:
        """Split text into content before the first tool call and the rest.
        
        Args:
            text: The text to split
            
        Returns:
            Tuple of (text before tool call, remaining text including tool call)
            If no tool call found, returns (text, None)
        """
        # Find first tool call
        match = self.TOOL_CALL_PATTERN.search(text)
        if not match:
            for pattern in self.ALT_PATTERNS:
                match = pattern.search(text)
                if match:
                    break
        
        if match:
            before = text[:match.start()].strip()
            after = text[match.start():]
            return (before, after)
        
        return (text, None)


# Global parser instance
tool_parser = ToolCallParser()
