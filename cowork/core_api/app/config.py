from pydantic_settings import BaseSettings


class CoreApiSettings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 3001
    database_url: str = "postgresql://postgres:postgres@localhost:5432/cowork"


settings = CoreApiSettings()
