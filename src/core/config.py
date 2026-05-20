from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    # API Keys
    GROQ_API_KEY: str
    HF_TOKEN: str
    HF_HUB_OFFLINE: bool
    VERITAS_API_KEYS: str
    VERITAS_ADMIN_KEY: str

    # Models
    DEFAULT_MODEL: str = "llama-3.3-70b-versatile"
    ACTOR_MODEL: str = "llama-3.3-70b-versatile"
    CRITIC_MODEL: str = "qwen-qwq-32b" 

    # Rate Limits
    REQUESTS_PER_MINUTE: int = Field(default=60, ge=1)

    # App Config
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


settings = Settings()