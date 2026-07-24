"""ReAct Agent 实现 — 基于 DeepSeek Chat 的飞书地图助手。

提供基于 LLM 的对话式地图生成能力，Agent 自主决策调用工具链完成
用户需求：查表 → 读数据 → 地理编码 → 距离计算 → 生成地图。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from config import get_settings
from tools.llm_tools import (
    calculate_distances,
    geocode_addresses_async,
    list_feishu_tables,
    read_feishu_records,
    render_map,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """你是一个飞书地图助手，帮助用户将飞书多维表格中的地点数据可视化生成交互式地图。

## 可用工具
1. **list_feishu_tables** — 列出所有已配置的飞书多维表格
2. **read_feishu_records** — 读取指定表格中的地点记录（需要 app_token 和 table_id）
3. **geocode_addresses_async** — 对地点进行批量地理编码，获取经纬度坐标
4. **calculate_distances** — 计算地点之间的两两直线距离矩阵
5. **render_map** — 生成交互式地址标注地图 HTML 页面

## 工作流程
当用户提出生成地图的需求时，请严格按照以下顺序执行：

1. **先调用 list_feishu_tables** 查看当前有哪些可用表格，永远不要猜测或假设表格名称。
2. 根据用户的需求匹配到合适的表格后，**调用 read_feishu_records** 读取该表格中的地点数据。
3. 数据读取成功后，**调用 geocode_addresses_async** 对地点地址进行地理编码，获取经纬度坐标。
4. **调用 calculate_distances** 计算地点之间的距离矩阵。
5. 最后**调用 render_map** 生成交互式地图。

## 行为约束
- **永远先查表再读数据**，不要猜测表格名称或 app_token。
- 如果用户的意图不明确，**列出所有可用表格让用户选择**，不要自作主张。
- 生成地图后，**必须在回复中返回地图 URL**。
- 如果某个工具调用失败，**必须告诉用户失败原因和失败的是哪个工具**，不要隐瞒错误。
- **用中文回复用户**，回复中给出地点数量和地图 URL。

## 回复格式
成功时给出总结：包含处理了几个地点、成功地理编码了几个、地图 URL。
失败时说明原因，并给出用户可以采取的行动建议。
"""

# ---------------------------------------------------------------------------
# Lazy singleton pattern
# ---------------------------------------------------------------------------

_agent: Any | None = None


def get_agent():
    """创建并缓存 ReAct agent（懒加载单例模式）。

    首次调用时初始化 ChatOpenAI（DeepSeek）模型并编译 agent，
    后续调用直接返回缓存的 agent 实例。
    """
    global _agent
    if _agent is not None:
        return _agent

    settings = get_settings()

    if not settings.deepseek_api_key:
        raise ValueError("未配置 DEEPSEEK_API_KEY")

    llm = ChatOpenAI(
        model="deepseek-v4-pro",
        api_key=settings.deepseek_api_key,
        base_url="https://llm.meiying.homes/v1",
        temperature=0.1,
    )

    tools = [
        list_feishu_tables,
        read_feishu_records,
        geocode_addresses_async,
        calculate_distances,
        render_map,
    ]

    _agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT, checkpointer=MemorySaver())
    logger.info("ReAct agent 初始化完成（DeepSeek Chat）")
    return _agent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _extract_map_url(messages: list[dict]) -> str | None:
    """从 agent 消息历史中提取 render_map 返回的地图 URL。

    遍历所有消息，查找 tool 角色中名为 render_map 的调用结果，
    从中提取 url 字段。
    """
    for msg in messages:
        role = msg.get("role") or msg.get("type", "")
        if role == "tool" and msg.get("name") == "render_map":
            content = msg.get("content", "")
            if isinstance(content, str):
                try:
                    result = json.loads(content)
                    if isinstance(result, dict) and "url" in result:
                        return result["url"]
                except json.JSONDecodeError:
                    logger.warning("render_map tool output is not valid JSON, skipping")
                    continue
    return None


def run_chat_agent(query: str, session_id: str | None = None) -> dict:
    """执行单轮对话式地图生成。

    使用 ReAct agent 自主决策工具调用链，将用户的自然语言请求
    转换为地图生成流程。

    Args:
        query: 用户的自然语言请求
        session_id: 会话 ID，相同 ID 共享对话上下文。传入飞书的 chat_id 实现多轮对话。

    Returns:
        dict with keys:
            reply (str): Agent 的自然语言回复
            map_url (str | None): 生成的地图 URL，未生成则为 None
            logs (list[str]): 执行日志
            error (str): 错误信息，无错误时为空字符串
    """
    logs: list[str] = []

    # 检查 API key 配置
    settings = get_settings()
    if not settings.deepseek_api_key:
        logger.warning("DEEPSEEK_API_KEY 未配置")
        return {
            "reply": "抱歉，系统未配置大模型 API Key，无法处理您的请求。",
            "map_url": None,
            "logs": logs,
            "error": "未配置 DEEPSEEK_API_KEY，请在 .env 中设置",
            "success_count": 0,
        }

    # 获取 agent
    try:
        agent = get_agent()
    except Exception as exc:
        logger.exception("初始化 agent 失败")
        return {
            "reply": f"初始化 AI 助手失败：{exc}",
            "map_url": None,
            "logs": logs,
            "error": f"初始化 agent 失败: {exc}",
            "success_count": 0,
        }

    # 构建消息
    messages: list[dict] = [{"role": "user", "content": query}]

    # 调用 agent
    try:
        config = {"configurable": {"thread_id": session_id or "default"}}
        result = agent.invoke({"messages": messages}, config)
    except Exception as exc:
        logger.exception("Agent 调用失败")
        return {
            "reply": f"处理请求时发生错误：{exc}，请稍后重试。",
            "map_url": None,
            "logs": logs,
            "error": f"Agent 调用失败: {exc}",
            "success_count": 0,
        }

    # 提取回复和地图 URL
    all_messages = result.get("messages", [])
    all_messages_dicts = [
        msg if isinstance(msg, dict) else _message_to_dict(msg) for msg in all_messages
    ]

    # 提取最后一条 AI 消息作为回复
    reply = "抱歉，未能生成有效回复，请重试。"
    for msg in reversed(all_messages_dicts):
        if msg.get("type") == "ai" or msg.get("role") == "ai":
            content = msg.get("content", "")
            if content and isinstance(content, str) and content.strip():
                reply = content.strip()
                break

    # 提取地图 URL
    map_url = _extract_map_url(all_messages_dicts)

    return {
        "reply": reply,
        "map_url": map_url,
        "logs": logs,
        "error": "",
        "success_count": 0,  # LLM path doesn't track count; render_map returns count separately
    }


def _message_to_dict(msg: Any) -> dict:
    """将 LangChain message 对象转换为普通 dict，便于遍历提取字段。"""
    try:
        result: dict = {"type": getattr(msg, "type", "unknown")}
        result["content"] = getattr(msg, "content", "")
        for attr in ("name", "tool_calls", "tool_call_id", "role"):
            if hasattr(msg, attr):
                result[attr] = getattr(msg, attr)
        return result
    except Exception:
        return {"type": "unknown", "content": str(msg)}
