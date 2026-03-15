from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "agent-service"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8001
    DEBUG: bool = True

    GROQ_API_KEY: str
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    INTENT_MODEL_DIR: str = "services/agent-service/models/intent"
    INTENT_BASE_MODEL: str | None = None
    ENABLE_INTENT_MODEL_RUNTIME: bool = False
    ENABLE_INTENT_KEYWORD_FALLBACK: bool = True
    ENABLE_EMOTION_KEYWORD_FALLBACK: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        case_sensitive=False,
    )


settings = Settings()