from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    max_file_size_mb: int = 10
    llm_primary_provider: str = "openai"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
