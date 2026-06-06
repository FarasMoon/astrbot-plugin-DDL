<div align="center">

# AstrBot DDL 检测插件

自动检测群聊 DDL 消息，LLM 总结 + 图片展示。

![version](https://img.shields.io/badge/version-1.2.0-blue.svg)
![license](https://img.shields.io/badge/license-AGPL--3.0-green.svg)
![AstrBot](https://img.shields.io/badge/AstrBot-%3E%3D4.5.7-orange.svg)
![python](https://img.shields.io/badge/python-3.10%2B-blue.svg)

</div>

> **作者**: FarasMoon | **许可**: [AGPL-3.0](LICENSE)
> 
> 大量 vibe coding 注意  
> 可能维护困难

---

## 核心功能

| 功能 | 说明 |
| --- | --- |
| 自动检测 | 正则匹配关键词 + 时间格式 |
| LLM 总结 | 调用大模型生成不超过10字的精简总结 |
| 紧急分类 | 可配置时间阈值，分 马上截止 / 很快截止 / 普通 |
| 图片输出 | HTML 卡片 + 随机背景图，三个栏目始终显示 |
| 定时通知 | 每日定时推送 DDL 列表 |
| 过期清理 | 超时 DDL 自动清除 |

---

## 安装

```powershell
cd AstrBot\data\plugins
git clone https://github.com/FarasMoon/astrbot-plugin-DDL.git
```

重启 AstrBot 即可加载。无额外依赖。

---

## 基础配置

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| ddl_keywords | DDL 检测关键词 | 截止,截止时间,截止日期,deadline,ddl,交作业 |
| enable_llm_summary | 启用 LLM 总结 | 开启 |
| urgent_hours | 马上截止 时间阈值（小时） | 24 |
| soon_hours | 很快截止 时间阈值（小时） | 48 |
| output_format | 输出格式（image/text） | image |
| background_api | 背景图 API | 随机二次元图 |
| enable_notification | 定时通知开关 | 关闭 |
| notification_time | 通知时间（HH:MM） | 08:00 |

---

## 指令

| 指令 | 说明 |
| --- | --- |
| `/ddl` | 查询今日 DDL |
| `/清除ddl` | 清除今日 DDL |

---

## 社区

[提交 Issue](https://github.com/FarasMoon/astrbot-plugin-DDL/issues)
