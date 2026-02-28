from __future__ import annotations
import threading
import uuid
import time
import openai
from typing import TYPE_CHECKING,Optional,Callable,Literal



from core.session.chat_history_manager import ChatHistoryTools


if TYPE_CHECKING:
    from config.settings import LciSettings, ApiConfig
    from core.session.session_model import ChatSession, ChatMessage

class _Preparer:
    @staticmethod
    def prepare(
        session: "ChatSession", 
        settings: "LciSettings",
        ):
        
        history = session.shallow_history
        required=set(settings.include)
        
        return _Preparer._filter(history,required)
    
    @staticmethod
    def _filter(
        history:list['ChatMessage'],
        required:set,
        collect_mode:Literal['newest','jumpcut'] = ''
        ):

        items=[]
        
        for item in history:

            if item['role'] in required:
                items.append(item)
                continue

            if item.get('info', {}).keys() & required:
                items.append(item)
            
        return items


class LongChatImprove:
    """
    Long Context Optimization Service Class 
    Role: Responsible for executing long conversation compression and summarization tasks.
    """

    def __init__(self) -> None:
        self._lci_settings: "LciSettings" = None
        self._api_settings: "ApiConfig" = None

        # --- Callbacks (Replacements for Signals) ---
        # Signature: (level: str, message: str) -> None
        # level: "info" | "log" | "warning"
        self.on_log: Optional[Callable[[str, str], None]] = None

        # Signature: (lci_items: list, anchor_id: str) -> None
        self.on_save_history: Optional[Callable[[list, str], None]] = None

        # Signature: () -> None
        self.on_update_bar: Optional[Callable[[], None]] = None

        # Signature: () -> None
        self.on_finished: Optional[Callable[[], None]] = None


    def start(
            self, 
            session: 'ChatSession',
            lci_settings: "LciSettings", 
            api_settings: "ApiConfig"
            ) -> None:
        """
        Start the optimization thread.
        """
        self._lci_settings: "LciSettings" = lci_settings
        self._api_settings: "ApiConfig" = api_settings

        chathistory = _Preparer.prepare(
            session = session,
            settings = self._lci_settings
            )


        if self.on_update_bar:
            self.on_update_bar()

        if not self._validate_config():
            if self.on_finished:
                self.on_finished()
            return

        if self.on_log:
            self.on_log("info", "Long Text Optimization: Thread Started (Smart Parse Mode)")

        # Start thread
        threading.Thread(
            target=self._run_thread,
            args=(chathistory,),
            daemon=True
        ).start()

    def _validate_config(self) -> bool:
        if not self._lci_settings.api_provider:
             if self.on_log:
                 self.on_log("warning", "LCI Config Error: API Provider not specified")
             return False
        if not self._lci_settings.model:
             if self.on_log:
                 self.on_log("warning", "LCI Config Error: Model not specified")
             return False
        return True

    def _get_client(self) -> openai.Client:
        """Get OpenAI Client Instance"""
        provider = self._lci_settings.api_provider
        return openai.Client(
            api_key=self._api_settings.providers[provider].key,
            base_url=self._api_settings.providers[provider].url
        )

    def _create_lci_item(self, content: str, mode: str, related_ids: list[str], is_global: bool = False) -> dict:
        """Construct standard LCI message object"""
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")
        item = {
            "role": "system",
            "content": content,
            "info": {
                "id": f"lci_{uuid.uuid4()}",
                "time": now_str,
                "lci": {
                    "mode": mode,
                    "related": related_ids,
                    # If it's a global summary in mix mode, mark it for receiver handling (e.g., pinning)
                    "is_global": is_global 
                }
            }
        }
        return item

    def _parse_context(self, chathistory: list[dict]) -> dict:
        """
        Core Parsing Logic:
        Scan backwards to find the nearest LCI node, determining which are "new dialogues" and which are "old summaries".
        """
        new_messages = []
        related_ids = []

        last_lci_content = ""
        anchor_id = "" # Anchor: ID of the last message of the new conversation

        # For MIX mode: collect all dispersed summaries in history
        all_dispersed_summaries = [] 

        # 1. Backwards search for nearest anchor and unsummarized fragments
        # Assuming end of chathistory is newest
        found_last_lci = False

        for i in range(len(chathistory) - 1, -1, -1):
            msg = chathistory[i]
            msg_info = msg.get("info", {})
            msg_id = msg_info.get("id", str(uuid.uuid4())) # Fallback

            # Check if it is an LCI node
            if "lci" in msg_info:
                # Record found LCI content
                current_lci_content = msg.get("content", "")

                # If it's the first LCI encountered (first in reverse), this is the immediate context background
                if not found_last_lci:
                    last_lci_content = current_lci_content
                    found_last_lci = True

                # Collect all historical LCI content (for Mix mode)
                all_dispersed_summaries.insert(0, current_lci_content)

            else:
                # If LCI not yet encountered, these are "new conversations"
                if not found_last_lci:
                    # Record anchor (only once, i.e., the last non-LCI message)
                    if not anchor_id:
                        anchor_id = msg_id

                    new_messages.insert(0, msg) # Preserve order
                    related_ids.append(msg_id)

        return {
            "new_messages": new_messages,           # List of message objects to summarize
            "related_ids": related_ids,             # List of message IDs to summarize
            "last_summary": last_lci_content,       # Content of the most recent summary (context)
            "anchor_id": anchor_id,                 # Insertion anchor point
            "all_summaries": all_dispersed_summaries # List of all historical summaries
        }

    def _run_thread(self, chathistory: list[dict]) -> None:
        """Execution Logic"""
        try:
            # 1. Parse context
            ctx = self._parse_context(chathistory)
            new_msgs = ctx["new_messages"]
            anchor_id = ctx["anchor_id"]

            if not new_msgs:
                if self.on_log:
                    self.on_log("warning", "No new conversation content detected for summarization.")
                return

            # Convert new conversation to text
            new_content_str = ChatHistoryTools.to_readable_str(new_msgs)

            mode = self._lci_settings.mode
            client = self._get_client()
            model = self._lci_settings.model
            preset = self._lci_settings.preset

            generated_items = []

            if self.on_log:
                self.on_log("log", f"LCI Started. Mode: {mode} | New content length: {len(new_content_str)}")

            summary_system_prompt = preset.summary_prompt

            # --- Mode: Single (Complete Summary Mode) ---
            # Merge old summary + new chat -> generate brand new complete summary
            if mode == 'single':
                summary_user_template = preset.single_update_prompt

                # Handle Hint Injection
                hint_text = ""
                if self._lci_settings.hint:
                    hint_text = f"{preset.long_chat_hint_prefix}{self._lci_settings.hint}\n"

                # Handle old background
                # If no old summary, provide default text
                context_summary = ctx["last_summary"] if ctx["last_summary"] else "(No previous summary, this is the start of the story)"

                # Format Prompt
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

                # Create Item
                item = self._create_lci_item(result_text, "single", ctx["related_ids"])
                generated_items.append(item)

            # --- Mode: Dispersed (Incremental Summary Mode) ---
            # Based on old background (read-only) + new chat -> generate incremental summary
            elif mode == 'dispersed':
                prompt_template = preset.dispersed_summary_prompt

                all_summaries_list = ctx.get("all_summaries", [])

                if all_summaries_list:
                    context_summary = "\n\n".join(all_summaries_list)
                else:
                    context_summary = "None"

                final_prompt = prompt_template.format(
                    new_content=new_content_str,
                    context_summary=context_summary
                )

                messages = [
                    {"role": "system", "content": summary_system_prompt},
                    {"role": "user", "content": final_prompt}
                ]

                resp = client.chat.completions.create(model=model, messages=messages)
                result_text = resp.choices[0].message.content

                # Create Item
                item = self._create_lci_item(result_text, "dispersed", ctx["related_ids"])
                generated_items.append(item)

            # --- Mode: Mix (Mixed Mode) ---
            elif mode == 'mix':
                # ===========================
                # Step 1: Generate Incremental Summary (Same as Dispersed logic)
                # ===========================

                # 1.1 Prepare background: Join all historical summaries
                all_past_summaries = ctx.get("all_summaries", [])
                if all_past_summaries:
                    context_summary = "\n\n".join(all_past_summaries)
                else:
                    context_summary = "None"

                dispersed_prompt = preset.dispersed_summary_prompt.format(
                    new_content=new_content_str,
                    context_summary=context_summary
                )

                resp1 = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": summary_system_prompt},
                        {"role": "user", "content": dispersed_prompt}
                    ]
                )
                dispersed_text = resp1.choices[0].message.content

                # Create Dispersed Item (Insert into timeline)
                dispersed_item = self._create_lci_item(dispersed_text, "dispersed", ctx["related_ids"])
                generated_items.append(dispersed_item)

                if self.on_log:
                    self.on_log("log", "Mix Mode: Incremental summary done, starting global consolidation...")

                # ===========================
                # Step 2: Consolidate all summary fragments -> Generate Global Summary
                # ===========================

                # 2.1 Collect all: Historical + Newest
                full_chain_summaries = all_past_summaries + [dispersed_text]

                # 2.2 Join
                dispersed_contents_str = "\n\n".join(full_chain_summaries)

                mix_prompt = preset.mix_consolidation_prompt.format(
                    dispersed_contents=dispersed_contents_str
                )

                resp2 = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": summary_system_prompt},
                        {"role": "user", "content": mix_prompt}
                    ]
                )
                grand_text = resp2.choices[0].message.content

                # Create Grand Item (For global pinning)
                grand_item = self._create_lci_item(grand_text, "mix", [], is_global=True)
                generated_items.append(grand_item)

            # --- Execution Complete ---
            if self.on_log:
                self.on_log("log", f"LCI Execution Complete. Generated {len(generated_items)} summaries.")

            # Send results
            if anchor_id and generated_items:
                if self.on_save_history:
                    self.on_save_history(generated_items, anchor_id)
            else:
                if self.on_log:
                    self.on_log("warning", "LCI finished, but no anchor found or content generated.")

        except Exception as e:
            if self.on_log:
                self.on_log("warning", f"Error in long chat optimization: {str(e)}")
            import traceback
            traceback.print_exc()

        finally:
            if self.on_finished:
                self.on_finished()
