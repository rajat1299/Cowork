from pydantic import field_validator
from pydantic_settings import BaseSettings


class CoreApiSettings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 3001
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cowork"
    auto_create_tables: bool = False
    internal_api_key: str = ""
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 14
    app_callback_scheme: str = "cowork"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_scope: str = "openid email profile"
    github_client_id: str = ""
    github_client_secret: str = ""
    github_scope: str = "read:user user:email"
    exa_api_key: str = ""
    data_encryption_key: str = ""
    snapshot_dir: str = "storage/snapshots"
    share_token_minutes: int = 1440
    rate_limit_auth_per_minute: int = 20
    rate_limit_proxy_per_minute: int = 30
    rate_limit_oauth_per_minute: int = 20

    @field_validator("auto_create_tables")
    @classmethod
    def validate_auto_create_tables(cls, value: bool, info):
        app_env = info.data.get("app_env")
        if app_env == "production" and value:
            raise ValueError("auto_create_tables must be false in production")
        return value

    @field_validator("internal_api_key")
    @classmethod
    def validate_internal_api_key(cls, value: str, info):
        app_env = info.data.get("app_env")
        if app_env == "production" and not value:
            raise ValueError("INTERNAL_API_KEY is required in production")
        return value

    @field_validator("data_encryption_key")
    @classmethod
    def validate_data_encryption_key(cls, value: str, info):
        app_env = info.data.get("app_env")
        if app_env == "production" and not value:
            raise ValueError("DATA_ENCRYPTION_KEY is required in production")
        return value


settings = CoreApiSettings()
