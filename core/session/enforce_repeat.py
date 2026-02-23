import difflib
from config import APP_SETTINGS
from common import LOGMANAGER

class RepeatProcessor:
    @classmethod
    def analyze_repeats(cls, chathistory: list) -> tuple[bool, str]:
        """
        分析重复内容（支持多模态文本提取）
        :param chathistory: 对话历史
        :return: (is_strong_truncation, detected_repeats_str)
        """
        assistants = []
        for msg in chathistory:
            if msg.get('role') == 'assistant':
                # 使用 cls 调用类方法
                text_content = cls._extract_text_from_msg(msg)
                if text_content: 
                    assistants.append(text_content)

        is_strong_truncation = False
        clean_output_str = ""

        if len(assistants) >= 4:
            last_four = assistants[-4:]

            # 使用 cls 调用
            is_strong_truncation = cls._check_similarity(last_four)
            repeats = cls._find_repeated_substrings(last_four)
            clean_output_list = cls._clean_repeats(repeats)

            if clean_output_list:
                clean_output_str = ", ".join(clean_output_list)

        return is_strong_truncation, clean_output_str

    @classmethod
    def _extract_text_from_msg(cls, msg) -> str:
        """从消息中提取文本内容，兼容纯字符串和多模态列表"""
        content = msg.get('content', '')

        if isinstance(content, str):
            return content

        if isinstance(content, list):
            text_parts = []
            for item in content:
                if isinstance(item, dict) and item.get('type') == 'text':
                    text_val = item.get('text', item.get('content', ''))
                    if text_val:
                        text_parts.append(str(text_val))
            return "\n".join(text_parts)

        return ""

    @classmethod
    def _check_similarity(cls, last_four):
        """检查消息相似度"""
        similarity_threshold = 0.4

        for i in range(len(last_four)):
            for j in range(i+1, len(last_four)):
                ratio = difflib.SequenceMatcher(None, last_four[i], last_four[j]).ratio()
                LOGMANAGER.info(f'[RepeatProcesser]当前相似度 {ratio:.2f}')
                if ratio >= similarity_threshold:
                    LOGMANAGER.warning('[RepeatProcesser]已确认过高相似度')
                    return True
        return False

    @classmethod
    def _find_repeated_substrings(cls, last_four):
        """查找重复子串"""
        repeats = set()
        for i in range(len(last_four)):
            for j in range(i + 1, len(last_four)):
                s_prev = last_four[i]
                s_current = last_four[j]
                cls._add_repeats(s_prev, s_current, repeats)
        return sorted(repeats, key=lambda x: (-len(x), x))

    @classmethod
    def _add_repeats(cls, s1, s2, repeats):
        """添加发现的重复项"""
        len_s1 = len(s1)
        for idx in range(len_s1):
            max_len = len_s1 - idx
            for l in range(max_len, 0, -1):
                substr = s1[idx:idx+l]
                if substr in s2:
                    repeats.add(substr)
                    break

    @classmethod
    def _clean_repeats(cls, repeats):
        """清洗重复项结果"""
        symbol_to_remove = [',','.','"',"'",'，','。','！','？','...','——','：','~']
        clean_output = []
        repeats_check_list = list(reversed(repeats)) 

        for item1 in repeats_check_list:
            if cls._is_unique_substring(item1, repeats_check_list) and len(item1) > 3:
                cleaned = cls._remove_symbols(item1, symbol_to_remove)
                if cleaned:
                    clean_output.append(cleaned)
        return clean_output

    @classmethod
    def _is_unique_substring(cls, item, repeats):
        """检查是否唯一子串"""
        return not any(item in item2 and item != item2 for item2 in repeats)

    @classmethod
    def _remove_symbols(cls, text, symbols):
        """移除指定符号"""
        for symbol in symbols:
            text = text.replace(symbol, '')
        return text