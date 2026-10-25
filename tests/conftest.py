import os

import pytest
from tools.lookup_record import reset_mock_store

# Env vars take precedence over .env in pydantic-settings; keep tests offline,
# deterministic, and from exporting traces to the real Langfuse project.
os.environ["GEMINI_API_KEY"] = ""
os.environ["LANGFUSE_PUBLIC_KEY"] = ""
os.environ["LANGFUSE_SECRET_KEY"] = ""
os.environ["DEMO_TOKEN"] = "test-demo-token"
os.environ["CORS_ORIGINS"] = "https://allowed.example"


@pytest.fixture(autouse=True)
def _fresh_mock_store():
    """Isolate tests from mutations applied to the shared in-memory store."""
    reset_mock_store()
    yield
    reset_mock_store()
