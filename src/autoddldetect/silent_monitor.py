"""静默监听模块 - 跨群监听 DDL 并推送给管理员"""

from datetime import datetime

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.core.message.components import Plain
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.star.star_tools import StarTools


def should_monitor_group(
    group_id: str,
    group_mode: str,
    group_list_str: str,
) -> bool:
    """判断群是否应被静默监听

    Args:
        group_id: 群号
        group_mode: blacklist / whitelist
        group_list_str: 逗号分隔的群号列表

    Returns:
        True 表示该群需要被监听
    """
    if not group_list_str.strip():
        # 列表为空，黑名单模式监听所有，白名单模式监听空
        return group_mode == "blacklist"

    group_ids = [g.strip() for g in group_list_str.split(",") if g.strip()]
    if group_mode == "blacklist":
        return group_id not in group_ids
    else:
        return group_id in group_ids


def format_silent_msg(raw_ddl: dict) -> str:
    """格式化静默监听推送消息"""
    task = raw_ddl.get("summary") or raw_ddl.get("task", raw_ddl.get("raw_message", ""))
    ddl_time = raw_ddl.get("ddl_time", "未知")
    sender = raw_ddl.get("sender", "未知")
    group_id = raw_ddl.get("group_id", "未知")
    detected_at = raw_ddl.get("detected_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    return (
        f"[DDL监听]\n"
        f"群: {group_id}\n"
        f"任务: {task}\n"
        f"截止: {ddl_time}\n"
        f"来自: {sender}\n"
        f"时间: {detected_at}"
    )


async def notify_admin(
    event: AstrMessageEvent,
    raw_ddl: dict,
    admin_sid: str,
) -> None:
    """向管理员推送 DDL 消息

    Args:
        event: 消息事件（用于获取平台信息）
        raw_ddl: DDL 数据
        admin_sid: 管理员 QQ 号
    """
    if not admin_sid:
        return

    platform = event.get_platform_name()
    msg_text = format_silent_msg(raw_ddl)
    chain = MessageChain()
    chain.chain.append(Plain(msg_text))

    try:
        await StarTools.send_message_by_id(
            type="PrivateMessage",
            id=admin_sid,
            message_chain=chain,
            platform=platform,
        )
        logger.info(f"[SilentMonitor] 已推送 DDL 给管理员 {admin_sid}")
    except Exception as e:
        logger.error(f"[SilentMonitor] 推送失败: {e}")
