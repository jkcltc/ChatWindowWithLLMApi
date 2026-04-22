from __future__ import annotations

import asyncio
import json
import os
import threading
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Tuple


class McpClient:
    """Persistent MCP client backed by official Python MCP SDK."""

    def __init__(
        self,
        *,
        name: str,
        transport: str,
        command: str,
        args: List[str] | None = None,
        env: Dict[str, str] | None = None,
        cwd: str = "",
        timeout_sec: float = 30.0,
        url: str = "",
    ):
        self.name = name
        self.transport = transport
        self.command = command
        self.args = list(args or [])
        self.env = dict(env or {})
        self.cwd = cwd
        self.timeout_sec = float(timeout_sec or 30.0)
        self.url = url.strip()

        self._connected = False
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._stack: AsyncExitStack | None = None
        self._session: Any = None
        self._lock = threading.Lock()

    def connect(self):
        if self.transport not in {"stdio", "streamable_http", "sse"}:
            raise NotImplementedError(f"Unsupported transport: {self.transport}")

        with self._lock:
            self._ensure_loop()
            self._run(self._async_connect())
            self._connected = True

    def close(self):
        with self._lock:
            if self._loop and self._loop.is_running():
                try:
                    self._run(self._async_close(), timeout=10.0)
                except Exception:
                    pass
                try:
                    self._loop.call_soon_threadsafe(self._loop.stop)
                except Exception:
                    pass

            if self._thread:
                try:
                    self._thread.join(timeout=2.0)
                except Exception:
                    pass

            self._loop = None
            self._thread = None
            self._stack = None
            self._session = None
            self._connected = False

    def list_tools(self) -> List[Dict[str, Any]]:
        if not self._connected:
            raise RuntimeError(f"MCP server '{self.name}' not connected")
        return self._run(self._async_list_tools())

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if not self._connected:
            raise RuntimeError(f"MCP server '{self.name}' not connected")
        return self._run(self._async_call_tool(tool_name, arguments or {}))

    def _ensure_loop(self):
        if self._loop and self._loop.is_running():
            return

        loop = asyncio.new_event_loop()

        def _runner():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(
            target=_runner, name=f"mcp-client-{self.name}", daemon=True
        )
        t.start()
        self._loop = loop
        self._thread = t

    def _run(self, coro, timeout: float | None = None):
        if not self._loop:
            raise RuntimeError("MCP loop not initialized")
        fut = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return fut.result(timeout=timeout or self.timeout_sec)

    async def _async_connect(self):
        if self._session is not None:
            return

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamablehttp_client
            from mcp.client.sse import sse_client
        except Exception as e:
            raise RuntimeError(
                "MCP SDK import failed. Please install dependency 'mcp'."
            ) from e

        stack = AsyncExitStack()
        if self.transport == "stdio":
            env = os.environ.copy()
            env.update({k: str(v) for k, v in self.env.items()})

            server_params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=env,
                cwd=(self.cwd or None),
            )
            rw: Tuple[Any, Any] = await stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = rw
        elif self.transport == "streamable_http":
            target_url = self.url or self.command
            if not target_url:
                raise ValueError("streamable_http transport requires url")
            rwg = await stack.enter_async_context(
                streamablehttp_client(target_url, timeout=self.timeout_sec)
            )
            read, write, _get_session_id = rwg
        else:
            target_url = self.url or self.command
            if not target_url:
                raise ValueError("sse transport requires url")
            rw = await stack.enter_async_context(
                sse_client(target_url, timeout=self.timeout_sec)
            )
            read, write = rw

        session = await stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        self._stack = stack
        self._session = session

    async def _async_close(self):
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def _async_list_tools(self) -> List[Dict[str, Any]]:
        if self._session is None:
            await self._async_connect()

        result = await self._session.list_tools()
        tools = getattr(result, "tools", result) or []

        output: List[Dict[str, Any]] = []
        for item in tools:
            if isinstance(item, dict):
                name = str(item.get("name") or "").strip()
                desc = str(item.get("description") or "")
                schema = (
                    item.get("inputSchema")
                    or item.get("input_schema")
                    or item.get("parameters")
                    or {"type": "object", "properties": {}}
                )
            else:
                name = str(getattr(item, "name", "") or "").strip()
                desc = str(getattr(item, "description", "") or "")
                schema = (
                    getattr(item, "inputSchema", None)
                    or getattr(item, "input_schema", None)
                    or getattr(item, "parameters", None)
                    or {"type": "object", "properties": {}}
                )

            if not name:
                continue
            output.append(
                {
                    "name": name,
                    "description": desc,
                    "inputSchema": self._to_plain(schema),
                }
            )

        return output

    async def _async_call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        if self._session is None:
            await self._async_connect()

        try:
            result = await self._session.call_tool(name=tool_name, arguments=arguments)
        except TypeError:
            # 兼容部分 SDK 版本的参数形式
            result = await self._session.call_tool(tool_name, arguments)

        plain = self._to_plain(result)

        # 优先将纯文本 content 汇总成可读结果
        if isinstance(plain, dict) and isinstance(plain.get("content"), list):
            texts: List[str] = []
            for c in plain["content"]:
                if isinstance(c, dict):
                    t = c.get("text")
                    if isinstance(t, str):
                        texts.append(t)
            if texts:
                joined = "\n".join(texts).strip()
                if joined:
                    try:
                        return json.loads(joined)
                    except Exception:
                        return joined
        return plain

    def _to_plain(self, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return [self._to_plain(v) for v in value]
        if isinstance(value, tuple):
            return [self._to_plain(v) for v in value]
        if isinstance(value, dict):
            return {str(k): self._to_plain(v) for k, v in value.items()}
        if hasattr(value, "model_dump"):
            try:
                return self._to_plain(value.model_dump())
            except Exception:
                pass
        if hasattr(value, "dict"):
            try:
                return self._to_plain(value.dict())
            except Exception:
                pass
        if hasattr(value, "__dict__"):
            try:
                return self._to_plain(
                    {k: v for k, v in vars(value).items() if not k.startswith("_")}
                )
            except Exception:
                pass
        return str(value)
