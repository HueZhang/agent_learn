# agent-demo

基于 FastAPI + LangChain 的反馈分类 Demo。把一段用户反馈交给大模型，返回结构化的分类结果。

## 安装

```bash
uv sync
```

## 配置

复制示例配置并填入自己的 API Key：

```bash
# Windows
copy config.example.toml config.toml

# macOS / Linux
cp config.example.toml config.toml
```

`config.toml` 已被 `.gitignore` 排除，不会被提交。

## 运行

```bash
uv run uvicorn agent_demo.main:app --reload
```

接口文档：http://127.0.0.1:8000/docs

## 接口

`POST /feedback?info=<待分析文本>`

返回字段：

| 字段 | 说明 |
| --- | --- |
| `category` | 问题类型：网络问题 / 账号问题 / 功能问题 / 其他 |
| `priority` | 优先级：low / medium / high |
| `summary` | 一句话摘要 |
| `suggested_action` | 建议处理动作 |
