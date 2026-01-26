"""Tool registry and handlers for LLM tool use."""

import asyncio
import subprocess
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import urlparse

import httpx

# Optional: trafilatura for better web content extraction
try:
    import trafilatura
    HAS_TRAFILATURA = True
except ImportError:
    HAS_TRAFILATURA = False

# Optional: BeautifulSoup as fallback
try:
    from bs4 import BeautifulSoup
    HAS_BS4 = True
except ImportError:
    HAS_BS4 = False


@dataclass
class ToolResult:
    """Result of a tool execution."""
    
    success: bool
    output: str
    error: Optional[str] = None


@dataclass
class ToolDefinition:
    """Definition of a tool."""
    
    name: str
    description: str
    args: dict[str, str]  # arg_name -> type description
    triggers: list[str]  # Keywords that suggest using this tool
    handler: Callable[..., ToolResult]
    requires_confirmation: bool = False
    enabled: bool = True


class ToolRegistry:
    """Registry of available tools."""
    
    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
        
        # Tool settings
        self.fetch_timeout: float = 10.0
        self.max_content_length: int = 8000
        self.command_timeout: float = 30.0
        self.allowed_commands: list[str] = [
            "ls", "pwd", "cat", "head", "tail", "grep", "find", "wc",
            "echo", "date", "whoami", "uname", "df", "du", "env",
            "curl", "wget", "python", "python3", "node", "npm"
        ]
        
        # Register default tools
        self._register_default_tools()
    
    def _register_default_tools(self) -> None:
        """Register the default set of tools."""
        
        # fetch_url tool
        self.register(ToolDefinition(
            name="fetch_url",
            description="Fetch and extract text content from a URL/website",
            args={"url": "The URL to fetch (must start with http:// or https://)"},
            triggers=["go to", "navigate to", "fetch", "look at", "open", "check out", 
                     "visit", "browse", "read from", "get from", "what does", "show me"],
            handler=self._fetch_url_handler,
        ))
        
        # run_command tool
        self.register(ToolDefinition(
            name="run_command",
            description="Execute a shell command and return the output",
            args={"command": "The shell command to execute"},
            triggers=["run", "execute", "shell", "terminal", "command", "script"],
            handler=self._run_command_handler,
            requires_confirmation=True,
        ))
        
        # read_file tool
        self.register(ToolDefinition(
            name="read_file",
            description="Read the contents of a local file",
            args={"path": "The path to the file to read"},
            triggers=["read file", "show file", "open file", "cat", "contents of"],
            handler=self._read_file_handler,
        ))
        
        # get_datetime tool
        self.register(ToolDefinition(
            name="get_datetime",
            description="Get the current date and time",
            args={},
            triggers=["what time", "what date", "current time", "today", "now"],
            handler=self._get_datetime_handler,
        ))
        
        # web_search tool (using DuckDuckGo)
        self.register(ToolDefinition(
            name="web_search",
            description="Search the web for information",
            args={"query": "The search query"},
            triggers=["search for", "look up", "find information", "google", "search the web"],
            handler=self._web_search_handler,
        ))
        
        # get_weather tool
        self.register(ToolDefinition(
            name="get_weather",
            description="Get current weather for a location",
            args={"location": "City name or location"},
            triggers=["weather in", "weather for", "forecast", "temperature in"],
            handler=self._get_weather_handler,
        ))
        
        # calculate tool
        self.register(ToolDefinition(
            name="calculate",
            description="Evaluate a mathematical expression",
            args={"expression": "The math expression to evaluate (e.g., '2 + 2', 'sqrt(16)')"},
            triggers=["calculate", "compute", "what is", "solve", "evaluate"],
            handler=self._calculate_handler,
        ))
    
    def register(self, tool: ToolDefinition) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
    
    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool by name."""
        return self._tools.get(name)
    
    def list_tools(self) -> list[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_enabled_tools(self) -> list[ToolDefinition]:
        """Get all enabled tools."""
        return [t for t in self._tools.values() if t.enabled]
    
    def get_all_tools(self) -> list[ToolDefinition]:
        """Get all registered tools (alias for list_tools)."""
        return self.list_tools()
    
    def set_tool_enabled(self, name: str, enabled: bool) -> bool:
        """Enable or disable a tool by name. Returns True if tool was found."""
        tool = self._tools.get(name)
        if tool is not None:
            tool.enabled = enabled
            return True
        return False
    
    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=self.fetch_timeout,
                follow_redirects=True,
                headers={"User-Agent": "Mozilla/5.0 (compatible; LocalChatbot/1.0)"}
            )
        return self._http_client
    
    async def execute(self, tool_name: str, args: dict[str, Any]) -> ToolResult:
        """Execute a tool by name with given arguments."""
        tool = self.get(tool_name)
        if tool is None:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {tool_name}"
            )
        
        if not tool.enabled:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool '{tool_name}' is disabled"
            )
        
        try:
            # Check if handler is async
            if asyncio.iscoroutinefunction(tool.handler):
                return await tool.handler(**args)
            else:
                # Run sync handler in thread pool
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, lambda: tool.handler(**args))
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Tool execution error: {str(e)}"
            )
    
    # ===== Tool Handlers =====
    
    async def _fetch_url_handler(self, url: str) -> ToolResult:
        """Fetch content from a URL."""
        # Validate URL
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return ToolResult(
                    success=False,
                    output="",
                    error="Invalid URL scheme. Only http:// and https:// are allowed."
                )
            if not parsed.netloc:
                return ToolResult(
                    success=False,
                    output="",
                    error="Invalid URL: missing domain"
                )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Invalid URL: {str(e)}"
            )
        
        try:
            client = await self._get_http_client()
            response = await client.get(url)
            response.raise_for_status()
            
            content_type = response.headers.get("content-type", "")
            html = response.text
            
            # Extract readable text
            text = self._extract_text_from_html(html, url)
            
            # Truncate if too long
            if len(text) > self.max_content_length:
                text = text[:self.max_content_length] + "\n\n[Content truncated...]"
            
            return ToolResult(
                success=True,
                output=f"Content from {url}:\n\n{text}"
            )
            
        except httpx.TimeoutException:
            return ToolResult(
                success=False,
                output="",
                error=f"Timeout fetching URL: {url}"
            )
        except httpx.HTTPStatusError as e:
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP error {e.response.status_code}: {url}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error fetching URL: {str(e)}"
            )
    
    def _extract_text_from_html(self, html: str, url: str) -> str:
        """Extract readable text from HTML."""
        # Try trafilatura first (best quality)
        if HAS_TRAFILATURA:
            try:
                text = trafilatura.extract(html, url=url, include_links=False)
                if text:
                    return text.strip()
            except Exception:
                pass
        
        # Fallback to BeautifulSoup
        if HAS_BS4:
            try:
                soup = BeautifulSoup(html, "html.parser")
                
                # Remove script and style elements
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()
                
                # Get text
                text = soup.get_text(separator="\n", strip=True)
                
                # Clean up whitespace
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                return "\n".join(lines)
            except Exception:
                pass
        
        # Last resort: regex cleanup
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def _run_command_handler(self, command: str) -> ToolResult:
        """Execute a shell command (sandboxed)."""
        # Parse the command to check if it's allowed
        parts = command.strip().split()
        if not parts:
            return ToolResult(
                success=False,
                output="",
                error="Empty command"
            )
        
        base_command = parts[0]
        
        # Check if command is in allowed list
        # Allow commands with paths (e.g., /usr/bin/python)
        cmd_name = base_command.split("/")[-1]
        if cmd_name not in self.allowed_commands:
            return ToolResult(
                success=False,
                output="",
                error=f"Command '{cmd_name}' is not in the allowed list. Allowed: {', '.join(self.allowed_commands)}"
            )
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.command_timeout,
                cwd=None,  # Use current directory
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]: {result.stderr}"
            
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            
            # Truncate if too long
            if len(output) > self.max_content_length:
                output = output[:self.max_content_length] + "\n\n[Output truncated...]"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output if output else "(no output)",
                error=None if result.returncode == 0 else f"Command exited with code {result.returncode}"
            )
            
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {self.command_timeout} seconds"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error executing command: {str(e)}"
            )
    
    def _read_file_handler(self, path: str) -> ToolResult:
        """Read contents of a local file."""
        from pathlib import Path
        
        try:
            file_path = Path(path).expanduser().resolve()
            
            # Security: prevent reading sensitive files
            sensitive_patterns = [
                ".ssh", ".gnupg", ".aws", "credentials", "secrets",
                ".env", "password", "token", ".key", ".pem"
            ]
            path_str = str(file_path).lower()
            for pattern in sensitive_patterns:
                if pattern in path_str:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"Access denied: cannot read potentially sensitive file"
                    )
            
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File not found: {path}"
                )
            
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Not a file: {path}"
                )
            
            # Check file size
            if file_path.stat().st_size > 100_000:  # 100KB limit
                return ToolResult(
                    success=False,
                    output="",
                    error=f"File too large (max 100KB)"
                )
            
            content = file_path.read_text(encoding="utf-8", errors="replace")
            
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "\n\n[Content truncated...]"
            
            return ToolResult(
                success=True,
                output=f"Contents of {path}:\n\n{content}"
            )
            
        except PermissionError:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: {path}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Error reading file: {str(e)}"
            )
    
    def _get_datetime_handler(self) -> ToolResult:
        """Get current date and time."""
        now = datetime.now()
        return ToolResult(
            success=True,
            output=f"Current date and time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}\n"
                   f"ISO format: {now.isoformat()}\n"
                   f"Unix timestamp: {int(now.timestamp())}"
        )
    
    async def _web_search_handler(self, query: str) -> ToolResult:
        """Search the web using DuckDuckGo HTML."""
        try:
            client = await self._get_http_client()
            
            # Use DuckDuckGo HTML version
            search_url = f"https://html.duckduckgo.com/html/?q={query}"
            response = await client.get(search_url)
            response.raise_for_status()
            
            # Extract search results
            results = self._parse_ddg_results(response.text)
            
            if not results:
                return ToolResult(
                    success=True,
                    output=f"No results found for: {query}"
                )
            
            output = f"Search results for '{query}':\n\n"
            for i, (title, snippet, url) in enumerate(results[:5], 1):
                output += f"{i}. {title}\n   {snippet}\n   URL: {url}\n\n"
            
            return ToolResult(success=True, output=output)
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Search error: {str(e)}"
            )
    
    def _parse_ddg_results(self, html: str) -> list[tuple[str, str, str]]:
        """Parse DuckDuckGo HTML results."""
        results = []
        
        if HAS_BS4:
            try:
                soup = BeautifulSoup(html, "html.parser")
                for result in soup.select(".result"):
                    title_elem = result.select_one(".result__title a")
                    snippet_elem = result.select_one(".result__snippet")
                    
                    if title_elem:
                        title = title_elem.get_text(strip=True)
                        url = title_elem.get("href", "")
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                        results.append((title, snippet, url))
            except Exception:
                pass
        
        return results
    
    async def _get_weather_handler(self, location: str) -> ToolResult:
        """Get weather using wttr.in."""
        try:
            client = await self._get_http_client()
            
            # Use wttr.in with text format
            weather_url = f"https://wttr.in/{location}?format=3"
            response = await client.get(weather_url)
            response.raise_for_status()
            
            weather = response.text.strip()
            
            # Get more details
            detail_url = f"https://wttr.in/{location}?format=%l:+%c+%t+(feels+like+%f)+%h+humidity,+%w+wind"
            detail_response = await client.get(detail_url)
            detail = detail_response.text.strip()
            
            return ToolResult(
                success=True,
                output=f"Weather: {weather}\nDetails: {detail}"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Weather error: {str(e)}"
            )
    
    def _calculate_handler(self, expression: str) -> ToolResult:
        """Safely evaluate a math expression."""
        import math
        
        # Allowed names for evaluation
        allowed_names = {
            "abs": abs, "round": round, "min": min, "max": max,
            "sum": sum, "pow": pow, "int": int, "float": float,
            "sqrt": math.sqrt, "sin": math.sin, "cos": math.cos,
            "tan": math.tan, "log": math.log, "log10": math.log10,
            "exp": math.exp, "pi": math.pi, "e": math.e,
            "floor": math.floor, "ceil": math.ceil,
        }
        
        # Clean expression
        expr = expression.strip()
        
        # Check for dangerous patterns
        dangerous = ["import", "exec", "eval", "open", "file", "__", "os.", "sys."]
        for d in dangerous:
            if d in expr.lower():
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Invalid expression: contains '{d}'"
                )
        
        try:
            # Compile and evaluate with restricted namespace
            result = eval(expr, {"__builtins__": {}}, allowed_names)
            return ToolResult(
                success=True,
                output=f"{expression} = {result}"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Calculation error: {str(e)}"
            )
    
    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None


# Global tool registry instance
tool_registry = ToolRegistry()


def generate_tool_prompt() -> str:
    """Generate the tool instructions for the system prompt."""
    tools = tool_registry.get_enabled_tools()
    
    if not tools:
        return ""
    
    prompt = """
## Available Tools

You have access to the following tools. You MUST use them when needed.

**CRITICAL RULES:**
1. You do NOT know the current date or time - you MUST use the get_datetime tool
2. You CANNOT browse the internet directly - you MUST use fetch_url or web_search tools
3. You CANNOT see local files - you MUST use read_file tool
4. NEVER make up information - USE THE TOOLS to get real data

When you need to use a tool, output a tool call in this EXACT format:

<tool_call>
{"tool": "tool_name", "args": {"arg1": "value1"}}
</tool_call>

After receiving tool results, incorporate them naturally into your response.

### Tools:
"""
    
    for tool in tools:
        args_str = ", ".join([f'"{k}": "{v}"' for k, v in tool.args.items()])
        if args_str:
            args_str = f'{{{args_str}}}'
        else:
            args_str = '{}'
        
        prompt += f"\n**{tool.name}**: {tool.description}\n"
        prompt += f"  - Arguments: {args_str}\n"
        prompt += f"  - Use when: {', '.join(tool.triggers[:4])}\n"
    
    prompt += """
### Examples:

User: "What time is it?" or "What's the date?" or "What is the current date and time?"
You MUST respond with:
<tool_call>
{"tool": "get_datetime", "args": {}}
</tool_call>

User: "Go to https://example.com and tell me what it's about"
You MUST respond with:
<tool_call>
{"tool": "fetch_url", "args": {"url": "https://example.com"}}
</tool_call>

User: "What's the weather in Tokyo?"
You MUST respond with:
<tool_call>
{"tool": "get_weather", "args": {"location": "Tokyo"}}
</tool_call>

REMEMBER: For date/time questions, ALWAYS output the get_datetime tool call first. Do NOT guess or make up times.
"""
    
    return prompt
