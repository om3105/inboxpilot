"""
Centralised configuration loaded from environment variables.

Design decisions:
- pydantic-settings validates types and presence at startup, so we fail fast
  if a required secret is missing rather than crashing mid-request.
- All config lives here — no scattered os.getenv() calls.
- The LLM model name is configurable so we can swap Gemini <-> OpenAI by
  changing one env var, not code.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings sourced exclusively from environment variables."""

    # ── LLM ───────────────────────────────────────────────────
    gemini_api_key: str = Field(
        default="", description="Google Gemini API key"
    )
    llm_model_name: str = Field(
        default="gemini-3.5-flash",
        description="Model identifier passed to the LLM provider",
    )
    llm_max_rpm: int = Field(
        default=0,
        description="Max live LLM requests per minute (0 = unlimited; free tier is 5)",
    )
    llm_live_drafts: bool = Field(
        default=True,
        description="Use the LLM for draft replies; false uses templates and halves LLM calls",
    )

    # ── MongoDB ───────────────────────────────────────────────
    mongodb_uri: str = Field(
        default="", description="MongoDB Atlas connection string"
    )
    mongodb_db_name: str = Field(
        default="inboxpilot",
        description="Database name for business data and checkpoints",
    )

    # ── Langfuse ──────────────────────────────────────────────
    langfuse_public_key: str = Field(default="", description="Langfuse public key")
    langfuse_secret_key: str = Field(default="", description="Langfuse secret key")
    langfuse_host: str = Field(
        default="https://cloud.langfuse.com",
        description="Langfuse server URL",
    )

    # ── API Security ──────────────────────────────────────────
    demo_token: str = Field(
        default="",
        description="Token required in X-Demo-Token for agent endpoints; empty disables them",
    )
    cors_origins: str = Field(
        default="",
        description="Comma-separated origins allowed to call the API cross-origin",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ── Server ────────────────────────────────────────────────
    port: int = Field(default=8000, description="HTTP port (set by Render)")

    model_config = {
        # pydantic-settings reads from a .env file in local dev;
        # on Render these come from the dashboard's env-var config.
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache
def get_settings() -> Settings:
    """Factory cached at module level.  Import this, not the class directly."""
    return Settings()  # type: ignore[call-arg]
