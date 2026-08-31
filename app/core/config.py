from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Projectly API"
    environment: str = "development"
    api_prefix: str = "/api"
    database_url: str = "postgresql+psycopg://projectly:projectly@localhost:5432/projectly"
    auth_secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 120
    password_hash_iterations: int = 210_000
    google_client_id: str = ""
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    frontend_url: str = "http://localhost:5173"
    kafka_bootstrap_servers: str = "localhost:9092"
    search_events_topic: str = "projectly.search.events"
    elasticsearch_url: str = "http://localhost:9200"
    github_app_webhook_secret: str = ""
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_storage_bucket: str = "projectly-attachments"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @property
    def cors_origin_list(self) -> list[str]:
        origins = []
        for origin in self.cors_origins.split(","):
            normalized_origin = origin.strip().rstrip("/")
            if not normalized_origin:
                continue
            origins.append(normalized_origin)
            origins.append(f"{normalized_origin}/")
        return list(dict.fromkeys(origins))

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


settings = Settings()
