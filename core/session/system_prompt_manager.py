import os
from dataclasses import dataclass, field
from typing import List, Dict, Any
import json
from typing import List, Tuple, Optional

@dataclass
class SystemPromptPreset:
    name: str = ""
    content: str = ""
    post_history: str = ""
    tools: List[str] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)
    avatars: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Dict[str, Any]):
        info = data.get("info", {}) or {}
        # 兼容多处字段
        tools = info.get("tools", [])
        avatars = info.get("avatar") or data.get("avatar") or {}
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
            post_history=data.get("post_history", ""),
            tools=tools or [],
            info=info,
            avatars={"user": avatars.get("user", ""), "assistant": avatars.get("assistant", "")},
        )

    def to_json(self) -> Dict[str, Any]:
        info = dict(self.info or {})
        info.setdefault("id", "system_prompt")
        # 确保默认中文名
        names = info.get("name") or {}
        info["name"] = {
            "user": names.get("user", ""),
            "assistant": names.get("assistant", "")
        }
        # 工具与头像
        info["tools"] = list(self.tools or [])
        info["avatar"] = {
            "user": (self.avatars or {}).get("user", ""),
            "assistant": (self.avatars or {}).get("assistant", "")
        }
        return {
            "name": self.name,
            "content": self.content,
            "post_history": self.post_history,
            "info": info
        }

class SystemPromptStore:
    def __init__(self, folder_path: str = "data/system_prompt_presets"):
        self.folder_path = folder_path
        os.makedirs(self.folder_path, exist_ok=True)

    def _full_path(self, file_name: str) -> str:
        if not file_name.endswith(".json"):
            file_name += ".json"
        return os.path.join(self.folder_path, file_name)

    def list_files(self) -> List[str]:
        try:
            with os.scandir(self.folder_path) as it:
                return [e.path for e in it if e.is_file() and e.name.endswith(".json")]
        except FileNotFoundError:
            os.makedirs(self.folder_path, exist_ok=True)
            return []

    def list_presets(self) -> List[Tuple[str, SystemPromptPreset]]:
        out = []
        for path in self.list_files():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                preset = SystemPromptPreset.from_json(data)
                out.append((path, preset))
            except Exception:
                # 跳过损坏文件
                continue
        return out

    def read(self, file_path: str) -> Optional[SystemPromptPreset]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return SystemPromptPreset.from_json(json.load(f))
        except Exception:
            return None

    def save(self, file_path: str, preset: SystemPromptPreset) -> bool:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(preset.to_json(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def create(self, file_name: str, preset: SystemPromptPreset) -> Optional[str]:
        path = self._full_path(file_name)
        ok = self.save(path, preset)
        return path if ok else None

    def delete(self, file_path: str) -> bool:
        try:
            os.remove(file_path)
            return True
        except Exception:
            return False

    def current_dialog_path(self, base_name: str = "当前对话") -> str:
        return self._full_path(base_name)

