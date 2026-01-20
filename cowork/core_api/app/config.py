from pydantic_settings import BaseSettings


class CoreApiSettings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 3001
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cowork"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    refresh_token_days: int = 14


settings = CoreApiSettings()
