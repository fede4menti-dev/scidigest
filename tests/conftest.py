import pytest


@pytest.fixture(autouse=True)
def _offline_defaults(monkeypatch):
    """Tests never reach the real API: normal requests by default (batch tests opt in)."""
    monkeypatch.setenv("SCIDIGEST_BATCH", "0")
