from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging
import json
import os

from config import APP_SETTINGS, APP_RUNTIME
from core.tool_call.tool_core import Tool, ToolRegistry

from .adapter import parse_remote_tool, to_local_tool_name
from .client import McpClient
from .types import McpLoadSummary, RemoteToolRef

logger = logging.getLogger("tools")


class McpManager:
    """Manage MCP servers and register MCP tools to ToolRegistry."""

    def __init__(self, registry: ToolRegistry):
        self._registry = registry
        self._clients: Dict[str, McpClient] = {}
        self._tool_refs: Dict[str, RemoteToolRef] = {}
        self._loaded = False

    def initial_load(self, force_refresh: bool = False) -> Dict[str, Any]:
        summary = McpLoadSummary()
        if self._loaded:
            return summary.to_dict()

        cfg = APP_SETTINGS.mcp
        if not cfg.enabled:
            return summary.to_dict()

        if (not force_refresh) and (
            not bool(getattr(cfg, "refresh_tools_on_startup", False))
        ):
            cache_data = self._load_cache_data()
            for server in cfg.servers:
                if not server.enabled:
                    continue
                self._restore_from_cache(
                    server.name, cache_data.get(server.name, []), summary
                )
            self._loaded = True
            return summary.to_dict()

        cache_data = self._load_cache_data()
        cache_modified = False

        for server in cfg.servers:
            if not server.enabled:
                continue
            if not server.name:
                summary.failed_servers.append(server.name or "<empty-name>")
                summary.errors.append(f"invalid server config: {server.model_dump()}")
                continue

            if server.transport == "stdio" and not server.command:
                summary.failed_servers.append(server.name)
                summary.errors.append(
                    f"invalid stdio server config '{server.name}': command is required"
                )
                continue
            if server.transport in ("streamable_http", "sse") and not (
                getattr(server, "url", "") or server.command
            ):
                summary.failed_servers.append(server.name)
                summary.errors.append(
                    f"invalid remote server config '{server.name}': url is required"
                )
                continue

            try:
                client = McpClient(
                    name=server.name,
                    transport=server.transport,
                    command=server.command,
                    url=getattr(server, "url", ""),
                    args=server.args,
                    env=server.env,
                    cwd=server.cwd,
                    timeout_sec=server.timeout_sec,
                )
                client.connect()
                self._clients[server.name] = client
            except Exception as e:
                summary.failed_servers.append(server.name)
                summary.errors.append(f"connect '{server.name}' failed: {e}")
                continue

            try:
                tools = client.list_tools()
                for raw_tool in tools:
                    self._register_remote_tool(server.name, raw_tool, summary)
                cache_data[server.name] = [t for t in tools if isinstance(t, dict)]
                cache_modified = True
            except Exception as e:
                summary.failed_servers.append(server.name)
                summary.errors.append(f"list_tools '{server.name}' failed: {e}")
                try:
                    client.close()
                except Exception:
                    pass
                self._clients.pop(server.name, None)
                cache_tools = cache_data.get(server.name, [])
                self._restore_from_cache(server.name, cache_tools, summary)

        if cache_modified:
            self._save_cache_data(cache_data)
        self._loaded = True
        return summary.to_dict()

    def reload_all(self, force_refresh: bool = True) -> Dict[str, Any]:
        self.shutdown_all()
        return self.initial_load(force_refresh=force_refresh)

    def shutdown_all(self):
        self._remove_all_registered_tools()
        for _, client in list(self._clients.items()):
            try:
                client.close()
            except Exception:
                pass
        self._clients.clear()
        self._loaded = False

    def call(
        self, server_name: str, remote_tool_name: str, arguments: Dict[str, Any]
    ) -> Any:
        client = self._clients.get(server_name)
        if not client:
            client = self._connect_single_server(server_name)
        if not client:
            raise ValueError(f"MCP server '{server_name}' not available")
        return client.call_tool(remote_tool_name, arguments)

    def resolve_remote_ref(self, local_tool_name: str) -> Optional[RemoteToolRef]:
        return self._tool_refs.get(local_tool_name)

    def _register_remote_tool(
        self, server_name: str, raw_tool: Dict[str, Any], summary: McpLoadSummary
    ):
        policy = APP_SETTINGS.mcp.name_conflict_policy
        remote_name, desc, parameters = parse_remote_tool(raw_tool)
        local_name = to_local_tool_name(server_name, remote_name, policy)

        if self._registry.get(local_name):
            if policy == "prefix":
                summary.skipped.append(local_name)
                return
            if policy == "skip":
                summary.skipped.append(local_name)
                return
            if policy == "error":
                summary.errors.append(f"tool name conflict: {local_name}")
                return

        def _handler_factory(s_name: str, r_name: str):
            def _handler(**kwargs):
                return self.call(s_name, r_name, kwargs)

            return _handler

        tool = Tool(
            name=local_name,
            description=desc or f"MCP tool from {server_name}: {remote_name}",
            parameters=parameters,
            handler=_handler_factory(server_name, remote_name),
            tags=["mcp", f"mcp:{server_name}"],
            timeout=self._get_server_timeout(server_name),
            permissions=[],
            is_async=False,
        )
        self._registry.register(tool)
        self._tool_refs[local_name] = RemoteToolRef(
            local_name=local_name,
            server_name=server_name,
            remote_name=remote_name,
        )
        summary.added.append(local_name)
        logger.info(
            "MCP tool registered: %s <- %s/%s", local_name, server_name, remote_name
        )

    def _remove_all_registered_tools(self):
        for local_name in list(self._tool_refs.keys()):
            self._registry.remove(local_name)
            self._tool_refs.pop(local_name, None)

    def _cache_file_path(self) -> str:
        cfg_dir = APP_RUNTIME.paths.config_path
        return os.path.join(cfg_dir, "mcp_tools_cache.json")

    def _load_cache_data(self) -> Dict[str, List[Dict[str, Any]]]:
        fp = self._cache_file_path()
        if not os.path.exists(fp):
            return {}
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            out: Dict[str, List[Dict[str, Any]]] = {}
            for k, v in data.items():
                if isinstance(k, str) and isinstance(v, list):
                    out[k] = [item for item in v if isinstance(item, dict)]
            return out
        except Exception:
            return {}

    def _save_cache_data(self, cache_data: Dict[str, List[Dict[str, Any]]]):
        fp = self._cache_file_path()
        try:
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning("MCP cache save failed: %s", e)

    def _restore_from_cache(
        self,
        server_name: str,
        cache_tools: List[Dict[str, Any]],
        summary: McpLoadSummary,
    ):
        for raw_tool in cache_tools or []:
            before = len(summary.added)
            self._register_remote_tool(server_name, raw_tool, summary)
            if len(summary.added) > before:
                summary.cached.append(summary.added[-1])

    def _get_server_timeout(self, server_name: str) -> float:
        for s in APP_SETTINGS.mcp.servers:
            if s.name == server_name:
                try:
                    return float(s.timeout_sec)
                except Exception:
                    return 30.0
        return 30.0

    def _connect_single_server(self, server_name: str) -> Optional[McpClient]:
        for server in APP_SETTINGS.mcp.servers:
            if server.name != server_name or not server.enabled:
                continue
            try:
                client = McpClient(
                    name=server.name,
                    transport=server.transport,
                    command=server.command,
                    url=getattr(server, "url", ""),
                    args=server.args,
                    env=server.env,
                    cwd=server.cwd,
                    timeout_sec=server.timeout_sec,
                )
                client.connect()
                self._clients[server.name] = client
                return client
            except Exception as e:
                logger.warning("MCP lazy connect failed for %s: %s", server_name, e)
                return None
        return None
