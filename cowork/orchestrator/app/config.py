from pydantic import field_validator
from pydantic_settings import BaseSettings


class OrchestratorSettings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 5001
    core_api_url: str = "http://localhost:3001"
    core_api_internal_key: str = ""
    rate_limit_chat_per_minute: int = 30

    @field_validator("core_api_internal_key")
    @classmethod
    def validate_core_api_internal_key(cls, value: str, info):
        app_env = info.data.get("app_env")
        if app_env == "production" and not value:
            raise ValueError("CORE_API_INTERNAL_KEY is required in production")
        return value


settings = OrchestratorSettings()
