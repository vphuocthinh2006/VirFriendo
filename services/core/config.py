from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Anime Companion"
    VERSION: str = "0.1.0"
    DEBUG: bool = False
    DATABASE_URL: str  # Required: set in .env e.g. postgresql+asyncpg://user:pass@localhost:5432/anime_companion
    
    # Security
    SECRET_KEY: str  # Required: generate with `openssl rand -hex 32`
    ALGORITHM: str = "HS256"
    # Longer default so refresh / WebSocket stay valid during a session (override in .env)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    # Groq API Key for LLM inference
    GROQ_API_KEY: str | None = None

    # Optional: Quickstart personality buffer + summary (chat entry mode)
    REDIS_URL: str | None = None
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
