import json
import warnings
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_verification_token: str = ""
    feishu_encrypt_key: str = ""
    amap_web_key: str = ""
    amap_js_key: str = ""
    public_base_url: str = "http://localhost:8000"
    map_output_dir: str = "static/maps"
    api_key: str = ""  # 默认空，未配置时不强制鉴权（兼容本地开发）
    deepseek_api_key: str = ""
    feishu_app_tokens: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    def get_app_tokens(self) -> list[dict]:
        """Parse feishu_app_tokens JSON string into a list of dicts.

        Expected format: [{"app_token": "bascnxxx", "name": "深圳门店"}, ...]
        Returns empty list if feishu_app_tokens is empty or invalid JSON.
        """
        if not self.feishu_app_tokens:
            return []
        try:
            tokens = json.loads(self.feishu_app_tokens)
            if isinstance(tokens, list):
                return tokens
            warnings.warn("feishu_app_tokens is not a JSON array, ignoring.")
            return []
        except json.JSONDecodeError:
            warnings.warn("feishu_app_tokens is not valid JSON, ignoring.")
            return []


@lru_cache
def get_settings() -> Settings:
    return Settings()
