"""Application configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import PostgresDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: str = "development"
    app_debug: bool = True
    database_url: PostgresDsn
    redis_url: str = "redis://localhost:6379"
    email_provider: str = "stub"
    resend_api_key: SecretStr | None = None
    email_from: str = "onboarding@resend.dev"
    email_redirect_enabled: bool = True
    email_redirect_to: str | None = None
    twilio_account_sid: SecretStr | None = None
    twilio_auth_token: SecretStr | None = None
    twilio_phone_number: str | None = None
    twilio_default_to: str | None = None
    twilio_inbound_webhook_url: str | None = None
    auth_disabled: bool = True
    auth0_domain: str | None = None
    auth0_audience: str | None = None
    auth0_claims_namespace: str = "https://acufycrm"
    use_swarm_graph: bool = False

    llm_provider: str = "groq"
    llm_model: str = "llama-3.1-8b-instant"
    fallback_provider: str | None = None
    fallback_model: str | None = None
    groq_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    gemini_api_key: SecretStr | None = None
    ollama_base_url: str = "http://127.0.0.1:11434"
    langfuse_secret_key: SecretStr | None = None
    langfuse_public_key: SecretStr | None = None
    langfuse_base_url: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings instance."""
    return Settings()
