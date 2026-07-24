"""飞书消息回复模块 — 发送交互式卡片消息到飞书对话。"""

import json
import logging
from typing import Any

import requests

from config import get_settings

logger = logging.getLogger(__name__)


def _get_tenant_token() -> str:
    """获取飞书 tenant_access_token，复用 FeishuClient 的认证逻辑。"""
    settings = get_settings()
    response = requests.post(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        json={
            "app_id": settings.feishu_app_id,
            "app_secret": settings.feishu_app_secret,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    token = payload.get("tenant_access_token")
    if not token:
        raise RuntimeError(
            f"获取飞书 tenant_access_token 失败: {payload.get('msg', payload)}"
        )
    return token


def send_card_message(
    chat_id: str,
    title: str,
    count: int,
    map_url: str,
) -> dict[str, Any]:
    """向飞书对话发送一张交互式卡片消息。

    卡片包含标题、地点数量摘要、以及一个"查看地图"按钮。

    Args:
        chat_id: 飞书对话 ID（从 Webhook 事件中获取）
        title: 地图标题，如 "工厂数据分布图"
        count: 地点数量
        map_url: 地图页面的公网可访问 URL

    Returns:
        API 响应 JSON
    """
    token = _get_tenant_token()
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": f"🗺️ {title}"},
            "template": "blue",
        },
        "elements": [
            {
                "tag": "markdown",
                "content": f"共 **{count}** 个地点已标注在地图上。",
            },
            {
                "tag": "action",
                "actions": [
                    {
                        "tag": "button",
                        "text": {"tag": "plain_text", "content": "🔗 查看地图"},
                        "url": map_url,
                        "type": "default",
                    }
                ],
            },
        ],
    }

    response = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": "chat_id"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "receive_id": chat_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False),
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code", 0) != 0:
        logger.error("发送飞书卡片消息失败: %s", payload.get("msg", payload))
        raise RuntimeError(f"发送飞书消息失败: {payload.get('msg', payload)}")
    logger.info("卡片消息发送成功: chat_id=%s", chat_id)
    return payload

def send_text_message(chat_id: str, text: str) -> dict[str, Any]:
    """向飞书对话发送纯文本消息。

    Args:
        chat_id: 飞书对话 ID
        text: 消息文本内容

    Returns:
        API 响应 JSON
    """
    token = _get_tenant_token()
    content = json.dumps({"text": text}, ensure_ascii=False)
    response = requests.post(
        "https://open.feishu.cn/open-apis/im/v1/messages",
        params={"receive_id_type": "chat_id"},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "receive_id": chat_id,
            "msg_type": "text",
            "content": content,
        },
        timeout=15,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code", 0) != 0:
        logger.error("发送飞书文本消息失败: %s", payload.get("msg", payload))
        raise RuntimeError(f"发送飞书消息失败: {payload.get('msg', payload)}")
    else:
        logger.info("文本消息发送成功: chat_id=%s", chat_id)
    return payload
