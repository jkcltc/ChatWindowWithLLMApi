# utils\lci.py

from __future__ import annotations
import threading
import uuid
import datetime
import openai
from typing import TYPE_CHECKING
from PyQt6.QtCore import QObject, pyqtSignal

from utils.chat_history_manager import ChatHistoryTools

if TYPE_CHECKING:
    from utils.setting.data import LciSettings, ApiConfig

class LongChatImprove(QObject):
    """
    长文本优化业务服务类 (Refactored)
    Role: 负责执行长对话压缩、总结任务。
    """

    # level: "info" | "log" | "warning", message: 内容
    sig_log = pyqtSignal(str, str)

    # 修改：回传 (生成的LCI消息列表, 锚点消息ID)
    # 接收端需要根据 anchor_id 将 new_lci_items 插入到对应位置
    sig_save_history = pyqtSignal(list, str)

    sig_update_bar = pyqtSignal()
    sig_finished = pyqtSignal()

    def __init__(self, lci_settings: "LciSettings", api_settings: "ApiConfig") -> None:
        super().__init__()
        self._new_chat_rounds: int = 0
        self._lci_settings: "LciSettings" = lci_settings
        self._api_settings: "ApiConfig" = api_settings

    def increment_rounds(self) -> None:
        self._new_chat_rounds += 1

    def start_optimize(self, chathistory: list[dict]) -> None:
        """
        启动优化线程
        注意：不再需要传入 current_sysrule，所有信息应包含在 chathistory 中
        """
        self._new_chat_rounds = 0
        self.sig_update_bar.emit()

        if not self._validate_config():
            self.sig_finished.emit()
            return

        self.sig_log.emit("info", "长文本优化：线程启动 (智能解析模式)")

        # 启动线程
        threading.Thread(
            target=self._run_thread,
            args=(chathistory,),
            daemon=True
        ).start()

    def _validate_config(self) -> bool:
        if not self._lci_settings.api_provider:
             self.sig_log.emit("warning", "LCI配置错误：未指定 API Provider")
             return False
        if not self._lci_settings.model:
             self.sig_log.emit("warning", "LCI配置错误：未指定 Model")
             return False
        return True

    def _get_client(self) -> openai.Client:
        """获取 OpenAI 客户端实例"""
        provider = self._lci_settings.api_provider
        return openai.Client(
            api_key=self._api_settings.providers[provider].key,
            base_url=self._api_settings.providers[provider].url
        )

    def _create_lci_item(self, content: str, mode: str, related_ids: list[str], is_global: bool = False) -> dict:
        """构造标准的 LCI 消息对象"""
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        item = {
            "role": "system",
            "content": content,
            "info": {
                "id": f"lci_{uuid.uuid4().hex[:8]}",
                "time": now_str,
                "lci": {
                    "mode": mode,
                    "related": related_ids,
                    # 如果是混合模式下的全局总结，标记一下，方便接收端处理（例如置顶）
                    "is_global": is_global 
                }
            }
        }
        return item

    def _parse_context(self, chathistory: list[dict]) -> dict:
        """
        核心解析逻辑：
        倒序扫描，找到最近的一个 LCI 节点，确定哪些是"新对话"，哪些是"旧总结"。
        """
        new_messages = []
        related_ids = []

        last_lci_content = ""
        anchor_id = "" # 锚点：新对话的最后一条消息ID

        # 用于 MIX 模式：收集历史上所有的分散总结
        all_dispersed_summaries = [] 

        # 1. 倒序寻找最近的锚点和未总结片段
        # 我们假设 chathistory 的末尾是最新的
        found_last_lci = False

        for i in range(len(chathistory) - 1, -1, -1):
            msg = chathistory[i]
            msg_info = msg.get("info", {})
            msg_id = msg_info.get("id", str(uuid.uuid4())) # 容错

            # 检查是否是 LCI 节点
            if "lci" in msg_info:
                # 记录找到的 LCI 内容
                current_lci_content = msg.get("content", "")

                # 如果是第一次遇到 LCI（倒序的第一个），这就是最近的上下文背景
                if not found_last_lci:
                    last_lci_content = current_lci_content
                    found_last_lci = True

                # 收集所有历史 LCI 内容 (针对 Mix 模式)
                # 注意：这里我们只收集 dispersed 类型的，或者全部收集由 Prompt 决定
                # 简单起见，收集所有 LCI 节点的内容
                all_dispersed_summaries.insert(0, current_lci_content)

            else:
                # 如果还没遇到 LCI，说明这些是“新发生的对话”
                if not found_last_lci:
                    # 记录锚点（只记录一次，即最后一条非LCI消息）
                    if not anchor_id:
                        anchor_id = msg_id

                    new_messages.insert(0, msg) # 保持顺序
                    related_ids.append(msg_id)

        return {
            "new_messages": new_messages,           # 待总结的消息对象列表
            "related_ids": related_ids,             # 待总结的消息ID列表
            "last_summary": last_lci_content,       # 最近一次总结的内容（上下文）
            "anchor_id": anchor_id,                 # 插入位置锚点
            "all_summaries": all_dispersed_summaries # 所有历史总结列表
        }

    def _run_thread(self, chathistory: list[dict]) -> None:
        """执行逻辑"""
        try:
            # 1. 解析上下文
            ctx = self._parse_context(chathistory)
            new_msgs = ctx["new_messages"]
            anchor_id = ctx["anchor_id"]

            if not new_msgs:
                self.sig_log.emit("warning", "没有检测到需要总结的新对话内容。")
                return

            # 将新对话转为文本
            new_content_str = ChatHistoryTools.to_readable_str(new_msgs)

            mode = self._lci_settings.mode
            client = self._get_client()
            model = self._lci_settings.model
            preset = self._lci_settings.preset

            generated_items = []

            self.sig_log.emit("log", f"LCI 开始执行。模式: {mode} | 新增内容长度: {len(new_content_str)}")

            # --- Mode: Single (完整总结模式) ---
            # 合并旧总结 + 新对话 -> 生成全新完整总结
            if mode == 'single':
                summary_system_prompt = preset.summary_prompt
                summary_user_template = preset.single_update_prompt

                # 处理 Hint 注入
                hint_text = ""
                if self._lci_settings.hint:
                    # 如果有提示词，按照预设前缀组合
                    hint_text = f"{preset.long_chat_hint_prefix}{self._lci_settings.hint}\n"

                # 处理旧背景
                # 如果没有旧总结，提供一个默认文本，避免看起来像数据缺失
                context_summary = ctx["last_summary"] if ctx["last_summary"] else "（无先前总结，这是故事的开始）"

                # 格式化 Prompt
                full_user_content = summary_user_template.format(
                    hint_text=hint_text,
                    context_summary=context_summary,
                    new_content=new_content_str
                )

                messages = [
                    {"role": "system", "content": summary_system_prompt},
                    {"role": "user", "content": full_user_content}
                ]

                resp = client.chat.completions.create(model=model, messages=messages)
                result_text = resp.choices[0].message.content

                # 创建 Item
                item = self._create_lci_item(result_text, "single", ctx["related_ids"])
                generated_items.append(item)

            # --- Mode: Dispersed (增量摘要模式) ---
            # 基于旧背景(只读) + 新对话 -> 生成增量摘要
            elif mode == 'dispersed':
                prompt_template = preset.dispersed_summary_prompt

                # 格式化 Prompt
                # 如果没有旧背景，填"无"
                context_summary = ctx["last_summary"] if ctx["last_summary"] else "无已知背景，这是故事的开始。"

                final_prompt = prompt_template.format(
                    new_content=new_content_str,
                    context_summary=context_summary
                )

                messages = [
                    {"role": "user", "content": final_prompt}
                ]

                resp = client.chat.completions.create(model=model, messages=messages)
                result_text = resp.choices[0].message.content

                # 创建 Item
                item = self._create_lci_item(result_text, "dispersed", ctx["related_ids"])
                generated_items.append(item)

            # --- Mode: Mix (混合模式) ---
            # 步骤1: 生成增量摘要
            elif mode == 'mix':
                context_summary = ctx["last_summary"] if ctx["last_summary"] else "无"
                dispersed_prompt = preset.dispersed_summary_prompt.format(
                    new_content=new_content_str,
                    context_summary=context_summary
                )

                resp1 = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": dispersed_prompt}]
                )
                dispersed_text = resp1.choices[0].message.content

                # 创建 Dispersed Item (这是要插入到对话流中的)
                dispersed_item = self._create_lci_item(dispersed_text, "dispersed", ctx["related_ids"])
                generated_items.append(dispersed_item)

                self.sig_log.emit("log", "Mix模式：增量总结完成，开始执行全局整合...")

                # 步骤2: 整合所有摘要片段 -> 生成全局总结
                all_summaries = ctx["all_summaries"]
                all_summaries.append(dispersed_text) # 把最新的加进去

                # 拼接所有碎片文本
                dispersed_contents_str = ""
                for idx, summary in enumerate(all_summaries):
                    dispersed_contents_str += f"\n[摘要片段 {idx+1}]:\n{summary}\n"

                mix_prompt = preset.mix_consolidation_prompt.format(
                    dispersed_contents=dispersed_contents_str
                )

                resp2 = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": mix_prompt}]
                )
                grand_text = resp2.choices[0].message.content

                # 创建 Grand Item (这是可能需要置顶或替换头部的)
                # 注意：related_ids 理论上是所有相关的，这里暂时只填新的，或者留空
                grand_item = self._create_lci_item(grand_text, "single", [], is_global=True)
                generated_items.append(grand_item)

            # --- 执行完成 ---
            self.sig_log.emit("log", f"LCI 执行完成。生成了 {len(generated_items)} 条总结。")

            # 发送结果
            if anchor_id and generated_items:
                self.sig_save_history.emit(generated_items, anchor_id)
            else:
                self.sig_log.emit("warning", "LCI 完成，但未找到锚点或未生成内容。")

        except Exception as e:
            self.sig_log.emit("warning", f"长对话优化发生错误: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            self.sig_finished.emit()