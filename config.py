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

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
