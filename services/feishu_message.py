import json

import requests

from app.tools.feishu_tool import FeishuClient


class FeishuMessenger:
    def __init__(self, client: FeishuClient):
        self.client = client

    def send_text(self, receive_id: str, text: str, receive_id_type: str = "chat_id") -> None:
        token = self.client.tenant_access_token()
        response = requests.post(
            "https://open.feishu.cn/open-apis/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "receive_id": receive_id,
                "msg_type": "text",
                "content": json.dumps({"text": text}, ensure_ascii=False),
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"发送飞书消息失败: {payload.get('msg', payload)}")
