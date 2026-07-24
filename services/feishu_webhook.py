"""飞书 Webhook 事件解析 — URL 验证 + 消息提取。"""

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# Event deduplication: store recently processed event_ids with timestamps
# Feishu webhook may deliver the same event multiple times
_recent_events: dict[str, float] = {}
_EVENT_TTL = 300  # 5 minutes — clear old entries periodically


def is_duplicate_event(event_id: str) -> bool:
    """Check if an event has already been processed.

    Feishu webhook has at-least-once delivery — same event may arrive twice.
    Returns True if the event was already processed within the TTL window.
    """
    now = time.time()
    # Clean expired entries
    expired = [eid for eid, ts in _recent_events.items() if now - ts > _EVENT_TTL]
    for eid in expired:
        del _recent_events[eid]

    if event_id in _recent_events:
        return True
    _recent_events[event_id] = now
    return False


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
    event_id = header.get("event_id", "")
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

    logger.info("收到飞书消息: event_id=%s, chat_id=%s, text=%s", event_id, chat_id, text[:100])
    return {"event_id": event_id, "chat_id": chat_id, "text": text}


def is_bot_message(body: dict[str, Any]) -> bool:
    """判断消息事件是否来自机器人自身。

    机器人自己发送的交互式卡片和富文本消息会再次触发 Webhook 回调，
    必须过滤掉，否则形成死循环。通过 msg_type 字段进行简单启发式判断：
    ``interactive``（卡片消息）和 ``post``（富文本）均为机器人发出。

    Args:
        body: 飞书 Webhook 回调的完整 JSON body。

    Returns:
        True 表示该消息来自机器人自身，需要跳过处理。
    """
    event = body.get("event", {})
    message = event.get("message", {})
    msg_type = message.get("msg_type", "")

    if msg_type in ("interactive", "post"):
        logger.info("跳过机器人自己的消息: msg_type=%s", msg_type)
        return True
    return False
