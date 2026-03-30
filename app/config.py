from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    max_file_size_mb: int = 10

    # Primary LLM provider. "auto" selects the first provider with a valid API key.
    # Valid values: auto, openai, anthropic, google, xai
    llm_primary_provider: str = "auto"

    # Model names — override via env vars (e.g. GEMINI_MODEL=gemini-2.5-flash)
    openai_model: str = "gpt-4o"
    anthropic_model: str = "claude-sonnet-4-20250514"
    gemini_model: str = "gemini-2.0-flash"
    xai_model: str = "grok-3"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
