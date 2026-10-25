import pytest
from tools.lookup_record import reset_mock_store


@pytest.fixture(autouse=True)
def _fresh_mock_store():
    """Isolate tests from mutations applied to the shared in-memory store."""
    reset_mock_store()
    yield
    reset_mock_store()
