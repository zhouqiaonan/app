---
title: "飞书机器人对话模式 — HTTP Webhook 集成"
type: feature
created: 2026-07-24T02:38:40.944Z
status: draft
branch: feature/-http-webhook-
---

# 飞书机器人对话模式 — HTTP Webhook 集成

## Summary

将当前的浏览器聊天页面（`/chat`）升级为飞书机器人对话模式。用户在飞书里 @机器人，通过 HTTP Webhook 回调到我们的服务，ReAct Agent 处理后发送交互式卡片回复。支持多轮对话，基于 chat_id 自动记忆上下文。

## Architecture Diagram

```mermaid
graph TD
    subgraph "飞书客户端"
        U[用户 @机器人<br/>"生成工厂数据地图"]
    end

    subgraph "飞书服务器"
        FS[飞书开放平台<br/>事件回调]
    end

    subgraph "我们的服务"
        WH["POST /feishu/webhook<br/>（新增）"]
        PARSE["feishu_webhook.py<br/>消息解析 + URL 验证"]
        AGENT["agent_llm.py<br/>run_chat_agent<br/>+ MemorySaver 多轮"]
        REPLY["feishu_reply.py<br/>发送交互式卡片"]
        API["POST /agent/chat<br/>（保留）"]
        UI["GET /chat<br/>（保留）"]
    end

    subgraph "外部服务"
        FSAPI[飞书消息 API<br/>发送卡片]
        DS[DeepSeek API]
    end

    U -->|发送消息| FS
    FS -->|HTTP POST| WH
    WH --> PARSE
    PARSE -->|提取文本 + chat_id| AGENT
    AGENT -->|result| REPLY
    REPLY -->|卡片 JSON| FSAPI
    FSAPI -->|飞书消息| U
    AGENT -.-> DS
```

## Tasks

- [ ] Task 1: 多轮对话支持 — agent_llm.py 添加 MemorySaver
  - AC: `get_agent()` 使用 `MemorySaver` checkpointer
  - AC: `run_chat_agent()` 将 `session_id` 传入 `thread_id`
  - AC: `/agent/chat` 多轮对话验证通过

- [ ] Task 2: 飞书消息回复模块 — 新建 services/feishu_reply.py
  - AC: `send_card_message(chat_id, title, count, url)` 发送交互式卡片
  - AC: 卡片包含标题、地点数、查看地图按钮
  - AC: 复用现有 `FeishuClient` 的 token 获取逻辑

- [ ] Task 3: 飞书 Webhook 消息解析 — 新建 services/feishu_webhook.py
  - AC: `handle_url_verification(body)` 处理飞书 URL 验证
  - AC: `extract_chat_message(body)` 从事件中提取文本 + chat_id
  - AC: 只处理 `im.message.receive_v1` 类型事件

- [ ] Task 4: Webhook 端点 — main.py 新增 POST /feishu/webhook
  - AC: 接收飞书事件回调，返回 URL 验证 challenge
  - AC: 提取消息 → 调 run_chat_agent → 发送卡片回复
  - AC: 不受 `verify_api_key` 鉴权限制（飞书有自己签名验证）
  - AC: 异常 200 返回（飞书要求立即返回，不阻塞）

- [ ] Task 5: 构建验证
  - AC: 全量导入成功
  - AC: `/health` 正常
  - AC: `/chat` 正常（不受影响）
  - AC: `/agent/chat` 正常（不受影响）
  - AC: `/feishu/webhook` URL 验证返回 challenge

## Technical Approach

### Phase 1: 多轮对话底层（Task 1）

修改 `agent_llm.py`，在 ReAct Agent 编译时注入 `MemorySaver`，使用 `session_id` 作为 `thread_id` 实现上下文记忆。

### Phase 2: 飞书能力（Task 2-3）

新建两个 service 模块：
- `feishu_reply.py`：构造飞书卡片消息 JSON，调飞书 API 发送
- `feishu_webhook.py`：解析飞书事件、URL 验证

### Phase 3: 接入（Task 4）

在 `main.py` 新增 `/feishu/webhook` 端点，串联消息解析 → Agent → 卡片回复。

## Key Decisions

1. **HTTP Webhook** 而非 WebSocket — 跟 FastAPI 统一架构
2. **交互式卡片** 回复 — 比纯文本体验好
3. **chat_id 作为 thread_id** — 天然多轮，无需额外状态管理
4. **MemorySaver 内存存储** — 服务重启丢失历史，后续可换 SQLite/Redis
5. **Webhook 不鉴权** — 飞书有事件签名，安全由飞书侧保证
## Tasks

- [ ] Task 1: 多轮对话支持 — agent_llm.py 添加 MemorySaver checkpointer
- [ ] Task 2: 飞书消息回复模块 — 新建 services/feishu_reply.py 发送交互式卡片
- [ ] Task 3: 飞书 Webhook 消息解析 — 新建 services/feishu_webhook.py 事件解析 + URL 验证
- [ ] Task 4: Webhook 端点 — main.py 新增 POST /feishu/webhook
- [ ] Task 5: 构建验证 — 全量导入 + 端点检查
