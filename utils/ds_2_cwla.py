from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from config import APP_RUNTIME
from core.session.session_model import ChatSession


def _extract_chain_longest(mapping: Dict) -> List[str]:
    """从 root 到叶子节点，提取最长分支；无 root 时做降级处理。"""
    if 'root' not in mapping:
        return [
            nid for nid in sorted(
                mapping.keys(),
                key=lambda x: (not str(x).isdigit(), str(x))
            ) if nid != 'root'
        ]

    best: List[str] = []
    stack: List[Tuple[str, List[str]]] = [('root', [])]
    guard = 0

    while stack:
        node_id, path = stack.pop()
        guard += 1
        if guard > 200000:
            break

        node = mapping.get(node_id) or {}
        children = node.get('children') or []

        if not children:
            if len(path) > len(best):
                best = path
            continue

        for child in children:
            if child in path:
                continue
            stack.append((child, path + [child]))

    if best:
        return best

    # 降级：沿第一子节点向下
    chain: List[str] = []
    node_id = 'root'
    visited = {'root'}
    while True:
        node = mapping.get(node_id) or {}
        children = node.get('children') or []
        if not children:
            break
        nxt = children[0]
        if nxt in visited:
            break
        visited.add(nxt)
        chain.append(nxt)
        node_id = nxt
    return chain


def convert_one_conversation(conv: Dict) -> ChatSession:
    """将单条 deepseek conversation 转为 ChatSession。"""
    mapping = conv.get('mapping', {}) or {}

    history = [{
        'role': 'system',
        'content': '',
        'info': {'id': 'system_prompt'}
    }]

    chain = _extract_chain_longest(mapping)

    for node_id in chain:
        node = mapping.get(node_id, {})
        message = node.get('message')
        if not isinstance(message, dict):
            continue

        fragments = message.get('fragments') or []
        inserted_at = message.get('inserted_at')
        model = message.get('model')

        think_parts: List[str] = []
        response_parts: List[str] = []

        for i, frag in enumerate(fragments):
            if not isinstance(frag, dict):
                continue

            frag_type = frag.get('type')
            content = frag.get('content')

            if frag_type == 'REQUEST' and content is not None:
                history.append({
                    'role': 'user',
                    'content': str(content),
                    'info': {
                        'id': f'{node_id}_{i}',
                        'time': inserted_at,
                        'model': model,
                    },
                })
            elif frag_type == 'THINK' and content is not None:
                think_parts.append(str(content))
            elif frag_type == 'RESPONSE' and content is not None:
                response_parts.append(str(content))

        if response_parts or think_parts:
            history.append({
                'role': 'assistant',
                'content': '\n'.join(response_parts) if response_parts else '',
                'reasoning_content': '\n'.join(think_parts) if think_parts else None,
                'tool_calls': None,
                'info': {
                    'id': f'{node_id}_assistant',
                    'time': inserted_at,
                    'model': model,
                },
            })

    return ChatSession.from_dict({
        'history': history,
        'chat_id': conv.get('id', ''),
        'new_chat_rounds': 0,
        'new_background_rounds': 0,
        'title': conv.get('title') or '',
        'name': {'user': '', 'assistant': ''},
        'avatars': {'user': '', 'assistant': ''},
        'tools': [],
        '_version': 'V2',
    })


def convert_file(
    source_path: str | Path,
    output_dir: str | Path | None = None,
) -> Dict[str, int | str]:
    """
    批量转换 conversations.json 到 CWLA 会话文件。

    参数:
        source_path: 原始 conversations.json 路径
        output_dir: 导出目录，默认 APP_RUNTIME.paths.history_path

    返回:
        执行统计信息
    """
    src = Path(source_path)
    if output_dir is None:
        output_dir = APP_RUNTIME.paths.history_path

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    with src.open('r', encoding='utf-8') as f:
        conversations = json.load(f)

    success = 0
    failed = 0

    for i, conv in enumerate(conversations, 1):
        try:
            session = convert_one_conversation(conv)
            chat_id = session.chat_id or f'noid_{i}'
            (out / f'{chat_id}.json').write_text(session.to_json(), encoding='utf-8')
            success += 1
        except Exception:
            failed += 1

    return {
        'source': str(src),
        'output_dir': str(out),
        'total': len(conversations),
        'success': success,
        'failed': failed,
    }


if __name__ == '__main__':
    # 默认输入路径，可按需修改
    default_source = Path.home() / 'Downloads' / 'conversations.json'
    result = convert_file(default_source)
    print(json.dumps(result, ensure_ascii=False, indent=2))
