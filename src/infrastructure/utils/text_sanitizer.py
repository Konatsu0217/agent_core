"""
text_sanitizer.py

TTS 文本预处理工具：过滤颜文字中的希腊字母、日文假名、特殊装饰符号等，
确保只有可朗读的中文/英文/数字/标点被送入 TTS 引擎。
"""

import re

# 日文半角片假名（在全角区 U+FF65 ~ U+FF9F）
_HALFWIDTH_KANA_RE = re.compile('[\uff65-\uff9f]')

# 全角反引号 ｀ (U+FF40) 和全角波浪号 ～ (U+FF5E) 等不需要朗读的全角符号
_UNWANTED_FULLWIDTH_RE = re.compile('[\uff40\uff5e]')

# 空括号对（半角和全角，内部可能含空格或残留的纯标点）
_EMPTY_PARENS_RE = re.compile(r"[\(\uff08][^a-zA-Z\u4e00-\u9fff0-9]*[\)\uff09]")

# 多余空格
_MULTI_SPACE_RE = re.compile(r' {2,}')


def sanitize_text_for_tts(text: str) -> str:
    """
    过滤掉不适合 TTS 朗读的字符。

    保留：中文、英文、数字、常用中英文标点、空白
    过滤：希腊字母(αβγωσπ等)、日文假名、颜文字装饰符、数学符号等
    """
    if not text:
        return text

    # Step 1: 只保留白名单字符（否定字符集 → 非白名单字符替换为空）
    cleaned = re.sub(
        '[^'
        '\u4e00-\u9fff'       # CJK 汉字
        '\u3000-\u303f'       # CJK 标点
        '\uff01-\uff5e'       # 全角 ASCII
        'a-zA-Z0-9'           # 半角英文数字
        r'\s'                 # 空白
        r'.,!?;:\'\"\-\(\)/'  # 常用半角标点
        ']',
        '',
        text
    )

    # Step 2: 去除全角区的日文半角片假名
    cleaned = _HALFWIDTH_KANA_RE.sub('', cleaned)

    # Step 3: 去除不需要朗读的全角符号（反引号、波浪号等）
    cleaned = _UNWANTED_FULLWIDTH_RE.sub('', cleaned)

    # Step 4: 清理括号内无实际文字内容的括号对
    cleaned = _EMPTY_PARENS_RE.sub('', cleaned)

    # Step 5: 合并多余空格
    cleaned = _MULTI_SPACE_RE.sub(' ', cleaned).strip()

    return cleaned
