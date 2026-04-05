"""ForgeGod MCP client — connect to external Model Context Protocol servers."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx

from forgegod.tools import register_tool

logger = logging.getLogger("forgegod.mcp")

# Active MCP connections (server_name → transport)
_MCP_SERVERS: dict[str, "MCPConnection"] = {}


class MCPConnection:
    """Lightweight MCP client over stdio or SSE transport."""

    def __init__(self, name: str, command: list[str] | None = None, url: str | None = None) -> None:
        """Initialize an MCP connection.

        Args:
            name: Server name for identification
            command: Command list for stdio transport
            url: URL for SSE transport
        """
        self.name = name
        self.command = command  # stdio transport
        self.url = url  # SSE transport
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._tools: list[dict] = []

    async def connect(self) -> str:
        """Connect and discover tools from the MCP server.

        Returns:
            Status message indicating connection success or failure
        """
        if self.url:
            return await self._connect_sse()
        if self.command:
            return await self._connect_stdio()
        return "Error: No transport configured (need command or url)"

    async def _connect_stdio(self) -> str:
        """Connect via stdio (spawn subprocess).

        Returns:
            Status message indicating connection success or failure
        """
        try:
            self._process = await asyncio.create_subprocess_exec(
                *self.command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            # Initialize
            init_result = await self._send_jsonrpc("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "forgegod", "version": "0.1.0"},
            })
            if "error" in init_result:
                return f"Error initializing: {init_result['error']}"

            # Notify initialized
            await self._send_notification("notifications/initialized", {})

            # List tools
            tools_result = await self._send_jsonrpc("tools/list", {})
            self._tools = tools_result.get("result", {}).get("tools", [])
            return f"Connected to {self.name}: {len(self._tools)} tools available"

        except Exception as e:
            return f"Error connecting to {self.name}: {e}"

    async def _connect_sse(self) -> str:
        """Connect via SSE transport (HTTP).

        Returns:
            Status message indicating connection success or failure
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Discover endpoint
                resp = await client.get(f"{self.url}/sse")
                resp.raise_for_status()
                # For SSE, we'll use HTTP POST for tool calls
                self._tools = []
                return f"Connected to {self.name} via SSE at {self.url}"
        except Exception as e:
            return f"Error connecting to {self.name}: {e}"

    async def call_tool(self, tool_name: str, arguments: dict) -> str:
        """Call a tool on this MCP server."""
        if self._process and self._process.stdin:
            result = await self._send_jsonrpc("tools/call", {
                "name": tool_name,
                "arguments": arguments,
            })
            if "error" in result:
                return f"Error: {result['error']}"
            content = result.get("result", {}).get("content", [])
            texts = [c.get("text", "") for c in content if c.get("type") == "text"]
            return "\n".join(texts) if texts else json.dumps(content)

        elif self.url:
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{self.url}/call",
                        json={"tool": tool_name, "arguments": arguments},
                    )
                    resp.raise_for_status()
                    return resp.text
            except Exception as e:
                return f"Error calling {tool_name}: {e}"

        return f"Error: Not connected to {self.name}"

    async def _send_jsonrpc(self, method: str, params: dict) -> dict:
        """Send a JSON-RPC request and wait for response."""
        if not self._process or not self._process.stdin or not self._process.stdout:
            return {"error": "Process not running"}

        self._request_id += 1
        request = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params,
        }
        payload = json.dumps(request) + "\n"
        self._process.stdin.write(payload.encode())
        await self._process.stdin.drain()

        # Read response line
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(), timeout=30.0
            )
            return json.loads(line.decode())
        except asyncio.TimeoutError:
            return {"error": "Timeout waiting for response"}
        except json.JSONDecodeError:
            return {"error": "Invalid JSON response"}

    async def _send_notification(self, method: str, params: dict):
        """Send a JSON-RPC notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return
        notification = {"jsonrpc": "2.0", "method": method, "params": params}
        payload = json.dumps(notification) + "\n"
        self._process.stdin.write(payload.encode())
        await self._process.stdin.drain()

    async def close(self):
        """Close the MCP connection."""
        if self._process:
            self._process.terminate()
            await self._process.wait()
            self._process = None

    @property
    def tool_names(self) -> list[str]:
        return [t.get("name", "") for t in self._tools]


# ── Tool handlers ──


async def mcp_connect(server_name: str, command: str = "", url: str = "") -> str:
    """Connect to an MCP server."""
    if not command and not url:
        return "Error: Provide either 'command' (stdio) or 'url' (SSE)"

    cmd_list = command.split() if command else None
    conn = MCPConnection(server_name, command=cmd_list, url=url or None)
    result = await conn.connect()
    if not result.startswith("Error"):
        _MCP_SERVERS[server_name] = conn
    return result


async def mcp_call(server: str, tool: str, arguments: str = "{}") -> str:
    """Call a tool on a connected MCP server."""
    if server not in _MCP_SERVERS:
        return f"Error: Not connected to '{server}'. Use mcp_connect first."
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else arguments
    except json.JSONDecodeError:
        return "Error: Invalid JSON arguments"
    return await _MCP_SERVERS[server].call_tool(tool, args)


async def mcp_list(server: str = "") -> str:
    """List connected MCP servers and their tools."""
    if server:
        if server not in _MCP_SERVERS:
            return f"Error: Not connected to '{server}'"
        conn = _MCP_SERVERS[server]
        tools = conn.tool_names
        return f"{server}: {len(tools)} tools\n" + "\n".join(f"  - {t}" for t in tools)

    if not _MCP_SERVERS:
        return "No MCP servers connected."
    lines = []
    for name, conn in _MCP_SERVERS.items():
        lines.append(f"{name}: {len(conn.tool_names)} tools")
    return "\n".join(lines)


async def mcp_disconnect(server: str) -> str:
    """Disconnect from an MCP server."""
    if server not in _MCP_SERVERS:
        return f"Not connected to '{server}'"
    await _MCP_SERVERS[server].close()
    del _MCP_SERVERS[server]
    return f"Disconnected from {server}"


# ── Register tools ──

register_tool(
    name="mcp_connect",
    description="Connect to an MCP server via stdio (command) or SSE (url).",
    parameters={
        "type": "object",
        "properties": {
            "server_name": {"type": "string", "description": "Name for this server connection"},
            "command": {
                "type": "string",
                "description": "Command to start stdio MCP server",
                "default": "",
            },
            "url": {"type": "string", "description": "URL for SSE MCP server", "default": ""},
        },
        "required": ["server_name"],
    },
    handler=mcp_connect,
)

register_tool(
    name="mcp_call",
    description="Call a tool on a connected MCP server.",
    parameters={
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "MCP server name"},
            "tool": {"type": "string", "description": "Tool name to call"},
            "arguments": {
                "type": "string",
                "description": "JSON string of tool arguments",
                "default": "{}",
            },
        },
        "required": ["server", "tool"],
    },
    handler=mcp_call,
)

register_tool(
    name="mcp_list",
    description="List connected MCP servers and their available tools.",
    parameters={
        "type": "object",
        "properties": {
            "server": {
                "type": "string",
                "description": "Specific server to list (optional)",
                "default": "",
            },
        },
    },
    handler=mcp_list,
)

register_tool(
    name="mcp_disconnect",
    description="Disconnect from an MCP server.",
    parameters={
        "type": "object",
        "properties": {
            "server": {"type": "string", "description": "MCP server name to disconnect"},
        },
        "required": ["server"],
    },
    handler=mcp_disconnect,
)
