"""DDL 检测模块：正则匹配 + 提取"""

import re
from typing import Optional, Tuple

DEFAULT_KEYWORDS = ["截止", "截止时间", "截止日期", "deadline", "ddl", "交作业"]


def parse_keywords(keywords_str: str) -> list:
    """解析 DDL 关键词配置"""
    if not keywords_str:
        keywords_str = ",".join(DEFAULT_KEYWORDS)
    return [k.strip() for k in keywords_str.split(",") if k.strip()]


def build_pattern(keywords: list) -> re.Pattern:
    """构建 DDL 检测正则表达式"""
    keyword_pattern = "|".join(re.escape(k) for k in keywords)

    time_patterns = [
        r"(\d{1,2}月\d{1,2}[日号]?(?:\s*[0-2]?\d(?:[:：点时])\d{1,2}(?:分?)?)?)",
        r"(\d{1,2}[/-]\d{1,2})(?!\d)",
        r"(\d{4}年\d{1,2}月\d{1,2}[日号]?)",
        r"(今天|明天|今晚|明晚)(?:\s*[0-2]?\d(?:[:：点时])\d{1,2}(?:分?)?)?",
        r"((?:本周|下周)?[一二三四五六日天])(?:[早晚]上?\s*[0-2]?\d(?:[:：点时])\d{1,2}(?:分?)?)?",
        r"([早中晚]上?\s*[0-2]?\d(?:[:：点时])\d{1,2}(?:分?)?)",
        r"(\d{1,2}(?:[:：点时])\d{1,2}(?:分)?)",
    ]

    combined_time = "|".join(time_patterns)
    pattern = rf"(({keyword_pattern})[：:为]?\s*({combined_time})|({combined_time})\s*({keyword_pattern}))"
    return re.compile(pattern, re.IGNORECASE)


def extract_ddl(message: str, pattern: re.Pattern, resolve_time_func) -> Optional[Tuple[str, str]]:
    """使用正则从消息中提取 DDL"""
    match = pattern.search(message)
    if not match:
        return None

    time_part = match.group(3) or match.group(4)
    time_part = resolve_time_func(time_part)

    task_desc = message[:match.start()].strip() + message[match.end():].strip()
    if not task_desc:
        task_desc = message.replace(time_part, "").strip()
    if not task_desc:
        task_desc = "未命名任务"

    return task_desc, time_part
