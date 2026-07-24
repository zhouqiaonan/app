import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


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
        logger.info(f"read_bitable_records")
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

        # Auto-detect field mapping
        try:
            table_fields = self.get_table_fields(app_token, table_id)
            logger.info(f"table_fields: {table_fields}")
            name_field, addr_field = _detect_field_mapping(table_fields)
            logger.info(f"name_field: {name_field}, addr_field: {addr_field}")
        except Exception:
            name_field, addr_field = None, None

        # TODO: 临时限制，后续移除
        # return [_record_to_location(item, name_field, addr_field) for item in items[:8]]
        return [_record_to_location(item, name_field, addr_field) for item in items]

    def list_tables(self, app_token: str) -> list[dict[str, Any]]:
        token = self.tenant_access_token()
        items: list[dict[str, Any]] = []
        page_token = ""

        while True:
            params: dict[str, Any] = {"page_size": 500}
            if page_token:
                params["page_token"] = page_token

            response = requests.get(
                f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                params=params,
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            if payload.get("code", 0) != 0:
                raise RuntimeError(f"获取飞书多维表格列表失败: {payload.get('msg', payload)}")

            data = payload.get("data", {})
            items.extend(data.get("items", []))
            if not data.get("has_more"):
                break
            page_token = data.get("page_token", "")

        return items

    def get_table_fields(self, app_token: str, table_id: str) -> list[dict[str, Any]]:
        """Get field metadata for a table."""
        token = self.tenant_access_token()
        response = requests.get(
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code", 0) != 0:
            raise RuntimeError(f"获取表格字段列表失败: {payload.get('msg', payload)}")
        return payload.get("data", {}).get("items", [])


def _detect_field_mapping(fields: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Auto-detect name and address fields from table field metadata.

    Returns (name_field_name, address_field_name) — the field_names to use as record keys.
    Returns None if a field cannot be determined.
    """
    NAME_KEYWORDS = ["名称", "名字", "name", "title", "标题", "姓名", "地点", "位置名", "位置名称", "地名", "供应商"]
    ADDRESS_KEYWORDS = ["地址", "address", "位置", "location", "所在地", "详细地址", "工厂地址", "门店地址"]

    name_field_name = None
    address_field_name = None

    for field in fields:
        field_name = field.get("field_name", "")
        lower_name = field_name.lower()

        if name_field_name is None:
            for kw in NAME_KEYWORDS:
                if kw.lower() in lower_name:
                    name_field_name = field_name
                    break

        if address_field_name is None:
            for kw in ADDRESS_KEYWORDS:
                if kw.lower() in lower_name:
                    address_field_name = field_name
                    break

    return name_field_name, address_field_name


def _record_to_location(
    record: dict[str, Any],
    name_field: str | None = None,
    address_field: str | None = None,
) -> dict[str, str]:
    """Convert a Bitable record to {name, address} dict using dynamic field mapping.

    Falls back to hardcoded field names if field names are not provided or not found.
    """
    fields = record.get("fields", {})

    name = "未命名"
    address = ""

    # Try dynamic field mapping first
    if name_field and name_field in fields:
        name = _field_text(fields[name_field]) or "未命名"
    if address_field and address_field in fields:
        address = _field_text(fields[address_field]) or ""

    # Fallback to hardcoded field names
    if name == "未命名":
        name = _field_text(fields.get("名称")) or _field_text(fields.get("name")) or "未命名"
    if not address:
        address = _field_text(fields.get("地址")) or _field_text(fields.get("address")) or ""

    return {"name": name, "address": address}


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
