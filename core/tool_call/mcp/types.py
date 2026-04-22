from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class McpRuntimeServer:
    name: str
    command: str
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    timeout_sec: float = 30.0


@dataclass
class RemoteToolRef:
    local_name: str
    server_name: str
    remote_name: str


@dataclass
class McpLoadSummary:
    added: List[str] = field(default_factory=list)
    cached: List[str] = field(default_factory=list)
    skipped: List[str] = field(default_factory=list)
    failed_servers: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "added": self.added,
            "cached": self.cached,
            "skipped": self.skipped,
            "failed_servers": self.failed_servers,
            "errors": self.errors,
        }
