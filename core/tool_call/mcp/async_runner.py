from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Dict, List

from core.tool_call.tool_core import get_mcp_manager

from .client import McpClient


class McpAsyncRunner:
    """Qt-free background runner for MCP operations."""

    def __init__(self, max_workers: int = 4):
        self._max_workers = max_workers
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="mcp-bg"
        )
        self._shutdown = False

    def shutdown(self, wait: bool = False):
        self._shutdown = True
        self._executor.shutdown(wait=wait)

    def _ensure_executor(self):
        if self._shutdown:
            self._executor = ThreadPoolExecutor(
                max_workers=self._max_workers, thread_name_prefix="mcp-bg"
            )
            self._shutdown = False

    def submit_test_server(self, srv: Dict[str, Any]) -> Future:
        self._ensure_executor()
        return self._executor.submit(self._test_server_blocking, dict(srv))

    def submit_preview_servers(
        self, servers: List[Dict[str, Any]], enabled_only: bool = True
    ) -> Future:
        self._ensure_executor()
        payload = [dict(s) for s in servers]
        return self._executor.submit(
            self._preview_servers_blocking, payload, enabled_only
        )

    def submit_apply_reload(self, enabled: bool, force_refresh: bool = True) -> Future:
        self._ensure_executor()
        return self._executor.submit(
            self._apply_reload_blocking, bool(enabled), bool(force_refresh)
        )

    @staticmethod
    def _test_server_blocking(srv: Dict[str, Any]) -> Dict[str, Any]:
        client = McpClient(
            name=str(srv.get("name", "")),
            transport=str(srv.get("transport", "stdio") or "stdio"),
            url=str(srv.get("url", "") or ""),
            command=str(srv.get("command", "")),
            args=list(srv.get("args", []) or []),
            env=dict(srv.get("env", {}) or {}),
            cwd=str(srv.get("cwd", "")),
            timeout_sec=float(srv.get("timeout_sec", 30.0)),
        )
        try:
            client.connect()
            tools = client.list_tools()
            return {
                "ok": True,
                "message": f"连接成功，发现 {len(tools)} 个工具",
                "tools": tools,
                "server": srv.get("name", ""),
            }
        except Exception as e:
            return {
                "ok": False,
                "message": str(e),
                "tools": [],
                "server": srv.get("name", ""),
            }
        finally:
            try:
                client.close()
            except Exception:
                pass

    @classmethod
    def _preview_servers_blocking(
        cls, servers: List[Dict[str, Any]], enabled_only: bool = True
    ) -> Dict[str, Any]:
        rows: List[Dict[str, Any]] = []
        errors: List[str] = []
        for srv in servers:
            if enabled_only and not bool(srv.get("enabled", True)):
                continue

            result = cls._test_server_blocking(srv)
            if not result.get("ok"):
                errors.append(
                    f"{srv.get('name', '<unnamed>')}: {result.get('message', 'unknown error')}"
                )
                continue

            for t in result.get("tools", []) or []:
                rows.append(
                    {
                        "server": srv.get("name", ""),
                        "name": t.get("name", ""),
                        "description": t.get("description", ""),
                        "schema": t.get("inputSchema") or t.get("parameters") or {},
                    }
                )

        return {"rows": rows, "errors": errors}

    @staticmethod
    def _apply_reload_blocking(
        enabled: bool, force_refresh: bool = True
    ) -> Dict[str, Any]:
        if enabled:
            return get_mcp_manager().reload_all(force_refresh=force_refresh)
        get_mcp_manager().shutdown_all()
        return {"added": [], "cached": [], "failed_servers": [], "errors": []}
