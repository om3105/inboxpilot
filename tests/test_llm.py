"""
tests/test_llm.py — Provider fallback chain: Gemini -> NVIDIA -> heuristic.
"""

import pytest

import app.llm as llm_module
from app.config import Settings
from app.llm import LLMProvider
from app.models import DocumentType, ExtractedEmail

TEXT = "From: aarav.sharma@acme.dev\nSubject: Leave\n\nCasual leave 2024-11-04 to 2024-11-05. EMP001."


class _FakeModel:
    def __init__(self, behaviour):
        self.behaviour = behaviour

    def with_structured_output(self, schema):
        return self

    async def ainvoke(self, prompt):
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        return self.behaviour


@pytest.fixture
def provider(monkeypatch):
    settings = Settings(gemini_api_key="AIza-real", nvidia_api_key="nvapi-real", llm_providers="gemini,nvidia")
    monkeypatch.setattr(llm_module, "get_settings", lambda: settings)
    monkeypatch.setattr(llm_module, "_cooldown_until", {})
    monkeypatch.setattr(llm_module, "PROVIDER_COUNTS", {})
    monkeypatch.setattr(llm_module, "FALLBACK_COUNTS", {"extract": 0, "draft": 0})
    return LLMProvider()


def _install(monkeypatch, behaviours: dict, calls: list):
    def fake_chat_model(self, provider, temperature):
        calls.append(provider)
        return _FakeModel(behaviours[provider])
    monkeypatch.setattr(LLMProvider, "_chat_model", fake_chat_model)


nvidia_result = ExtractedEmail(document_type=DocumentType.LEAVE_REQUEST, employee_id="EMP001", leave_type="casual")


def test_chain_skips_providers_without_keys(monkeypatch):
    monkeypatch.setattr(llm_module, "get_settings", lambda: Settings(gemini_api_key="", nvidia_api_key="nvapi-real"))
    p = LLMProvider()
    assert p.providers == ["nvidia"]
    assert p.model_name == "nvidia:nvidia/nemotron-3-ultra-550b-a55b"


@pytest.mark.asyncio
async def test_gemini_success_does_not_call_nvidia(provider, monkeypatch):
    calls = []
    gemini_result = ExtractedEmail(document_type=DocumentType.INVOICE, invoice_number="INV-2024-001")
    _install(monkeypatch, {"gemini": gemini_result, "nvidia": nvidia_result}, calls)

    result = await provider.extract_structured(TEXT)
    assert result.invoice_number == "INV-2024-001"
    assert calls == ["gemini"]
    assert provider.last_provider == "gemini"


@pytest.mark.asyncio
async def test_gemini_failure_falls_back_to_nvidia(provider, monkeypatch):
    calls = []
    _install(monkeypatch, {"gemini": RuntimeError("503 UNAVAILABLE"), "nvidia": nvidia_result}, calls)

    result = await provider.extract_structured(TEXT)
    assert result.employee_id == "EMP001"
    assert calls == ["gemini", "nvidia"]
    assert llm_module.PROVIDER_COUNTS == {"nvidia": 1}
    assert llm_module.FALLBACK_COUNTS["extract"] == 0


@pytest.mark.asyncio
async def test_rate_limited_gemini_is_skipped_on_next_call(provider, monkeypatch):
    calls = []
    quota = RuntimeError("429 RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel-FreeTier")
    _install(monkeypatch, {"gemini": quota, "nvidia": nvidia_result}, calls)

    await provider.extract_structured(TEXT)
    await provider.extract_structured(TEXT)
    assert calls == ["gemini", "nvidia", "nvidia"]


@pytest.mark.asyncio
async def test_all_providers_failing_uses_heuristic(provider, monkeypatch):
    calls = []
    _install(monkeypatch, {"gemini": RuntimeError("503"), "nvidia": RuntimeError("500")}, calls)

    result = await provider.extract_structured(TEXT)
    assert result.employee_id == "EMP001"  # heuristic extractor still parses the ID
    assert calls == ["gemini", "nvidia"]
    assert llm_module.FALLBACK_COUNTS["extract"] == 1
