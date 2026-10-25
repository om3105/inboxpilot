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
    monkeypatch.setattr(llm_module, "_ATTEMPTS_PER_PROVIDER", 2)
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

    result = await provider.extract_structured("Please pay invoice INV-2024-001 for ₹4,500.")
    assert result.invoice_number == "INV-2024-001"
    assert calls == ["gemini"]
    assert provider.last_provider == "gemini"


@pytest.mark.asyncio
async def test_gemini_failure_falls_back_to_nvidia(provider, monkeypatch):
    calls = []
    _install(monkeypatch, {"gemini": RuntimeError("503 UNAVAILABLE"), "nvidia": nvidia_result}, calls)

    result = await provider.extract_structured(TEXT)
    assert result.employee_id == "EMP001"
    assert calls == ["gemini", "gemini", "nvidia"]  # transient error retried once first
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
    assert calls == ["gemini", "gemini", "nvidia", "nvidia"]
    assert llm_module.FALLBACK_COUNTS["extract"] == 1


@pytest.mark.asyncio
async def test_hallucinated_identifier_is_discarded(provider, monkeypatch):
    calls = []
    invented = ExtractedEmail(document_type=DocumentType.LEAVE_REQUEST, employee_id="EMP-4567")
    _install(monkeypatch, {"gemini": invented, "nvidia": nvidia_result}, calls)

    result = await provider.extract_structured("Need time off next month.")
    assert result.document_type == DocumentType.LEAVE_REQUEST
    assert result.employee_id is None


@pytest.mark.asyncio
async def test_transient_error_is_retried_on_same_provider(provider, monkeypatch):
    outcomes = iter([RuntimeError("[400] unknown field guided_json"), nvidia_result])

    class _Flaky(_FakeModel):
        async def ainvoke(self, prompt):
            r = next(outcomes)
            if isinstance(r, Exception):
                raise r
            return r

    monkeypatch.setattr(llm_module, "get_settings", lambda: Settings(nvidia_api_key="nvapi-real", llm_providers="nvidia"))
    monkeypatch.setattr(LLMProvider, "_chat_model", lambda self, p, t: _Flaky(None))
    result = await LLMProvider().extract_structured(TEXT)
    assert result.employee_id == "EMP001"
    assert llm_module.FALLBACK_COUNTS["extract"] == 0


def test_draft_html_is_converted_to_plain_text():
    from app.llm import _to_plain_text
    assert _to_plain_text("Dear Aarav,<br><br>Approved.<br/>Regards,<p>Ops</p>") == "Dear Aarav,\n\nApproved.\nRegards,\n\nOps"
    assert _to_plain_text("No tags here.") == "No tags here."


@pytest.mark.asyncio
async def test_draft_uses_plain_text_and_template_headers(provider, monkeypatch):
    from langchain_core.messages import AIMessage

    class _TextModel:
        def with_structured_output(self, schema):
            raise AssertionError("drafts must not use structured output")

        async def ainvoke(self, prompt):
            return AIMessage(content="Subject: Re: Leave\n\nDear Aarav,\n\nYour **EMP001** request is queued.\n\nInboxPilot Operations")

    monkeypatch.setattr(LLMProvider, "_chat_model", lambda self, p, t: _TextModel())
    ctx = {"document_type": "leave_request", "extracted": {"sender": "aarav.sharma@acme.dev", "employee_name": "Aarav Sharma"}}
    draft = await provider.generate_draft(ctx)
    assert draft.to == "aarav.sharma@acme.dev"
    assert draft.subject == "Re: Leave Request - Aarav Sharma"
    assert draft.body == "Dear Aarav,\n\nYour EMP001 request is queued.\n\nInboxPilot Operations"
    assert llm_module.FALLBACK_COUNTS["draft"] == 0
