from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    max_file_size_mb: int = 10

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
