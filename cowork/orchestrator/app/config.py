from pydantic_settings import BaseSettings


class OrchestratorSettings(BaseSettings):
    app_env: str = "development"
    log_level: str = "info"
    host: str = "0.0.0.0"
    port: int = 5001
    core_api_url: str = "http://localhost:3001"


settings = OrchestratorSettings()
