"""飞书 Webhook 事件解析 — URL 验证 + 消息提取。"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def handle_url_verification(body: dict[str, Any]) -> dict[str, Any] | None:
    """处理飞书开放平台的 URL 验证请求。

    飞书在首次配置 Webhook 时会发送 type=url_verification 的事件，
    需要原样返回 challenge 字段。

    Returns:
        验证响应 dict，如果不是验证请求则返回 None。
    """
    if body.get("type") == "url_verification":
        challenge = body.get("challenge", "")
        logger.info("飞书 URL 验证请求，challenge=%s", challenge)
        return {"challenge": challenge}
    return None


def extract_chat_message(body: dict[str, Any]) -> dict[str, Any] | None:
    """从飞书事件中提取用户消息文本和对话 ID。

    只处理 im.message.receive_v1 类型的消息接收事件。

    Args:
        body: 飞书 Webhook 回调的完整 JSON body。

    Returns:
        {"chat_id": str, "text": str} 或 None（非消息事件或解析失败）。
    """
    header = body.get("header", {})
    event_type = header.get("event_type", "")

    if event_type != "im.message.receive_v1":
        return None

    event = body.get("event", {})
    message = event.get("message", {})
    chat_id = message.get("chat_id", "")
    if not chat_id:
        return None

    # 飞书消息 content 是 JSON 字符串
    content_str = message.get("content", "{}")
    try:
        content = json.loads(content_str)
    except json.JSONDecodeError:
        logger.warning("无法解析消息 content: %s", content_str)
        return None

    text = content.get("text", "").strip()
    if not text:
        return None

    logger.info("收到飞书消息: chat_id=%s, text=%s", chat_id, text[:100])
    return {"chat_id": chat_id, "text": text}
