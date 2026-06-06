# DDL 检测插件

AstrBot 插件 - 自动检测并保存群内 DDL 消息

## 功能特性

- 自动检测群消息中的 DDL 格式（`截止：时间+日期`）
- 调用 LLM 总结 DDL 关键内容
- 用户发送 `/ddl` 查询今日保存的 DDL

## 支持的 DDL 格式

- `截止：6月10日`
- `截止：6-10`
- `截止：6月10日14:00`
- `截止：6月10日 14:00分`

## 使用方法

1. 将插件放入 `data/plugins/` 目录
2. 重启 AstrBot
3. 发送包含 DDL 格式的消息，插件自动检测并保存
4. 发送 `/ddl` 查询今日 DDL

## 项目结构

```
DDLdetectPlugin/
├── src/ddldetect/       # 源代码
│   ├── __init__.py
│   ├── plugin.py        # 插件主逻辑
│   └── utils.py         # 工具函数
├── main.py              # 插件入口
├── metadata.yaml        # 插件配置
├── requirements.txt     # 依赖
├── pyproject.toml       # 项目配置
└── README.md
```

## 开发

```bash
# 安装依赖
pip install -e .

# 代码检查
ruff check src/
```
