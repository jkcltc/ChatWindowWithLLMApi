from __future__ import annotations

from typing import Any, Dict, Tuple


def normalize_tool_schema(raw_parameters: Dict[str, Any] | None) -> Dict[str, Any]:
    if isinstance(raw_parameters, dict) and raw_parameters:
        return raw_parameters
    return {"type": "object", "properties": {}}


def to_local_tool_name(server_name: str, remote_tool_name: str, policy: str) -> str:
    if policy == "prefix":
        return f"{server_name}__{remote_tool_name}"
    return remote_tool_name


def parse_remote_tool(raw: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    name = str(raw.get("name") or "").strip()
    if not name:
        raise ValueError("Remote tool missing name")
    desc = str(raw.get("description") or "").strip()
    params = normalize_tool_schema(raw.get("inputSchema") or raw.get("parameters"))
    return name, desc, params
