import json
from typing import Any


def is_url_verification(payload: dict[str, Any]) -> bool:
    return payload.get("type") == "url_verification"


def verify_token(payload: dict[str, Any], expected_token: str) -> None:
    if not expected_token:
        return

    actual = payload.get("token") or payload.get("header", {}).get("token")
    if actual != expected_token:
        raise ValueError("飞书事件 token 校验失败")


def extract_text_message(payload: dict[str, Any]) -> tuple[str, str]:
    event = payload.get("event", {})
    message = event.get("message", {})
    chat_id = message.get("chat_id", "")
    content = message.get("content", "{}")

    if isinstance(content, str):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            parsed = {"text": content}
    else:
        parsed = content

    text = str(parsed.get("text", "")).strip()
    return chat_id, text
