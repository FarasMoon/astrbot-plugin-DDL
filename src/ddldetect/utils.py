"""
DDL 检测插件 - 工具模块
"""

import re
from datetime import datetime
from typing import Optional


# DDL 时间匹配正则
DDL_PATTERN = re.compile(
    r'截止[：:]\s*(\d{1,2}[月/-]\d{1,2}[日/]?(?:[^\d月日]*?\d{1,2}[时:]\d{1,2}分?)?)'
)


def extract_ddl_time(message: str) -> Optional[re.Match[str]]:
    """
    从消息中提取 DDL 时间

    Args:
        message: 原始消息文本

    Returns:
        匹配对象或 None
    """
    return DDL_PATTERN.search(message)


def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    格式化时间戳

    Args:
        dt: datetime 对象，默认为当前时间

    Returns:
        格式化的时间字符串
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def is_today(timestamp: str) -> bool:
    """
    判断时间戳是否为今天

    Args:
        timestamp: 时间戳字符串

    Returns:
        是否为今天
    """
    today = datetime.now().strftime("%Y-%m-%d")
    return timestamp.startswith(today)
