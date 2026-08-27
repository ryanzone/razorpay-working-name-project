from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Variable declarations ONLY (No default secret strings in code!)
    GEMINI_API_KEY: str
    POLICY_HMAC_SECRET: str = "super-secret-hmac-key" # default for dev
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    
    # Storage URLs (Defaults for local dev)
    # DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel_audit"
    # REDIS_URL: str = "redis://localhost:6379"

    # Tells Pydantic to read variables automatically from .env
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()