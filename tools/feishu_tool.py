from typing import Any

import requests


class FeishuClient:
    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret

    def tenant_access_token(self) -> str:
        response = requests.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("tenant_access_token")
        if not token:
            raise RuntimeError(f"获取飞书 tenant_access_token 失败: {payload.get('msg', payload)}")
        return token

    def read_bitable_records(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        token = self.tenant_access_token()
        items: list[dict[str, Any]] = []
        page_token = ""

        while True:
            body: dict[str, Any] = {"page_size": 500}
            if page_token:
                body["page_token"] = page_token

            response = requests.post(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records/search",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=30,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code", 0) != 0:
                raise RuntimeError(f"读取飞书多维表格失败: {payload.get('msg', payload)}")

            data = payload.get("data", {})
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")

        return [_record_to_location(item) for item in items]


def _record_to_location(record: dict[str, Any]) -> dict[str, str]:
    fields = record.get("fields", {})
    return {
        "name": _field_text(fields.get("名称")) or _field_text(fields.get("name")) or "未命名",
        "address": _field_text(fields.get("地址")) or _field_text(fields.get("address")) or "",
    }


def _field_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("name") or ""))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("name") or "").strip()
    return str(value).strip()
