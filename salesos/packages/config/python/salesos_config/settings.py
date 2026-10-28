from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    project_name: str = Field(default="SalesOS", alias="PROJECT_NAME")
    environment: Literal["development", "test", "staging", "production"] = Field(
        default="development",
        alias="ENVIRONMENT",
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    api_base_url: str = Field(default="http://api:8000", alias="API_BASE_URL")
    api_request_timeout_seconds: float = Field(default=30.0, alias="API_REQUEST_TIMEOUT_SECONDS")
    telegram_bot_port: int = Field(default=8080, alias="TELEGRAM_BOT_PORT")
    telegram_bot_internal_url: str = Field(
        default="http://telegram-bot:8080",
        alias="TELEGRAM_BOT_INTERNAL_URL",
    )

    postgres_host: str = Field(default="postgres", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="salesos", alias="POSTGRES_DB")
    postgres_user: str = Field(default="salesos", alias="POSTGRES_USER")
    postgres_password: str = Field(default="salesos", alias="POSTGRES_PASSWORD")

    redis_url: str = Field(default="redis://redis:6379/0", alias="REDIS_URL")
    redis_operation_timeout_seconds: float = Field(default=5.0, alias="REDIS_OPERATION_TIMEOUT_SECONDS")
    redis_retry_attempts: int = Field(default=2, alias="REDIS_RETRY_ATTEMPTS")

    ollama_base_url: str = Field(default="http://host.docker.internal:11434", alias="OLLAMA_BASE_URL")
    ollama_classification_model: str = Field(
        default="phi3",
        alias="OLLAMA_CLASSIFICATION_MODEL",
    )
    ollama_secondary_classification_model: str = Field(
        default="phi3",
        alias="OLLAMA_SECONDARY_CLASSIFICATION_MODEL",
    )
    ollama_reasoning_model: str = Field(
        default="gemma2:2b",
        alias="OLLAMA_REASONING_MODEL",
    )
    ollama_personalization_model: str = Field(
        default="phi3",
        alias="OLLAMA_PERSONALIZATION_MODEL",
    )
    ollama_timeout_seconds: float = Field(default=45.0, alias="OLLAMA_TIMEOUT_SECONDS")
    ollama_retry_attempts: int = Field(default=2, alias="OLLAMA_RETRY_ATTEMPTS")
    ollama_keep_alive: str = Field(default="10m", alias="OLLAMA_KEEP_ALIVE")
    ollama_warmup_enabled: bool = Field(default=False, alias="OLLAMA_WARMUP_ENABLED")
    ollama_generation_timeout_seconds: float = Field(
        default=10.0,
        alias="OLLAMA_GENERATION_TIMEOUT_SECONDS",
    )

    apify_token: str = Field(default="", alias="APIFY_TOKEN")
    apify_google_maps_actor_id: str = Field(
        default="johnvc~google-maps-places-api",
        alias="APIFY_GOOGLE_MAPS_ACTOR_ID",
    )
    apify_timeout_seconds: float = Field(default=30.0, alias="APIFY_TIMEOUT_SECONDS")
    apify_retry_attempts: int = Field(default=2, alias="APIFY_RETRY_ATTEMPTS")

    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_use_webhooks: bool = Field(default=False, alias="TELEGRAM_USE_WEBHOOKS")
    telegram_allowed_user_ids: str = Field(default="", alias="TELEGRAM_ALLOWED_USER_IDS")
    telegram_alert_chat_ids: str = Field(default="", alias="TELEGRAM_ALERT_CHAT_IDS")
    telegram_base_url: str = Field(default="", alias="TELEGRAM_BASE_URL")
    internal_service_token: str = Field(default="local-dev-token", alias="INTERNAL_SERVICE_TOKEN")
    startup_strict_validation: bool = Field(default=False, alias="STARTUP_STRICT_VALIDATION")
    startup_grace_period_seconds: int = Field(default=45, alias="STARTUP_GRACE_PERIOD_SECONDS")
    startup_dependency_timeout_seconds: int = Field(default=60, alias="STARTUP_DEPENDENCY_TIMEOUT_SECONDS")
    startup_dependency_retry_attempts: int = Field(default=12, alias="STARTUP_DEPENDENCY_RETRY_ATTEMPTS")
    startup_dependency_poll_seconds: float = Field(default=2.0, alias="STARTUP_DEPENDENCY_POLL_SECONDS")
    default_scrape_query: str = Field(default="marketing agency", alias="DEFAULT_SCRAPE_QUERY")
    default_scrape_location: str = Field(default="Austin, TX", alias="DEFAULT_SCRAPE_LOCATION")
    default_scrape_max_results: int = Field(default=5, alias="DEFAULT_SCRAPE_MAX_RESULTS")
    default_timezone: str = Field(default="UTC", alias="DEFAULT_TIMEZONE")
    process_existing_leads: bool = Field(default=True, alias="PROCESS_EXISTING_LEADS")
    scrape_job_timeout_seconds: float = Field(default=120.0, alias="SCRAPE_JOB_TIMEOUT_SECONDS")
    scrape_job_stale_timeout_seconds: float = Field(default=150.0, alias="SCRAPE_JOB_STALE_TIMEOUT_SECONDS")
    pipeline_retry_attempts: int = Field(default=2, alias="PIPELINE_RETRY_ATTEMPTS")
    pipeline_retry_backoff_seconds: float = Field(default=0.35, alias="PIPELINE_RETRY_BACKOFF_SECONDS")
    outreach_cooldown_hours: int = Field(default=24, alias="OUTREACH_COOLDOWN_HOURS")
    follow_up_default_delay_hours: int = Field(default=72, alias="FOLLOW_UP_DEFAULT_DELAY_HOURS")
    follow_up_max_attempts: int = Field(default=3, alias="FOLLOW_UP_MAX_ATTEMPTS")
    review_signal_min_severity: int = Field(default=65, alias="REVIEW_SIGNAL_MIN_SEVERITY")
    review_signal_alert_threshold: int = Field(default=75, alias="REVIEW_SIGNAL_ALERT_THRESHOLD")
    review_signal_ai_refinement_enabled: bool = Field(
        default=True,
        alias="REVIEW_SIGNAL_AI_REFINEMENT_ENABLED",
    )
    dev_force_outreach_regeneration: bool = Field(
        default=False,
        alias="SALESOS_DEV_FORCE_OUTREACH",
        description="Development-only: bypass outreach cooldown for testing. Disabled by default.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @computed_field
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field
    @property
    def sync_database_url(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def telegram_allowed_users(self) -> set[int]:
        return self._parse_int_set(self.telegram_allowed_user_ids)

    @property
    def telegram_alert_chats(self) -> set[int]:
        return self._parse_int_set(self.telegram_alert_chat_ids)

    @staticmethod
    def _parse_int_set(value: str) -> set[int]:
        if not value.strip():
            return set()
        return {int(item.strip()) for item in value.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    return Settings()
