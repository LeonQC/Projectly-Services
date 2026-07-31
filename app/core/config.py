from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Projectly API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://projectly:projectly@localhost:5432/projectly"
    auth_secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24
    password_hash_iterations: int = 210_000

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
