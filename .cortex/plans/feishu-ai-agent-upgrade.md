---
title: 飞书地图智能体升级
type: feature
branch: feature/feishu-ai-agent-upgrade
created: 2026-07-15
---

# 计划：飞书地图智能体升级

## Summary

将当前的飞书自定义应用机器人（固定指令 "生成地图 app_token=xxx table_id=yyy"）升级为飞书 AI 智能体。用户可以用自然语言对话，智能体自动理解意图、提取参数（不足时追问），调用现有 `/agent/run` 接口生成地图。

## Tasks

- [ ] Task 1: 代码清理 — 删除旧的飞书事件处理模块
  - AC: 删除 `services/feishu_events.py`
  - AC: 删除 `services/message_parser.py`
  - AC: 删除 `services/feishu_message.py`
  - AC: 移除 `main.py` 中的 `/feishu/events` 路由及相关 import

- [ ] Task 2: 添加 API 鉴权机制
  - AC: `config.py` 新增 `api_key` 配置项（默认值空字符串，未配置时不强制鉴权以兼容本地开发）
  - AC: 创建 `services/auth.py` 鉴权依赖（Bearer Token 校验，未配置 API_KEY 时跳过鉴权）
  - AC: `/agent/run` 端点添加鉴权依赖
  - AC: 无效 Token 返回 401 Unauthorized

- [ ] Task 3: 优化 /agent/run 响应格式 + 添加工具描述端点
  - AC: 确保返回结构化 JSON，包含 task_id, success_count, url, logs, error
  - AC: 错误信息使用清晰的中文描述
  - AC: 添加 GET `/agent/run/openapi.json` 端点，返回工具描述（供飞书智能体注册用）

- [ ] Task 4: 移除不再需要的 import 和依赖
  - AC: main.py 中移除 feishu_events/feishu_message/message_parser 相关 import
  - AC: requirements.txt 检查是否需要更新

- [ ] Task 5: 构建验证
  - AC: `python -c "from app.main import app"` 成功无报错
  - AC: `/health` 端点正常响应

## Technical Approach

### 代码清理
删除不再需要的飞书事件处理代码，保持项目简洁。核心管线（LangGraph + 四个 Tool）完全不变。

删除的文件：feishu_events.py, message_parser.py, feishu_message.py
删除的路由：POST /feishu/events

### API 鉴权
config.py 新增 api_key 配置，services/auth.py 新增 Bearer Token 校验依赖。
未配置时跳过鉴权以兼容本地开发。

### 飞书智能体平台配置
在飞书开放平台创建 AI 智能体，配置系统提示词和 generate_map 工具。
