"""
---
name: test_llm_fallback
description: "Tests for LLM service chain resolution and fallback execution"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-fallback
spec_doc: null
test_file: tests/stage1/test_llm_fallback.py
functions:
  - name: test_returns_profile_from_env_vars
    line: 239
    purpose: "Verifies build_environment_fallback reads all LLM_FALLBACK_* env vars and returns a populated RuntimeProfile"
    fixtures: [monkeypatch]
  - name: test_returns_none_when_disabled
    line: 264
    purpose: "Verifies build_environment_fallback returns None when LLM_FALLBACK_ENABLED=false"
    fixtures: [monkeypatch]
  - name: test_returns_none_when_incomplete_missing_api_key
    line: 272
    purpose: "Verifies build_environment_fallback returns None if API key is absent and no MINIMAX fallback"
    fixtures: [monkeypatch]
  - name: test_returns_none_when_incomplete_missing_base_url
    line: 281
    purpose: "Verifies build_environment_fallback returns None if base URL is absent"
    fixtures: [monkeypatch]
  - name: test_returns_none_when_incomplete_missing_model
    line: 290
    purpose: "Verifies build_environment_fallback returns None if model name is absent"
    fixtures: [monkeypatch]
  - name: test_falls_back_to_minimax_api_key
    line: 299
    purpose: "Verifies MINIMAX_API_KEY triggers a legacy minimax-fallback profile when primary vars absent"
    fixtures: [monkeypatch]
  - name: test_primary_env_takes_precedence_over_minimax
    line: 316
    purpose: "Verifies primary LLM_FALLBACK_* vars take precedence over MINIMAX_API_KEY"
    fixtures: [monkeypatch]
  - name: test_defaults_when_optional_vars_absent
    line: 329
    purpose: "Verifies optional env vars use safe defaults when absent"
    fixtures: [monkeypatch]
  - name: test_succeeds_on_first_provider
    line: 356
    purpose: "Verifies execute_with_fallback returns a successful result when first provider succeeds"
    fixtures: []
  - name: test_falls_back_on_timeout
    line: 373
    purpose: "Verifies execute_with_fallback falls back to next provider on timeout ProviderError"
    fixtures: []
  - name: test_falls_back_on_429
    line: 399
    purpose: "Verifies execute_with_fallback falls back when p1 raises a rate-limit (429) ProviderError"
    fixtures: []
  - name: test_falls_back_on_5xx
    line: 424
    purpose: "Verifies execute_with_fallback falls back when p1 raises a server error (500)"
    fixtures: []
  - name: test_stops_on_400_stop_disposition
    line: 448
    purpose: "Verifies execute_with_fallback stops chain on STOP disposition without trying next provider"
    fixtures: []
  - name: test_stops_on_vault_stop
    line: 473
    purpose: "Verifies execute_with_fallback raises NoProviderAvailableError immediately on VAULT_STOP disposition"
    fixtures: []
  - name: test_credential_fallback_marks_and_continues
    line: 495
    purpose: "Verifies execute_with_fallback continues chain on CREDENTIAL_FALLBACK disposition"
    fixtures: []
  - name: test_respects_total_deadline
    line: 523
    purpose: "Verifies execute_with_fallback raises NoProviderAvailableError when total_deadline_seconds=0"
    fixtures: []
  - name: test_raises_no_provider_available_when_all_fail
    line: 536
    purpose: "Verifies NoProviderAvailableError is raised after all providers in chain fail"
    fixtures: []
  - name: test_records_all_attempts_in_result
    line: 557
    purpose: "Verifies all fallback attempt records are collected in result.attempts"
    fixtures: []
  - name: test_empty_chain_raises_no_provider_available
    line: 587
    purpose: "Verifies NoProviderAvailableError is raised with empty provider chain"
    fixtures: []
  - name: test_unexpected_exception_triggers_fallback
    line: 594
    purpose: "Verifies unexpected RuntimeError is caught, mapped to unexpected_error code, and triggers fallback"
    fixtures: []
  - name: test_profile_overrides_request_fields
    line: 616
    purpose: "Verifies RuntimeProfile model/temperature/max_tokens override LLMGenerationRequest fields"
    fixtures: []
  - name: test_returns_profiles_in_priority_order
    line: 686
    purpose: "Verifies resolve_chain queries DB, decrypts credentials, and returns profiles sorted by priority"
    fixtures: [monkeypatch]
  - name: test_appends_environment_fallback
    line: 754
    purpose: "Verifies resolve_chain appends the env fallback profile at end of chain"
    fixtures: [monkeypatch]
  - name: test_skips_vault_failed_providers
    line: 775
    purpose: "Verifies resolve_chain skips providers whose credential decryption fails"
    fixtures: [monkeypatch]
  - name: test_skips_all_providers_when_dek_fails
    line: 839
    purpose: "Verifies resolve_chain skips all user providers when DEK unwrap fails and still returns env fallback"
    fixtures: [monkeypatch]
  - name: test_no_secret_key_row_skips_user_providers
    line: 886
    purpose: "Verifies resolve_chain returns empty list when user has no secret key row"
    fixtures: [monkeypatch]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_fallback.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.llm.models import (
    ErrorDisposition,
    LLMGenerationRequest,
    LLMProtocol,
    LLMResponse,
    ProviderError,
)
from backend.core.llm.service import (
    NoProviderAvailableError,
    RuntimeProfile,
    build_environment_fallback,
    execute_with_fallback,
    resolve_chain,
)
from backend.core.llm.vault import (
    CredentialAuthenticationError,
    VaultError,
)


# ---------------------------------------------------------------------------
# Test DB helper
# ---------------------------------------------------------------------------

class FakeResult:
    def __init__(self, rows=None, rowcount=0, scalar_val=None):
        self._rows = rows or []
        self.rowcount = rowcount
        self._scalar = scalar_val

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(
    *,
    provider_id: int | None = 1,
    label: str = "test-provider",
    protocol: LLMProtocol = LLMProtocol.OPENAI,
    base_url: str = "https://api.example.com/v1",
    model: str = "gpt-4",
    temperature: float | None = None,
    max_tokens: int = 4096,
    thinking: bool = False,
    effort: str = "low",
    api_key: str = "sk-test-key",
    is_environment_fallback: bool = False,
) -> RuntimeProfile:
    return RuntimeProfile(
        provider_id=provider_id,
        label=label,
        protocol=protocol,
        base_url=base_url,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        thinking=thinking,
        effort=effort,
        api_key=api_key,
        is_environment_fallback=is_environment_fallback,
    )


def _request(
    *,
    prompt: str = "Hello",
    model: str = "gpt-4",
    max_tokens: int = 4096,
) -> LLMGenerationRequest:
    return LLMGenerationRequest(prompt=prompt, model=model, max_tokens=max_tokens)


def _response(text: str = "world") -> LLMResponse:
    return LLMResponse(text=text, model="gpt-4", finish_reason="stop")


def _provider_error(
    code: str = "provider_timeout",
    disposition: ErrorDisposition = ErrorDisposition.FALLBACK,
    status_code: int | None = None,
) -> ProviderError:
    return ProviderError(
        code=code,
        message=f"test error: {code}",
        status_code=status_code,
        disposition=disposition,
    )


# ---------------------------------------------------------------------------
# build_environment_fallback
# ---------------------------------------------------------------------------

class TestBuildEnvironmentFallback:
    def test_returns_profile_from_env_vars(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_PROTOCOL", "openai")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://api.test.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fallback")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")
        monkeypatch.setenv("LLM_FALLBACK_TEMPERATURE", "0.7")
        monkeypatch.setenv("LLM_FALLBACK_MAX_TOKENS", "2048")
        monkeypatch.setenv("LLM_FALLBACK_THINKING", "true")
        monkeypatch.setenv("LLM_FALLBACK_EFFORT", "medium")

        profile = build_environment_fallback()

        assert profile is not None
        assert profile.provider_id is None
        assert profile.protocol == LLMProtocol.OPENAI
        assert profile.base_url == "https://api.test.com/v1"
        assert profile.api_key == "sk-fallback"
        assert profile.model == "gpt-3.5-turbo"
        assert profile.temperature == 0.7
        assert profile.max_tokens == 2048
        assert profile.thinking is True
        assert profile.effort == "medium"
        assert profile.is_environment_fallback is True

    def test_returns_none_when_disabled(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://api.test.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fallback")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")

        assert build_environment_fallback() is None

    def test_returns_none_when_incomplete_missing_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://api.test.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")
        monkeypatch.delenv("LLM_FALLBACK_API_KEY", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

        assert build_environment_fallback() is None

    def test_returns_none_when_incomplete_missing_base_url(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.delenv("LLM_FALLBACK_BASE_URL", raising=False)
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fallback")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

        assert build_environment_fallback() is None

    def test_returns_none_when_incomplete_missing_model(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://api.test.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fallback")
        monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)

        assert build_environment_fallback() is None

    def test_falls_back_to_minimax_api_key(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.delenv("LLM_FALLBACK_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_API_KEY", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)
        monkeypatch.setenv("MINIMAX_API_KEY", "minimax-key-123")

        profile = build_environment_fallback()

        assert profile is not None
        assert profile.label == "minimax-legacy-fallback"
        assert profile.protocol == LLMProtocol.OPENAI
        assert profile.base_url == "https://api.minimax.io/v1"
        assert profile.model == "MiniMax-M3"
        assert profile.api_key == "minimax-key-123"
        assert profile.is_environment_fallback is True

    def test_primary_env_takes_precedence_over_minimax(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://api.primary.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-primary")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "primary-model")
        monkeypatch.setenv("MINIMAX_API_KEY", "minimax-key")

        profile = build_environment_fallback()

        assert profile is not None
        assert profile.label == "environment-fallback"
        assert profile.api_key == "sk-primary"

    def test_defaults_when_optional_vars_absent(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://api.test.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fallback")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-4")
        monkeypatch.delenv("LLM_FALLBACK_ENABLED", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_PROTOCOL", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_TEMPERATURE", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_MAX_TOKENS", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_THINKING", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_EFFORT", raising=False)

        profile = build_environment_fallback()

        assert profile is not None
        assert profile.protocol == LLMProtocol.OPENAI  # default
        assert profile.temperature is None
        assert profile.max_tokens == 4096
        assert profile.thinking is False
        assert profile.effort == "low"


# ---------------------------------------------------------------------------
# execute_with_fallback
# ---------------------------------------------------------------------------

class TestExecuteWithFallback:
    @pytest.mark.asyncio
    async def test_succeeds_on_first_provider(self):
        chain = [_profile(provider_id=1, label="p1")]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(return_value=_response("hello"))

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback(chain, _request())

        assert result.response.text == "hello"
        assert result.provider_id == 1
        assert result.label == "p1"
        assert len(result.attempts) == 1
        assert result.attempts[0].success is True

    @pytest.mark.asyncio
    async def test_falls_back_on_timeout(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")
        chain = [p1, p2]

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=[
                _provider_error("provider_timeout", ErrorDisposition.FALLBACK),
                _response("from p2"),
            ]
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback(chain, _request())

        assert result.response.text == "from p2"
        assert result.provider_id == 2
        assert len(result.attempts) == 2
        assert result.attempts[0].success is False
        assert result.attempts[0].error_code == "provider_timeout"
        assert result.attempts[1].success is True

    @pytest.mark.asyncio
    async def test_falls_back_on_429(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=[
                _provider_error(
                    "provider_rate_limited",
                    ErrorDisposition.FALLBACK,
                    status_code=429,
                ),
                _response("from p2"),
            ]
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback([p1, p2], _request())

        assert result.provider_id == 2
        assert result.attempts[0].error_code == "provider_rate_limited"

    @pytest.mark.asyncio
    async def test_falls_back_on_5xx(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=[
                _provider_error(
                    "provider_unavailable",
                    ErrorDisposition.FALLBACK,
                    status_code=500,
                ),
                _response("from p2"),
            ]
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback([p1, p2], _request())

        assert result.provider_id == 2

    @pytest.mark.asyncio
    async def test_stops_on_400_stop_disposition(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=_provider_error(
                "provider_request_error",
                ErrorDisposition.STOP,
                status_code=400,
            )
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            with pytest.raises(NoProviderAvailableError) as exc_info:
                await execute_with_fallback([p1, p2], _request())

        # Should have stopped after p1, not attempted p2
        assert len(exc_info.value.attempts) == 1
        assert exc_info.value.attempts[0].error_code == "provider_request_error"
        assert exc_info.value.attempts[0].error_disposition == "stop"

    @pytest.mark.asyncio
    async def test_stops_on_vault_stop(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=_provider_error(
                "vault_error",
                ErrorDisposition.VAULT_STOP,
            )
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            with pytest.raises(NoProviderAvailableError) as exc_info:
                await execute_with_fallback([p1, p2], _request())

        assert len(exc_info.value.attempts) == 1
        assert exc_info.value.attempts[0].error_disposition == "vault_stop"

    @pytest.mark.asyncio
    async def test_credential_fallback_marks_and_continues(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=[
                _provider_error(
                    "credential_error",
                    ErrorDisposition.CREDENTIAL_FALLBACK,
                    status_code=401,
                ),
                _response("from p2"),
            ]
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback([p1, p2], _request())

        assert result.provider_id == 2
        assert len(result.attempts) == 2
        assert result.attempts[0].error_code == "credential_error"
        assert result.attempts[0].error_disposition == "credential_fallback"
        assert result.attempts[1].success is True

    @pytest.mark.asyncio
    async def test_respects_total_deadline(self):
        """When deadline is already expired, stop immediately."""
        p1 = _profile(provider_id=1, label="p1")

        with pytest.raises(NoProviderAvailableError) as exc_info:
            await execute_with_fallback(
                [p1], _request(), total_deadline_seconds=0.0
            )

        assert len(exc_info.value.attempts) == 1
        assert exc_info.value.attempts[0].error_code == "deadline_exceeded"

    @pytest.mark.asyncio
    async def test_raises_no_provider_available_when_all_fail(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=_provider_error(
                "provider_timeout", ErrorDisposition.FALLBACK
            )
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            with pytest.raises(NoProviderAvailableError) as exc_info:
                await execute_with_fallback([p1, p2], _request())

        assert len(exc_info.value.attempts) == 2
        assert all(not a.success for a in exc_info.value.attempts)

    @pytest.mark.asyncio
    async def test_records_all_attempts_in_result(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")
        p3 = _profile(provider_id=3, label="p3")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=[
                _provider_error("provider_timeout", ErrorDisposition.FALLBACK),
                _provider_error(
                    "credential_error", ErrorDisposition.CREDENTIAL_FALLBACK
                ),
                _response("from p3"),
            ]
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback([p1, p2, p3], _request())

        assert len(result.attempts) == 3
        assert result.attempts[0].label == "p1"
        assert result.attempts[0].success is False
        assert result.attempts[1].label == "p2"
        assert result.attempts[1].success is False
        assert result.attempts[2].label == "p3"
        assert result.attempts[2].success is True

    @pytest.mark.asyncio
    async def test_empty_chain_raises_no_provider_available(self):
        with pytest.raises(NoProviderAvailableError) as exc_info:
            await execute_with_fallback([], _request())

        assert len(exc_info.value.attempts) == 0

    @pytest.mark.asyncio
    async def test_unexpected_exception_triggers_fallback(self):
        p1 = _profile(provider_id=1, label="p1")
        p2 = _profile(provider_id=2, label="p2")

        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(
            side_effect=[
                RuntimeError("something unexpected"),
                _response("from p2"),
            ]
        )

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            result = await execute_with_fallback([p1, p2], _request())

        assert result.provider_id == 2
        assert result.attempts[0].error_code == "unexpected_error"
        assert result.attempts[1].success is True

    @pytest.mark.asyncio
    async def test_profile_overrides_request_fields(self):
        """Profile model/temperature/max_tokens should override the request."""
        profile = _profile(
            provider_id=1,
            model="custom-model",
            temperature=0.5,
            max_tokens=2048,
        )
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(return_value=_response())

        with patch(
            "backend.core.llm.service.create_provider", return_value=mock_adapter
        ):
            await execute_with_fallback([profile], _request())

        call_args = mock_adapter.generate.call_args
        sent_request = call_args[0][0]
        assert sent_request.model == "custom-model"
        assert sent_request.temperature == 0.5
        assert sent_request.max_tokens == 2048


# ---------------------------------------------------------------------------
# resolve_chain
# ---------------------------------------------------------------------------

def _make_test_tables():
    """Build real SQLAlchemy table objects for testing."""
    import sqlalchemy

    metadata = sqlalchemy.MetaData()
    user_secret_keys = sqlalchemy.Table(
        "user_secret_keys",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("user_id", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("encrypted_dek", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("dek_nonce", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("algorithm", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("kek_version", sqlalchemy.String, nullable=False),
    )
    user_ai_providers = sqlalchemy.Table(
        "user_ai_providers",
        metadata,
        sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
        sqlalchemy.Column("user_id", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("label", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("protocol", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("base_url", sqlalchemy.Text, nullable=False),
        sqlalchemy.Column("model", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("temperature", sqlalchemy.Float, nullable=True),
        sqlalchemy.Column("max_tokens", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("thinking", sqlalchemy.Boolean, nullable=False),
        sqlalchemy.Column("effort", sqlalchemy.String, nullable=False),
        sqlalchemy.Column("encrypted_api_key", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("credential_nonce", sqlalchemy.LargeBinary, nullable=False),
        sqlalchemy.Column("credential_version", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("priority", sqlalchemy.Integer, nullable=False),
        sqlalchemy.Column("enabled", sqlalchemy.Boolean, nullable=False),
    )

    tables = MagicMock()
    tables.user_ai_providers = user_ai_providers
    tables.user_secret_keys = user_secret_keys
    return tables


class TestResolveChain:
    @pytest.mark.asyncio
    async def test_returns_profiles_in_priority_order(self, monkeypatch):
        """Verifies that resolve_chain queries the DB, decrypts, and orders."""
        monkeypatch.delenv("LLM_FALLBACK_ENABLED", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_API_KEY", raising=False)
        monkeypatch.delenv("LLM_FALLBACK_MODEL", raising=False)
        monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")

        mock_db = AsyncMock()
        tables = _make_test_tables()

        provider_row_1 = {
            "id": 10, "user_id": 1, "label": "Provider A",
            "protocol": "openai", "base_url": "https://api.a.com/v1",
            "model": "gpt-4", "temperature": None, "max_tokens": 4096,
            "thinking": False, "effort": "low",
            "encrypted_api_key": b"encrypted1",
            "credential_nonce": b"nonce1nonce1",
            "credential_version": 1, "priority": 0, "enabled": True,
        }
        provider_row_2 = {
            "id": 20, "user_id": 1, "label": "Provider B",
            "protocol": "anthropic", "base_url": "https://api.b.com/v1",
            "model": "claude-3", "temperature": 0.5, "max_tokens": 8192,
            "thinking": True, "effort": "medium",
            "encrypted_api_key": b"encrypted2",
            "credential_nonce": b"nonce2nonce2",
            "credential_version": 1, "priority": 1, "enabled": True,
        }
        key_row = {
            "encrypted_dek": b"wrapped-dek-data",
            "dek_nonce": b"keynoncekyn",
            "algorithm": "AES-256-GCM",
            "kek_version": "v1",
        }

        mock_db.execute = AsyncMock(side_effect=[
            FakeResult(rows=[provider_row_1, provider_row_2]),
            FakeResult(rows=[key_row]),
        ])
        mock_db.commit = AsyncMock()
        mock_backend = AsyncMock()

        with (
            patch(
                "backend.core.llm.service.unwrap_user_dek",
                new_callable=AsyncMock,
                return_value=b"x" * 32,
            ),
            patch(
                "backend.core.llm.service.decrypt_provider_credential",
                side_effect=["api-key-a", "api-key-b"],
            ),
        ):
            profiles = await resolve_chain(
                mock_db, tables, mock_backend, user_id=1
            )

        assert len(profiles) == 2
        assert profiles[0].label == "Provider A"
        assert profiles[0].api_key == "api-key-a"
        assert profiles[0].protocol == LLMProtocol.OPENAI
        assert profiles[1].label == "Provider B"
        assert profiles[1].api_key == "api-key-b"
        assert profiles[1].protocol == LLMProtocol.ANTHROPIC

    @pytest.mark.asyncio
    async def test_appends_environment_fallback(self, monkeypatch):
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://fallback.api.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fallback")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "gpt-3.5-turbo")

        mock_db = AsyncMock()
        tables = _make_test_tables()
        mock_db.execute = AsyncMock(return_value=FakeResult(rows=[]))
        mock_db.commit = AsyncMock()
        mock_backend = AsyncMock()

        profiles = await resolve_chain(
            mock_db, tables, mock_backend, user_id=1
        )

        assert len(profiles) == 1
        assert profiles[0].is_environment_fallback is True
        assert profiles[0].label == "environment-fallback"

    @pytest.mark.asyncio
    async def test_skips_vault_failed_providers(self, monkeypatch):
        """If a single credential decrypt fails, skip it but continue."""
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")

        mock_db = AsyncMock()
        tables = _make_test_tables()

        provider_row_ok = {
            "id": 10, "user_id": 1, "label": "good-provider",
            "protocol": "openai", "base_url": "https://api.good.com/v1",
            "model": "gpt-4", "temperature": None, "max_tokens": 4096,
            "thinking": False, "effort": "low",
            "encrypted_api_key": b"encrypted-ok",
            "credential_nonce": b"nonce-ok-ok-",
            "credential_version": 1, "priority": 0, "enabled": True,
        }
        provider_row_bad = {
            "id": 20, "user_id": 1, "label": "bad-provider",
            "protocol": "openai", "base_url": "https://api.bad.com/v1",
            "model": "gpt-4", "temperature": None, "max_tokens": 4096,
            "thinking": False, "effort": "low",
            "encrypted_api_key": b"encrypted-bad",
            "credential_nonce": b"nonce-bad-bd",
            "credential_version": 1, "priority": 1, "enabled": True,
        }
        key_row = {
            "encrypted_dek": b"wrapped-dek-data",
            "dek_nonce": b"keynoncekyn",
            "algorithm": "AES-256-GCM",
            "kek_version": "v1",
        }

        mock_db.execute = AsyncMock(side_effect=[
            FakeResult(rows=[provider_row_ok, provider_row_bad]),
            FakeResult(rows=[key_row]),
        ])
        mock_db.commit = AsyncMock()
        mock_backend = AsyncMock()

        def _decrypt_side_effect(envelope, *, dek, user_id, provider_id, protocol, base_url):
            if provider_id == 20:
                raise CredentialAuthenticationError("auth failed")
            return "decrypted-key"

        with (
            patch(
                "backend.core.llm.service.unwrap_user_dek",
                new_callable=AsyncMock,
                return_value=b"x" * 32,
            ),
            patch(
                "backend.core.llm.service.decrypt_provider_credential",
                side_effect=_decrypt_side_effect,
            ),
        ):
            profiles = await resolve_chain(
                mock_db, tables, mock_backend, user_id=1
            )

        # Only the good provider should appear; bad one skipped
        assert len(profiles) == 1
        assert profiles[0].label == "good-provider"

    @pytest.mark.asyncio
    async def test_skips_all_providers_when_dek_fails(self, monkeypatch):
        """If DEK unwrap fails, skip all user providers but still add env fallback."""
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "true")
        monkeypatch.setenv("LLM_FALLBACK_BASE_URL", "https://fallback.com/v1")
        monkeypatch.setenv("LLM_FALLBACK_API_KEY", "sk-fb")
        monkeypatch.setenv("LLM_FALLBACK_MODEL", "model-fb")

        mock_db = AsyncMock()
        tables = _make_test_tables()

        provider_row = {
            "id": 10, "user_id": 1, "label": "some-provider",
            "protocol": "openai", "base_url": "https://api.test.com/v1",
            "model": "gpt-4", "temperature": None, "max_tokens": 4096,
            "thinking": False, "effort": "low",
            "encrypted_api_key": b"encrypted",
            "credential_nonce": b"noncenonceno",
            "credential_version": 1, "priority": 0, "enabled": True,
        }
        key_row = {
            "encrypted_dek": b"bad-dek",
            "dek_nonce": b"keynoncekyn",
            "algorithm": "AES-256-GCM",
            "kek_version": "v1",
        }

        mock_db.execute = AsyncMock(side_effect=[
            FakeResult(rows=[provider_row]),
            FakeResult(rows=[key_row]),
        ])
        mock_db.commit = AsyncMock()
        mock_backend = AsyncMock()

        with patch(
            "backend.core.llm.service.unwrap_user_dek",
            new_callable=AsyncMock,
            side_effect=VaultError("unwrap failed"),
        ):
            profiles = await resolve_chain(
                mock_db, tables, mock_backend, user_id=1
            )

        # User providers skipped, only env fallback
        assert len(profiles) == 1
        assert profiles[0].is_environment_fallback is True

    @pytest.mark.asyncio
    async def test_no_secret_key_row_skips_user_providers(self, monkeypatch):
        """If user has no secret key row, skip user providers."""
        monkeypatch.setenv("LLM_FALLBACK_ENABLED", "false")

        mock_db = AsyncMock()
        tables = _make_test_tables()

        provider_row = {
            "id": 10, "user_id": 1, "label": "orphan-provider",
            "protocol": "openai", "base_url": "https://api.test.com/v1",
            "model": "gpt-4", "temperature": None, "max_tokens": 4096,
            "thinking": False, "effort": "low",
            "encrypted_api_key": b"encrypted",
            "credential_nonce": b"noncenonceno",
            "credential_version": 1, "priority": 0, "enabled": True,
        }

        mock_db.execute = AsyncMock(side_effect=[
            FakeResult(rows=[provider_row]),
            FakeResult(rows=[]),  # no secret key row → first() returns None
        ])
        mock_db.commit = AsyncMock()
        mock_backend = AsyncMock()

        profiles = await resolve_chain(
            mock_db, tables, mock_backend, user_id=1
        )

        assert len(profiles) == 0
