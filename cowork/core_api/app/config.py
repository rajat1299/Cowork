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
    snapshot_dir: str = "storage/snapshots"
    share_token_minutes: int = 1440
    rate_limit_auth_per_minute: int = 20
    rate_limit_proxy_per_minute: int = 30
    rate_limit_oauth_per_minute: int = 20


settings = CoreApiSettings()
