"""
DDL Detect Plugin Entry Point
DDL 检测插件入口文件
"""

import re
from datetime import datetime
from typing import Optional

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("ddldetect", "YourName", "DDL 检测插件 - 自动检测并保存群内 DDL 消息", "1.0.0")
class DDLDetectPlugin(Star):
    """DDL 检测插件主类"""

    def __init__(self, context: Context):
        super().__init__(context)
        self.ddl_pattern = re.compile(
            r'截止[：:]\s*(\d{1,2}[月/-]\d{1,2}[日/]?(?:[^\d月日]*?\d{1,2}[时:]\d{1,2}分?)?)'
        )

    async def initialize(self) -> None:
        """插件初始化"""
        logger.info("DDL 检测插件已加载")

    @filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent) -> MessageEventResult:
        """监听群消息，检测 DDL 格式"""
        message_str = event.message_str.strip()

        match = self.ddl_pattern.search(message_str)
        if not match:
            return

        ddl_time = match.group(1)
        group_id = event.message_obj.group_id or "unknown"
        sender_name = event.get_sender_name()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        raw_ddl = {
            "raw_message": message_str,
            "ddl_time": ddl_time,
            "group_id": group_id,
            "sender": sender_name,
            "detected_at": timestamp,
            "message_id": event.message_obj.message_id
        }

        await self._save_ddl(group_id, raw_ddl)
        logger.info(f"检测到 DDL: {message_str}")

        summary = await self._summarize_ddl(raw_ddl)
        if summary:
            yield event.plain_result(f"已检测到 DDL 并保存：\n{summary}")

    async def _save_ddl(self, group_id: str, ddl_data: dict) -> None:
        """保存 DDL 到存储"""
        key = f"ddl_{group_id}"
        ddl_list = await self.get_kv_data(key, [])
        ddl_list.append(ddl_data)
        await self.put_kv_data(key, ddl_list)

    async def _summarize_ddl(self, ddl_data: dict) -> Optional[str]:
        """调用 LLM 总结 DDL"""
        try:
            prompt = self._build_summary_prompt(ddl_data)
            llm_resp = await self.context.llm_generate(
                chat_provider_id="",
                prompt=prompt,
            )
            return llm_resp.completion_text.strip() if llm_resp else None
        except Exception as e:
            logger.error(f"LLM 总结失败: {e}")
            return None

    def _build_summary_prompt(self, ddl_data: dict) -> str:
        """构建 LLM 总结提示词"""
        return f"""请帮我总结以下 DDL 信息，提取关键内容，生成简洁的格式：

原始消息：{ddl_data['raw_message']}
截止时间：{ddl_data['ddl_time']}
发送者：{ddl_data['sender']}
检测时间：{ddl_data['detected_at']}

请用一句话总结这个 DDL，包含：任务内容和截止时间。"""

    @filter.command("ddl")
    async def query_ddl(self, event: AstrMessageEvent) -> MessageEventResult:
        """查询今日保存的 DDL"""
        group_id = event.message_obj.group_id or "unknown"
        key = f"ddl_{group_id}"

        ddl_list = await self.get_kv_data(key, [])
        today = datetime.now().strftime("%Y-%m-%d")
        today_ddls = [
            ddl for ddl in ddl_list
            if ddl.get('detected_at', '').startswith(today)
        ]

        if not today_ddls:
            yield event.plain_result("今日暂无保存的 DDL。")
            return

        result = [f"今日 DDL 共 {len(today_ddls)} 条：\n"]
        for i, ddl in enumerate(today_ddls, 1):
            msg_preview = ddl.get('raw_message', '')[:50]
            result.append(
                f"{i}. {ddl.get('ddl_time', '未知')} - {ddl.get('sender', '未知')}\n"
                f"   原消息：{msg_preview}..."
            )

        yield event.plain_result("\n".join(result))

    async def terminate(self) -> None:
        """插件销毁时调用"""
        logger.info("DDL 检测插件已卸载")
