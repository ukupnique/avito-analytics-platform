from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Avito Analytics Platform"
    app_env: str = "local"
    debug: bool = True
    project_version: str = "0.1.0"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "avito_analytics"
    postgres_user: str = "app"
    postgres_password: str = "app123"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()