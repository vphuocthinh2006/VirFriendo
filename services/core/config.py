from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRET_SUBSTR = ("change-me", "changeme", "secret", "password", "test", "demo")


class Settings(BaseSettings):
    PROJECT_NAME: str = "VirFriendo"
    VERSION: str = "0.1.0"
    # development | staging | production — production enforces stronger SECRET_KEY
    APP_ENV: str = "development"
    DEBUG: bool = False
    DATABASE_URL: str  # .env — localhost for host uvicorn; host.docker.internal for docker run; database@5432 in compose

    # Security
    SECRET_KEY: str  # Required: generate with `openssl rand -hex 32`
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080

    # Comma-separated origins — never use * with credentials in browser.
    # Dev default: Vite. Production: e.g. https://virfriendo.win,https://www.virfriendo.win
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:8081,http://127.0.0.1:8081"
    )

    # production: comma-separated hostnames (no scheme). Empty = middleware skipped.
    TRUSTED_HOSTS: str = ""

    # Groq API Key for LLM inference
    GROQ_API_KEY: str | None = None

    # Optional: Quickstart personality buffer + summary (chat entry mode)
    REDIS_URL: str | None = None

    # Optional: Chroma HTTP API (retrieval / future RAG). Compose: http://chromadb:8000
    CHROMA_SERVER_URL: str | None = None
    CHROMA_GALLERY_COLLECTION: str = "character_gallery_vit"

    # --- Local ML (NLP multitask BERT + ViT gallery) — optional, lazy-loaded ---
    ENABLE_NLP_METADATA: bool = False
    NLP_MODEL_PATH: str | None = None
    NLP_LABEL_PATH: str | None = None
    NLP_BERT_NAME: str = "bert-base-uncased"
    NLP_ACT_LABEL_ID_OFFSET: int = 1
    NLP_EMOTION_MIN_PROB: float = 0.55
    NLP_EMOTION_MIN_MARGIN: float = 0.08
    NLP_EMOTION_LOW_PROB: float = 0.35
    NLP_CONFIDENCE_GRAY_LOW: float = 0.4
    NLP_CONFIDENCE_GRAY_HIGH: float = 0.7
    NLP_ACT_MIN_PROB: float = 0.55
    NLP_ACT_MIN_MARGIN: float = 0.06

    ENABLE_LLM_DOUBLE_CHECK: bool = False
    DOUBLE_CHECK_MODEL: str = "llama-3.1-8b-instant"
    DOUBLE_CHECK_MAX_TOKENS: int = 64

    ML_DEVICE: str = "cpu"

    ENABLE_VIT_GALLERY: bool = False
    VIT_MODEL_PATH: str | None = None
    VIT_TIMM_MODEL: str = "vit_base_patch16_224"
    VIT_NUM_CLASSES: int = 45
    GALLERY_EMBEDDINGS_NPY_PATH: str | None = None
    GALLERY_CLASS_NAMES_PKL_PATH: str | None = None
    GALLERY_VECTOR_BACKEND: str = "numpy"
    VIT_MIN_SIMILARITY: float = 0.35
    VIT_MIN_MARGIN_SIM: float = 0.03

    # Optional: external agent-service endpoint (microservice mode)
    AGENT_SERVICE_URL: str | None = None

    # Optional: media-service endpoint (microservice mode)
    MEDIA_SERVICE_URL: str | None = None

    # Optional: knowledge-service endpoint (youtube/web analysis)
    KNOWLEDGE_SERVICE_URL: str | None = None

    # Optional: S3 for user media uploads + generated images (boto3 uses AWS_ACCESS_KEY_ID etc.)
    S3_MEDIA_BUCKET: str | None = None
    S3_MEDIA_PREFIX: str = "virfriendo"
    S3_GET_PRESIGNED_SECONDS: int = 604800  # 7 days
    AWS_REGION: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    def trusted_host_list(self) -> list[str]:
        return [h.strip() for h in self.TRUSTED_HOSTS.split(",") if h.strip()]

    @model_validator(mode="after")
    def _enforce_production_secrets(self) -> Settings:
        if (self.APP_ENV or "").lower() != "production":
            return self
        sk = (self.SECRET_KEY or "").strip()
        if len(sk) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters when APP_ENV=production")
        low = sk.lower()
        if any(s in low for s in _WEAK_SECRET_SUBSTR):
            raise ValueError("SECRET_KEY must not contain placeholder words when APP_ENV=production")
        return self


settings = Settings()
