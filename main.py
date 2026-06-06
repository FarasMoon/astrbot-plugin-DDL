"""AutoDDLDetect - AstrBot 群聊 DDL 自动检测插件"""

import os
import sys
# 确保插件目录在 sys.path 中，使 src.autoddldetect 可导入
_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

import asyncio
from datetime import datetime, timedelta

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import AstrBotConfig
from astrbot.api import logger

from src.autoddldetect.detector import parse_keywords, build_pattern, extract_ddl
from src.autoddldetect.time_parser import resolve_relative_time
from src.autoddldetect.summarizer import summarize_ddl
from src.autoddldetect.renderer import categorize_ddls, format_text_ddl, render_image_card


# ── 静默监听工具函数 ────────────────────────────────────────

def _should_monitor_group(group_id: str, group_mode: str, group_list_str: str) -> bool:
    """判断群是否应被静默监听"""
    if not group_list_str.strip():
        return group_mode == "blacklist"
    group_ids = [g.strip() for g in group_list_str.split(",") if g.strip()]
    if group_mode == "blacklist":
        return group_id not in group_ids
    return group_id in group_ids


def _format_silent_msg(raw_ddl: dict) -> str:
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


# ── DDL 过期清理 ────────────────────────────────────────────

def _clean_expired_ddls(ddl_list: list, now: datetime) -> tuple:
    """清理已过期的 DDL，返回 (有效列表, 清理数量)"""
    valid_ddls = []
    removed_count = 0
    for ddl in ddl_list:
        ddl_time_str = ddl.get('ddl_time', '')
        try:
            for fmt in ['%m月%d日', '%m月%d日%H点', '%m月%d日%H:%M']:
                try:
                    parsed_time = datetime.strptime(ddl_time_str, fmt)
                    parsed_time = parsed_time.replace(year=now.year)
                    if parsed_time < now:
                        removed_count += 1
                    else:
                        valid_ddls.append(ddl)
                    break
                except ValueError:
                    continue
            else:
                valid_ddls.append(ddl)
        except Exception:
            valid_ddls.append(ddl)
    return valid_ddls, removed_count


def _filter_today(ddls: list) -> list:
    """筛选今天的 DDL"""
    today = datetime.now().strftime("%Y-%m-%d")
    return [ddl for ddl in ddls if ddl.get('detected_at', '').startswith(today)]


# 切换命令的临时存储
group_output_format = {}


@register("autoddldetect", "FarasMoon", "DDL 检测插件 - 自动检测并保存群内 DDL 消息", "1.2.0")
class DDLDetectPlugin(Star):
    """DDL 检测插件主类"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.keywords = parse_keywords(config.get("ddl_keywords", ""))
        self.ddl_pattern = build_pattern(self.keywords)
        self.notification_task = None
        self.monitored_groups: set = set()
        self.admin_ids: list = []

    def _is_admin(self, event: AstrMessageEvent) -> bool:
        """检查消息发送者是否为管理员"""
        if not self.admin_ids:
            return False
        sender_id = event.message_obj.sender.user_id if event.message_obj.sender else ""
        return sender_id in self.admin_ids

    # ── 事件处理 ──────────────────────────────────────────────

    async def initialize(self) -> None:
        times_str = self.config.get("notification_times", "08:00")
        self.notification_times = [t.strip() for t in times_str.split(",") if t.strip()]
        admin_str = self.config.get("silent_admin_sid", "")
        self.admin_ids = [a.strip() for a in admin_str.split(",") if a.strip()]
        logger.info(f"AutoDDLDetect 已加载，关键词: {self.keywords}，通知时间: {self.notification_times}，管理员: {self.admin_ids}")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent) -> MessageEventResult:
        """监听群消息，检测 DDL 格式"""
        message_str = event.message_str.strip()
        ddl_info = extract_ddl(message_str, self.ddl_pattern, resolve_relative_time)

        if not ddl_info:
            return

        task_desc, ddl_time = ddl_info
        group_id = event.message_obj.group_id or "unknown"
        sender_name = event.get_sender_name()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        raw_ddl = {
            "task": task_desc,
            "raw_message": message_str,
            "ddl_time": ddl_time,
            "group_id": group_id,
            "sender": sender_name,
            "detected_at": timestamp,
            "message_id": event.message_obj.message_id
        }

        await self._save_ddl(group_id, raw_ddl)
        self.monitored_groups.add(group_id)
        logger.info(f"检测到 DDL: {message_str}")

        if self.config.get("enable_auto_reply", True):
            if self.config.get("enable_llm_summary", True):
                summary = await summarize_ddl(raw_ddl, event, self.context)
                if summary:
                    yield event.plain_result(f"已检测到 DDL：{summary}")

        # 静默监听模式：跨平台推送给所有管理员
        if self.config.get("silent_mode", True) and self.admin_ids:
            group_mode = self.config.get("silent_group_mode", "blacklist")
            group_list_str = self.config.get("silent_group_list", "")
            if _should_monitor_group(group_id, group_mode, group_list_str):
                if self.config.get("enable_llm_summary", True):
                    summary = await summarize_ddl(raw_ddl, event, self.context)
                    if summary:
                        raw_ddl["summary"] = summary
                msg_text = _format_silent_msg(raw_ddl)
                from astrbot.api.star import StarTools
                import astrbot.api.message_components as Comp
                from astrbot.api.event import MessageChain
                platform = event.get_platform_name()
                for admin_id in self.admin_ids:
                    try:
                        chain = MessageChain()
                        chain.chain.append(Comp.Plain(msg_text))
                        admin_session = f"{platform}:FriendMessage:{admin_id}"
                        await StarTools.send_message(admin_session, chain)
                        logger.info(f"[SilentMonitor] 已推送 DDL 给管理员 {admin_id}")
                    except Exception as e:
                        logger.error(f"[SilentMonitor] 推送给 {admin_id} 失败: {e}")

    # ── 存储 ──────────────────────────────────────────────────

    async def _save_ddl(self, group_id: str, ddl_data: dict) -> None:
        key = f"ddl_{group_id}"
        ddl_list = await self.get_kv_data(key, [])
        ddl_list.append(ddl_data)
        await self.put_kv_data(key, ddl_list)

    # ── 查询 DDL ──────────────────────────────────────────────

    @filter.command("ddl")
    async def query_ddl(self, event: AstrMessageEvent) -> MessageEventResult:
        """查询今日保存的 DDL"""
        group_id = event.message_obj.group_id

        # 私聊：检查是否为管理员
        if not group_id:
            if self._is_admin(event):
                result = await self._query_all_groups_ddl(event)
                if isinstance(result, tuple):
                    mode, content = result
                    if mode == "image":
                        yield event.image_result(content)
                    else:
                        yield event.plain_result(content)
                else:
                    yield event.plain_result(result)
                return
            yield event.plain_result("📭 私聊仅管理员(silent_admin_sid)可查看汇总")
            return

        # 群聊：查本群 DDL
        key = f"ddl_{group_id}"
        result = await self._query_single_group(event, group_id, key)
        if isinstance(result, tuple):
            mode, content = result
            if mode == "image":
                yield event.image_result(content)
            else:
                yield event.plain_result(content)
        else:
            yield event.plain_result(result)

    async def _query_single_group(self, event, group_id, key):
        """查询并格式化单个群的 DDL"""
        ddl_list = await self.get_kv_data(key, [])
        now = datetime.now()
        valid_ddls, removed_count = _clean_expired_ddls(ddl_list, now)
        if removed_count > 0:
            await self.put_kv_data(key, valid_ddls)

        today_ddls = _filter_today(valid_ddls)
        if not today_ddls:
            return "📭 今日暂无 DDL 记录"

        return await self._format_ddl_output(event, group_id, today_ddls)

    async def _query_all_groups_ddl(self, event):
        """汇总所有监听群的 DDL（管理员专用），归并到一张卡片"""
        groups = sorted(self.monitored_groups)
        if not groups:
            return "📭 暂无监听的群组"

        group_mode = self.config.get("silent_group_mode", "blacklist")
        group_list_str = self.config.get("silent_group_list", "")
        all_today_ddls = []

        for gid in groups:
            if not _should_monitor_group(gid, group_mode, group_list_str):
                continue

            key = f"ddl_{gid}"
            ddl_list = await self.get_kv_data(key, [])
            now = datetime.now()
            valid_ddls, removed_count = _clean_expired_ddls(ddl_list, now)
            if removed_count > 0:
                await self.put_kv_data(key, valid_ddls)

            today_ddls = _filter_today(valid_ddls)
            for ddl in today_ddls:
                ddl["group_id"] = gid
            all_today_ddls.extend(today_ddls)

        if not all_today_ddls:
            return "📭 所有监听群今日暂无 DDL 记录"

        # 归并所有群的 DDL，渲染单张卡片
        merged_id = "__admin_all_groups__"
        return await self._format_ddl_output(event, merged_id, all_today_ddls)

    async def _format_ddl_output(self, event, group_id, today_ddls):
        """格式化单个群的 DDL 输出，返回 (type, content) 或纯文本"""
        urgent_hours = self.config.get("urgent_hours", 24)
        soon_hours = self.config.get("soon_hours", 48)
        urgent_ddls, soon_ddls, normal_ddls = categorize_ddls(today_ddls, urgent_hours, soon_hours)

        if self.config.get("enable_llm_summary", True):
            for ddl in urgent_ddls + soon_ddls + normal_ddls:
                summary = await summarize_ddl(ddl, event, self.context)
                if summary:
                    ddl['summary'] = summary

        output_format = group_output_format.get(group_id, self.config.get("output_format", "text"))

        if output_format == "image":
            try:
                bg_mode = self.config.get("background_mode", "image")
                bg_value = self.config.get("background_color", "#f0f0f0") if bg_mode == "color" else self.config.get("background_api", "https://t.alcy.cc/moez")
                url = await render_image_card(
                    self, urgent_ddls, soon_ddls, normal_ddls,
                    urgent_hours, soon_hours, bg_mode, bg_value
                )
                return ("image", url)
            except Exception as e:
                logger.error(f"生成图片失败: {e}")
        return ("text", format_text_ddl(urgent_ddls, soon_ddls, normal_ddls, urgent_hours, soon_hours))

    # ── 清除 DDL ──────────────────────────────────────────────

    @filter.command("clearddl", aliases=["清除ddl"])
    async def clear_ddl(self, event: AstrMessageEvent) -> MessageEventResult:
        """清除当前群聊/用户的 DDL；静默监听模式下管理员清除所有"""
        group_id = event.message_obj.group_id

        # 静默监听模式 + 管理员（群聊或私聊）→ 清除所有群的 DDL
        if self.config.get("silent_mode", True) and self._is_admin(event):
            yield event.plain_result(await self._clear_all_groups_ddl())
            return

        # 普通用户：清除当前群/私聊的 DDL
        gid = group_id or "unknown"
        key = f"ddl_{gid}"
        ddl_list = await self.get_kv_data(key, [])
        today = datetime.now().strftime("%Y-%m-%d")
        remaining_ddls = [ddl for ddl in ddl_list if not ddl.get('detected_at', '').startswith(today)]

        if len(ddl_list) > len(remaining_ddls):
            await self.put_kv_data(key, remaining_ddls)
            count = len(ddl_list) - len(remaining_ddls)
            yield event.plain_result(f"✅ 已清除今日的 {count} 条 DDL 记录")
        else:
            yield event.plain_result("📭 今日暂无 DDL 记录可清除")

    @filter.command("清除所有ddl")
    async def clear_all_ddl(self, event: AstrMessageEvent) -> MessageEventResult:
        """清除所有缓存的 DDL（仅管理员）"""
        if not self._is_admin(event):
            yield event.plain_result("❌ 仅管理员可清除所有 DDL")
            return
        yield event.plain_result(await self._clear_all_groups_ddl())

    async def _clear_all_groups_ddl(self) -> str:
        """清除所有已监听群的 DDL 数据"""
        if not self.monitored_groups:
            return "📭 暂无监听的群组数据"

        total_removed = 0
        for gid in list(self.monitored_groups):
            key = f"ddl_{gid}"
            await self.put_kv_data(key, [])
            total_removed += 1

        self.monitored_groups.clear()
        return f"✅ 已清除 {total_removed} 个群的全部 DDL 记录"

    # ── 切换输出格式 ──────────────────────────────────────────

    @filter.command("ddl_image")
    async def switch_to_image(self, event: AstrMessageEvent) -> MessageEventResult:
        group_id = event.message_obj.group_id or "unknown"
        group_output_format[group_id] = "image"
        yield event.plain_result("✅ 已切换到图片输出模式")

    @filter.command("ddl_text")
    async def switch_to_text(self, event: AstrMessageEvent) -> MessageEventResult:
        group_id = event.message_obj.group_id or "unknown"
        group_output_format[group_id] = "text"
        yield event.plain_result("✅ 已切换到文字输出模式")

    # ── 测试 ──────────────────────────────────────────────────

    @filter.command("ddl_test")
    async def test_notification(self, event: AstrMessageEvent) -> MessageEventResult:
        """测试定时通知"""
        group_id = event.message_obj.group_id or "unknown"
        key = f"ddl_{group_id}"
        ddl_list = await self.get_kv_data(key, [])
        today = datetime.now().strftime("%Y-%m-%d")
        today_ddls = [ddl for ddl in ddl_list if ddl.get('detected_at', '').startswith(today)]

        if not today_ddls:
            yield event.plain_result("今日暂无 DDL 可测试")
            return

        urgent_hours = self.config.get("urgent_hours", 24)
        soon_hours = self.config.get("soon_hours", 48)
        urgent_ddls, soon_ddls, normal_ddls = categorize_ddls(today_ddls, urgent_hours, soon_hours)

        output_format = group_output_format.get(group_id, self.config.get("output_format", "text"))

        if self.config.get("enable_llm_summary", True):
            for ddl in urgent_ddls + soon_ddls + normal_ddls:
                summary = await summarize_ddl(ddl, event, self.context)
                if summary:
                    ddl['summary'] = summary

        if output_format == "image":
            try:
                bg_mode = self.config.get("background_mode", "image")
                bg_value = self.config.get("background_color", "#f0f0f0") if bg_mode == "color" else self.config.get("background_api", "https://t.alcy.cc/moez")
                url = await render_image_card(
                    self, urgent_ddls, soon_ddls, normal_ddls,
                    urgent_hours, soon_hours, bg_mode, bg_value
                )
                yield event.image_result(url)
            except Exception as e:
                yield event.plain_result(f"生成测试图片失败: {e}")
        else:
            yield event.plain_result(format_text_ddl(urgent_ddls, soon_ddls, normal_ddls, urgent_hours, soon_hours))

    # ── 销毁 ──────────────────────────────────────────────────

    async def terminate(self) -> None:
        if self.notification_task and not self.notification_task.done():
            self.notification_task.cancel()
            try:
                await self.notification_task
            except asyncio.CancelledError:
                pass
        logger.info("AutoDDLDetect 已卸载")
