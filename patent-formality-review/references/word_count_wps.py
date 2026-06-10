"""
WPS/Word-style word count for Chinese patent text.

Problem: Python len() counts every Unicode char (English letters, punctuation,
whitespace all = 1). WPS/Word "字数" counts:
  - Each CJK character = 1
  - Each English/digit word = 1
  - Punctuation and whitespace = 0

This matters for Rule 3.15: 发明名称一般不得超过25个字.

Usage:
    from word_count_wps import word_count_wps
    count = word_count_wps("一种基于多维版本约束的推荐队列数据处理方法、装置及介质")
    # => 26
"""

import re


def word_count_wps(text: str) -> int:
    """
    Simulate WPS/Word '字数' statistic.

    Rules:
    - CJK Unified Ideographs (U+4E00-U+9FFF): each char = 1
    - English letters / digits: consecutive runs = 1 word each
    - All punctuation (both CJK and ASCII), whitespace: ignored
    """
    # CJK characters only — NOT including CJK punctuation blocks
    # (\u3000-\u303f and \uff00-\uffef are excluded because Word doesn't
    # count punctuation like 、！ as words)
    chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)

    # Remove CJK chars, extract English word tokens from remainder
    non_chinese = re.sub(r'[\u4e00-\u9fff]+', ' ', text)
    english_words = re.findall(r'[A-Za-z0-9]+', non_chinese)

    return len(chinese_chars) + len(english_words)


# Verified test cases against WPS:
#   "Hello, 世界 2026！"  => 4  (Hello, 世, 界, 2026)
#   "Hello, world"         => 2
#   "中文测试"              => 4
