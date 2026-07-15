import re
from dataclasses import dataclass


@dataclass(frozen=True)
class MapCommand:
    app_token: str
    table_id: str


def parse_map_command(text: str) -> MapCommand:
    app_token = _extract_token(text, "app_token")
    table_id = _extract_token(text, "table_id")
    return MapCommand(app_token=app_token, table_id=table_id)


def _extract_token(text: str, key: str) -> str:
    match = re.search(rf"(?:^|\s){key}=([A-Za-z0-9_\-]+)", text)
    if not match:
        raise ValueError(f"消息里缺少 {key}=xxx")
    return match.group(1)
