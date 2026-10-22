# Agent Learn

用于学习 Agent 开发的练习项目。目前包含一个基于 **FastAPI + LangChain** 的「反馈分类」Demo：把一段用户反馈交给大模型，输出结构化的问题分类、优先级、摘要和建议动作。

## 目录结构

```
002_phase_project/
├── README.md
├── .gitignore
└── agent-demo/              # FastAPI + LangChain 示例
    ├── config.example.toml  # 配置模板（可安全提交）
    ├── config.toml          # 真实配置，含 API Key（已被 .gitignore 排除）
    ├── pyproject.toml
    ├── uv.lock
    └── src/agent_demo/
        ├── main.py          # FastAPI 应用入口
        ├── config.py        # 读取并校验 config.toml
        ├── router.py        # 路由
        ├── schema.py        # 结构化输出模型
        └── service.py       # 调用大模型的核心逻辑
```

## 快速开始

### 1. 安装依赖

项目使用 [uv](https://docs.astral.sh/uv/) 管理依赖：

```bash
cd agent-demo
uv sync
```

### 2. 配置 API Key

复制示例配置，然后填入你自己的密钥：

```bash
# Windows
copy config.example.toml config.toml

# macOS / Linux
cp config.example.toml config.toml
```

编辑 `config.toml`：

```toml
api_key = "你的 DeepSeek API Key"
base_url = "https://api.deepseek.com"
model = "deepseek-flash"
```

> `config.toml` 已被 `.gitignore` 排除，**不会**被提交到仓库。

### 3. 启动服务

```bash
uv run uvicorn agent_demo.main:app --reload
```

打开 http://127.0.0.1:8000/docs 可以看到自动生成的接口文档。

## 接口说明

### POST /feedback

把一段用户反馈交给大模型，返回分类、优先级、摘要和建议动作。

请求示例（注意 `info` 是查询参数）：

```bash
curl -X POST "http://127.0.0.1:8000/feedback?info=登录不上去，一直提示密码错误"
```

返回示例：

```json
{
  "category": "账号问题",
  "priority": "high",
  "summary": "用户无法登录，提示密码错误",
  "suggested_action": "引导用户重置密码并核实账号状态"
}
```

## 实现要点

- 模型调用使用 LangChain 的 `with_structured_output`，返回值受 Pydantic 模型约束，无需自己解析 JSON。
- 密钥通过 Pydantic 的 `SecretStr` 承载，只有显式调用 `.get_secret_value()` 才能拿到明文，避免日志或异常信息中意外泄露。
- 配置使用标准库 `tomllib` 读取，启动时完成校验，配置有问题会在服务启动阶段直接报错。
