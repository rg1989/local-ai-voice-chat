"""Tool registry and handlers for LLM tool use."""

import asyncio
import subprocess
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

import httpx

from src.storage.memories import memory_storage

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
        self.fetch_timeout: float = 30.0
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
        
        # get_date tool
        self.register(ToolDefinition(
            name="get_date",
            description="Get the current date and time",
            args={},
            triggers=[
                "what time", "what's the time", "what is the time", "the time",
                "what date", "what's the date", "what is the date", "the date",
                "what day", "what's the day", "what is the day", "what day is it",
                "current time", "current date", "current day",
                "today", "today's date", "what is today",
                "now", "right now",
                "what year", "what's the year", "what is the year", "current year",
                "what month", "what's the month", "current month",
                "date today", "time now", "day today",
                "tell me the time", "tell me the date",
                "do you know the time", "do you know the date",
                "can you tell me the time", "can you tell me the date"
            ],
            handler=self._get_date_handler,
        ))
        
        # web_search tool (using DuckDuckGo)
        self.register(ToolDefinition(
            name="web_search",
            description="Search the web for information",
            args={"query": "The search query"},
            triggers=[
                # Direct search requests
                "search", "search for", "search online", "search the web", "search the internet",
                "look up", "look for", "lookup",
                "find", "find out", "find information", "find me",
                # Search engines
                "google", "google it", "google search", "bing", "duckduckgo",
                # Research/information gathering
                "research", "investigate", "explore",
                "what do you know about", "tell me about", "information about", "info on",
                "learn about", "read about",
                # Questions that need web search
                "who is", "who was", "who are",
                "what is", "what are", "what was",
                "where is", "where are", "where can",
                "when is", "when was", "when did",
                "why is", "why does", "why did",
                "how does", "how do", "how to", "how can",
                # News and current events
                "latest news", "recent news", "news about", "current events",
                "what happened", "what's happening", "trending",
                # Common phrases
                "can you find", "can you search", "can you look up",
                "I want to know", "I need to know", "I'm curious about",
                "check online", "check the internet", "check the web"
            ],
            handler=self._web_search_handler,
        ))
        
        # get_weather tool
        self.register(ToolDefinition(
            name="get_weather",
            description="Get current weather for a location",
            args={"location": "City name or location"},
            triggers=[
                "weather in", "weather for", "weather", "what's the weather",
                "what is the weather", "how's the weather", "how is the weather",
                "forecast", "forecast for", "forecast in",
                "temperature", "temperature in", "temperature for",
                "what's the temperature", "what is the temperature",
                "how hot", "how cold", "is it raining", "is it snowing",
                "climate", "conditions in"
            ],
            handler=self._get_weather_handler,
        ))
        
        # calculate tool
        self.register(ToolDefinition(
            name="calculate",
            description="Evaluate a mathematical expression",
            args={"expression": "The math expression to evaluate (e.g., '2 + 2', 'sqrt(16)')"},
            triggers=[
                # Direct calculation requests
                "calculate", "compute", "evaluate", "solve",
                "what is", "what's", "how much is", "how many is",
                # Math operations
                "add", "subtract", "multiply", "divide", "plus", "minus", "times",
                "sum of", "total of", "product of", "difference of", "quotient of",
                # Percentages
                "percent", "percentage", "% of", "percent of",
                "what percent", "what percentage",
                # Advanced math
                "square root", "sqrt", "cube root",
                "power of", "to the power", "squared", "cubed", "exponent",
                "logarithm", "log of", "natural log", "ln of",
                "sine", "cosine", "tangent", "sin of", "cos of", "tan of",
                # Comparisons
                "average", "mean", "median", "sum", "total",
                "minimum", "maximum", "min of", "max of",
                # Financial/practical
                "tip", "discount", "tax", "interest", "compound interest",
                "split the bill", "divide by", "per person",
                "convert", "conversion",
                # Common patterns
                "equals", "equal to", "result of",
                "work out", "figure out", "help me calculate",
                "do the math", "crunch the numbers",
                # Numbers in context
                "divided by", "multiplied by", "added to", "subtracted from",
                "times", "over", "raised to"
            ],
            handler=self._calculate_handler,
        ))
        
        # add_memory tool - store information across all conversations
        self.register(ToolDefinition(
            name="add_memory",
            description="Store important information to remember across all conversations. Use this when the user asks you to remember something permanently.",
            args={
                "content": "The information to remember (e.g., 'User's name is John', 'User prefers dark mode')",
                "tags": "Optional comma-separated tags for categorization (e.g., 'personal,preferences')"
            },
            triggers=[
                "remember", "remember this", "remember that", "remember my",
                "add to memory", "save to memory", "store in memory",
                "memorize", "memorize this", "memorize that",
                "don't forget", "keep in mind", "note that",
                "save this", "store this", "keep this",
                "my name is", "i am called", "call me",
                "i like", "i prefer", "i want you to remember",
                "always remember", "never forget"
            ],
            handler=self._add_memory_handler,
        ))
        
        # check_memory tool - recall stored information
        self.register(ToolDefinition(
            name="check_memory",
            description="Search and recall stored memories. Use this when the user asks what you remember about something.",
            args={
                "query": "What to search for in memories (e.g., 'name', 'preferences', 'birthday')"
            },
            triggers=[
                "recall", "recall my", "what do you remember",
                "check memory", "check your memory", "search memory",
                "do you remember", "do you recall",
                "what's my", "what is my", "what are my",
                "you should know", "you should remember",
                "have i told you", "did i tell you",
                "what did i say about", "what did i tell you about"
            ],
            handler=self._check_memory_handler,
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
            # Use realistic browser headers to avoid being blocked
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }
            self._http_client = httpx.AsyncClient(
                timeout=self.fetch_timeout,
                follow_redirects=True,
                headers=headers,
                verify=False,  # Disable SSL verification to avoid certificate issues
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
            
            # Check for Cloudflare or similar protection blocking
            if response.status_code == 403:
                response_text = response.text.lower()
                if "cloudflare" in response_text or "attention required" in response_text:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"This website ({parsed.netloc}) is protected by Cloudflare and blocks automated access. Ask the user to copy-paste the article content directly, or try a different source."
                    )
            
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
            print(f"[TOOL] Timeout fetching URL: {url}")
            return ToolResult(
                success=False,
                output="",
                error=f"Timeout fetching URL (tried for 30s): {url}"
            )
        except httpx.HTTPStatusError as e:
            print(f"[TOOL] HTTP error {e.response.status_code} for URL: {url}")
            # Check for Cloudflare block
            if e.response.status_code == 403:
                response_text = e.response.text.lower()
                if "cloudflare" in response_text or "attention required" in response_text:
                    return ToolResult(
                        success=False,
                        output="",
                        error=f"This website is protected by Cloudflare and blocks automated access. The user should copy-paste the article content directly."
                    )
            return ToolResult(
                success=False,
                output="",
                error=f"HTTP error {e.response.status_code}: {url}"
            )
        except Exception as e:
            print(f"[TOOL] Error fetching URL {url}: {str(e)}")
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
    
    def _get_date_handler(self) -> ToolResult:
        """Get current date and time in Jerusalem timezone."""
        jerusalem_tz = ZoneInfo("Asia/Jerusalem")
        now = datetime.now(jerusalem_tz)
        return ToolResult(
            success=True,
            output=f"The current date and time is: {now.strftime('%B %d, %Y at %I:%M %p')} (Jerusalem time). Use this EXACT information in your response."
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
                
                # Try multiple selectors as DDG structure may vary
                selectors = [
                    (".result", ".result__title a", ".result__snippet"),
                    (".web-result", ".result__a", ".result__snippet"),
                    (".results_links", "a.result__a", ".result__snippet"),
                ]
                
                for result_sel, title_sel, snippet_sel in selectors:
                    for result in soup.select(result_sel):
                        title_elem = result.select_one(title_sel)
                        snippet_elem = result.select_one(snippet_sel)
                        
                        if title_elem:
                            title = title_elem.get_text(strip=True)
                            url = title_elem.get("href", "")
                            snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""
                            if title and len(title) > 3:  # Filter out empty/junk results
                                results.append((title, snippet, url))
                    
                    if results:
                        break  # Found results with this selector
                
                # Fallback: try to find any links with reasonable content
                if not results:
                    for link in soup.find_all("a", href=True):
                        href = link.get("href", "")
                        text = link.get_text(strip=True)
                        if href.startswith("http") and len(text) > 10 and "duckduckgo" not in href.lower():
                            # Get nearby text as snippet
                            parent = link.parent
                            snippet = parent.get_text(strip=True)[:200] if parent else ""
                            results.append((text, snippet, href))
                            if len(results) >= 5:
                                break
                                
            except Exception as e:
                print(f"[TOOL] DDG parse error: {e}")
        
        # Regex fallback if BS4 failed or not available
        if not results:
            import re
            # Try to extract URLs and titles from the raw HTML
            pattern = r'<a[^>]+href="(https?://[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)
            for url, title in matches:
                if "duckduckgo" not in url.lower() and len(title) > 10:
                    results.append((title.strip(), "", url))
                    if len(results) >= 5:
                        break
        
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
    
    def _add_memory_handler(self, content: str, tags: str = "") -> ToolResult:
        """Add information to persistent memory."""
        if not content or not content.strip():
            return ToolResult(
                success=False,
                output="",
                error="Memory content cannot be empty"
            )
        
        # Parse tags from comma-separated string
        tag_list = []
        if tags and tags.strip():
            tag_list = [t.strip() for t in tags.split(",") if t.strip()]
        
        try:
            # Get conversation_id from context if available (will be set by caller)
            conversation_id = getattr(self, '_current_conversation_id', None)
            
            memory = memory_storage.add(
                content=content.strip(),
                source_conversation_id=conversation_id,
                tags=tag_list
            )
            
            tags_str = f" with tags [{', '.join(tag_list)}]" if tag_list else ""
            return ToolResult(
                success=True,
                output=f"Memory saved{tags_str}: \"{content.strip()}\""
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to save memory: {str(e)}"
            )
    
    def _check_memory_handler(self, query: str) -> ToolResult:
        """Search and recall stored memories."""
        try:
            memories = memory_storage.search(query)
            
            if not memories:
                return ToolResult(
                    success=True,
                    output=f"No memories found matching '{query}'. The memory is empty or nothing matches your search."
                )
            
            # Format the results
            results = []
            for i, memory in enumerate(memories[:10], 1):  # Limit to 10 results
                tags_str = f" [{', '.join(memory.tags)}]" if memory.tags else ""
                results.append(f"{i}. {memory.content}{tags_str}")
            
            output = f"Found {len(memories)} memor{'y' if len(memories) == 1 else 'ies'} matching '{query}':\n\n"
            output += "\n".join(results)
            
            return ToolResult(
                success=True,
                output=output
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output="",
                error=f"Failed to search memories: {str(e)}"
            )
    
    def set_conversation_context(self, conversation_id: Optional[str]) -> None:
        """Set the current conversation context for memory attribution."""
        self._current_conversation_id = conversation_id
    
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
1. You do NOT know the current date or time - you MUST use the get_date tool. Your training data is outdated.
2. You CANNOT browse the internet directly - you MUST use fetch_url or web_search tools
3. You CANNOT see local files - you MUST use read_file tool
4. NEVER make up information - USE THE TOOLS to get real data
5. NEVER assume a URL is invalid based on dates. Your training data cutoff is outdated. If a user provides a URL, ALWAYS fetch it with fetch_url.
6. When a user asks you to summarize/read/check a URL, you MUST use fetch_url immediately. Do NOT discuss whether the URL is valid - just fetch it.

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

User: "What time is it?"
You MUST respond with:
<tool_call>
{"tool": "get_date", "args": {}}
</tool_call>

User: "What's the date?" or "What is the date today?"
You MUST respond with:
<tool_call>
{"tool": "get_date", "args": {}}
</tool_call>

User: "What day is it?" or "What is today?"
You MUST respond with:
<tool_call>
{"tool": "get_date", "args": {}}
</tool_call>

User: "What year is it?" or "What is the current year?"
You MUST respond with:
<tool_call>
{"tool": "get_date", "args": {}}
</tool_call>

User: "Tell me the time" or "Can you tell me the date?"
You MUST respond with:
<tool_call>
{"tool": "get_date", "args": {}}
</tool_call>

User: "Go to https://example.com and tell me what it's about"
You MUST respond with:
<tool_call>
{"tool": "fetch_url", "args": {"url": "https://example.com"}}
</tool_call>

User: "Can you summarize this https://www.somesite.com/article/2026/..."
You MUST respond with:
<tool_call>
{"tool": "fetch_url", "args": {"url": "https://www.somesite.com/article/2026/..."}}
</tool_call>

User: "Search for Python tutorials"
You MUST respond with:
<tool_call>
{"tool": "web_search", "args": {"query": "Python tutorials"}}
</tool_call>

User: "Look up the latest news on AI"
You MUST respond with:
<tool_call>
{"tool": "web_search", "args": {"query": "latest news AI"}}
</tool_call>

User: "Who is Elon Musk?"
You MUST respond with:
<tool_call>
{"tool": "web_search", "args": {"query": "Elon Musk"}}
</tool_call>

User: "Search online for best restaurants in Tokyo"
You MUST respond with:
<tool_call>
{"tool": "web_search", "args": {"query": "best restaurants in Tokyo"}}
</tool_call>

User: "Find information about climate change"
You MUST respond with:
<tool_call>
{"tool": "web_search", "args": {"query": "climate change information"}}
</tool_call>

User: "Google how to make pasta"
You MUST respond with:
<tool_call>
{"tool": "web_search", "args": {"query": "how to make pasta"}}
</tool_call>

User: "What's the weather in Tokyo?"
You MUST respond with:
<tool_call>
{"tool": "get_weather", "args": {"location": "Tokyo"}}
</tool_call>

User: "What is the temperature in Paris?"
You MUST respond with:
<tool_call>
{"tool": "get_weather", "args": {"location": "Paris"}}
</tool_call>

User: "What's the forecast for London?"
You MUST respond with:
<tool_call>
{"tool": "get_weather", "args": {"location": "London"}}
</tool_call>

User: "How's the weather in New York?"
You MUST respond with:
<tool_call>
{"tool": "get_weather", "args": {"location": "New York"}}
</tool_call>

User: "Is it raining in Seattle?"
You MUST respond with:
<tool_call>
{"tool": "get_weather", "args": {"location": "Seattle"}}
</tool_call>

User: "What is 15% of 250?"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "0.15 * 250"}}
</tool_call>

User: "Calculate 45 times 23"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "45 * 23"}}
</tool_call>

User: "What's the square root of 144?"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "sqrt(144)"}}
</tool_call>

User: "How much is 500 divided by 7?"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "500 / 7"}}
</tool_call>

User: "Add 123 and 456"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "123 + 456"}}
</tool_call>

User: "What's 20% tip on $85?"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "0.20 * 85"}}
</tool_call>

User: "Split $120 between 4 people"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "120 / 4"}}
</tool_call>

User: "What is 5 to the power of 3?"
You MUST respond with:
<tool_call>
{"tool": "calculate", "args": {"expression": "pow(5, 3)"}}
</tool_call>

User: "Remember that my name is John"
You MUST respond with:
<tool_call>
{"tool": "add_memory", "args": {"content": "User's name is John", "tags": "personal,name"}}
</tool_call>

User: "Add to memory that I prefer dark mode"
You MUST respond with:
<tool_call>
{"tool": "add_memory", "args": {"content": "User prefers dark mode", "tags": "preferences"}}
</tool_call>

User: "Remember I'm allergic to peanuts"
You MUST respond with:
<tool_call>
{"tool": "add_memory", "args": {"content": "User is allergic to peanuts", "tags": "health,allergies"}}
</tool_call>

User: "My birthday is March 15th, please remember that"
You MUST respond with:
<tool_call>
{"tool": "add_memory", "args": {"content": "User's birthday is March 15th", "tags": "personal,birthday"}}
</tool_call>

User: "What's my name?" or "Do you remember my name?"
You MUST respond with:
<tool_call>
{"tool": "check_memory", "args": {"query": "name"}}
</tool_call>

User: "What do you remember about me?"
You MUST respond with:
<tool_call>
{"tool": "check_memory", "args": {"query": ""}}
</tool_call>

User: "Do you recall my preferences?"
You MUST respond with:
<tool_call>
{"tool": "check_memory", "args": {"query": "preferences"}}
</tool_call>

User: "What did I tell you about my allergies?"
You MUST respond with:
<tool_call>
{"tool": "check_memory", "args": {"query": "allergies"}}
</tool_call>

CRITICAL REMINDERS:
- For ANY date/time/day/year/month question, ALWAYS use get_date. You do NOT know the current date or time. Do NOT guess or assume.
- When user provides a URL, ALWAYS use fetch_url. Do NOT refuse based on the date in the URL.
- For ANY weather/temperature/forecast questions, ALWAYS use get_weather with the location. Do NOT guess weather.
- For ANY math/calculation/percentage/arithmetic question, ALWAYS use calculate. You are BAD at math. Do NOT try to compute in your head.
- For ANY search/lookup/research question, ALWAYS use web_search. When user says "search", they mean search the internet.
- For questions about people, places, events, or facts you're unsure about, use web_search to get accurate information.
- Your training data is outdated. You do NOT know what year it is. The current year may be 2025, 2026, or later. USE THE TOOLS.
- NEVER say "I don't have access to real-time information" - you DO have access through these tools. USE THEM.
- NEVER attempt mental arithmetic - ALWAYS use the calculate tool for any numbers.
- When in doubt, USE A TOOL rather than guessing or making up information.
- When user asks to "remember" something, ALWAYS use add_memory. Memories persist across ALL conversations.
- When user asks "what's my name", "do you remember", "what did I tell you", ALWAYS use check_memory first.
- Memories are PERSISTENT and shared across all chats. Use them to provide personalized responses.
"""
    
    return prompt
