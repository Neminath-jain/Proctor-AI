from typing import List, Union
from pydantic import AnyHttpUrl, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # General
    ENVIRONMENT: str = "development"
    PROJECT_NAME: str = "Online Exam Proctoring Platform"
    API_V1_STR: str = "/api/v1"

    # PostgreSQL Configuration
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres_password"
    POSTGRES_DB: str = "exam_proctoring_db"
    POSTGRES_HOST: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432

    # Override URLs if explicitly passed
    DATABASE_URL: str = ""
    DATABASE_SYNC_URL: str = ""

    @computed_field  # type: ignore[misc]
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[misc]
    @property
    def SYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_SYNC_URL:
            return self.DATABASE_SYNC_URL
        return (
            f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis Configuration
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_URL: str = "redis://127.0.0.1:6379/0"

    # JWT Security
    SECRET_KEY: str = "exam_proctoring_dev_secret_key_at_least_32_characters_long_super_secure"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]

    # External Services
    ML_SERVICE_URL: str = "http://127.0.0.1:8001"
    JUDGE0_API_URL: str = "http://127.0.0.1:2358"

    # Spending & Usage Safety Caps (Item 20)
    DAILY_JUDGE0_EXECUTION_CAP: int = 2000
    HOURLY_CANDIDATE_RUN_CODE_CAP: int = 50
    DAILY_EVIDENCE_STORAGE_MB_CAP: int = 5000

    # Phase 8: Comprehensive Rate Limiting Configuration
    RATE_LIMIT_LOGIN_PER_IP_MAX: int = 30
    RATE_LIMIT_LOGIN_PER_IP_WINDOW_SECONDS: float = 60.0
    RATE_LIMIT_LOGIN_MAX_FAILED_BEFORE_BACKOFF: int = 5
    RATE_LIMIT_LOGIN_BACKOFF_BASE_SECONDS: float = 5.0
    RATE_LIMIT_LOGIN_BACKOFF_FACTOR: float = 2.0
    RATE_LIMIT_LOGIN_BACKOFF_MAX_SECONDS: float = 60.0

    RATE_LIMIT_SIGNUP_PER_IP_MAX: int = 15
    RATE_LIMIT_SIGNUP_PER_IP_WINDOW_SECONDS: float = 3600.0

    RATE_LIMIT_AUTH_REFRESH_PER_IP_MAX: int = 60
    RATE_LIMIT_AUTH_REFRESH_WINDOW_SECONDS: float = 60.0

    RATE_LIMIT_PASSWORD_RESET_MAX: int = 5
    RATE_LIMIT_PASSWORD_RESET_WINDOW_SECONDS: float = 3600.0

    RATE_LIMIT_PUBLIC_MAX_REQUESTS: int = 120
    RATE_LIMIT_PUBLIC_WINDOW_SECONDS: float = 60.0

    RATE_LIMIT_AUTHENTICATED_MAX_REQUESTS: int = 300
    RATE_LIMIT_AUTHENTICATED_WINDOW_SECONDS: float = 60.0

    RATE_LIMIT_CODE_EXECUTION_MIN_INTERVAL: float = 5.0
    RATE_LIMIT_VIOLATION_LOG_MAX_REQUESTS: int = 15
    RATE_LIMIT_VIOLATION_LOG_WINDOW_SECONDS: float = 10.0

    # Error Tracking & Telemetry (Item 21)
    SENTRY_DSN: str = ""


settings = Settings()

