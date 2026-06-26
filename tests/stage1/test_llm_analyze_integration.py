"""
---
name: test_llm_analyze_integration
description: "Integration tests for analyze_with_providers() — mocked LLM/DB/sanitizer orchestration"
stage: stage1
type: pytest
target:
  layer: backend
  domain: llm-analyze
spec_doc: null
test_file: tests/stage1/test_llm_analyze_integration.py
functions:
  - name: test_analyze_list_returns_valid_rules
    line: 99
    purpose: "List mode returns a dict containing all 4 required keys"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_content_returns_valid_rules
    line: 151
    purpose: "Content mode returns a dict containing all 5 required keys"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_content_preserves_vue_flags
    line: 203
    purpose: "Content mode with a Vue template adds is_vue_template and vue_json_field to result"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_no_provider_raises
    line: 244
    purpose: "Raises NoProviderAvailableError when the resolved chain is empty"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_invalid_json_returns_empty
    line: 277
    purpose: "Returns {} when the LLM response cannot be parsed as JSON"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_validation_failure_returns_empty
    line: 313
    purpose: "Returns {} when parsed rules fail schema validation"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_env_only_works
    line: 353
    purpose: "Analysis succeeds when the chain contains only the env-fallback profile"
    fixtures: [fake_db, fake_tables, fake_kek]
  - name: test_analyze_debug_writer_saves_artifacts
    line: 401
    purpose: "debug_writer.save() is called at least twice when a writer is provided"
    fixtures: [fake_db, fake_tables, fake_kek]
run:
  command: "PYTHONPATH=.:backend:tests/stage1 python -m pytest tests/stage1/test_llm_analyze_integration.py -v"
  env:
    TEST_DATABASE_URL: "postgresql+asyncpg://palimpsest:testpass123@localhost:5432/palimpsest_test"
  prerequisites:
    - "PostgreSQL running with palimpsest_test database"
---

Integration tests for core.ai.analyze_with_providers().

Tests mock all external dependencies (LLM providers, DB, sanitizer) to verify
the orchestration logic: chain resolution → LLM call → parse → validate → return.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from core.llm.service import NoProviderAvailableError
from core.llm.models import LLMResponse


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _make_service_result(text: str):
    """Create a fake LLMServiceResult with given response text."""
    response = LLMResponse(text=text, model="test-model")
    result = MagicMock()
    result.response = response
    result.provider_id = 1
    result.label = "test"
    result.protocol = "openai"
    result.model = "test-model"
    result.attempts = []
    return result


def _make_runtime_profile(provider_id: int = 1, label: str = "test"):
    """Create a fake RuntimeProfile."""
    profile = MagicMock()
    profile.provider_id = provider_id
    profile.label = label
    profile.is_environment_fallback = False
    return profile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_db():
    return MagicMock()


@pytest.fixture
def fake_tables():
    return MagicMock()


@pytest.fixture
def fake_kek():
    return MagicMock()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnalyzeWithProviders:
    """Test suite for core.ai.analyze_with_providers()."""

    # ------------------------------------------------------------------
    # 1. List mode – happy path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.validate_list_rules",
           return_value={"container": ".c", "item": ".i", "title": "h2", "link": "a"})
    @patch("core.ai.parse_selector_response",
           return_value={"container": ".c", "item": ".i", "title": "h2", "link": "a"})
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_list_returns_valid_rules(
        self,
        mock_clean,
        mock_resolve,
        mock_execute,
        mock_parse,
        mock_validate,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """List mode returns a dict containing all 4 required keys."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = [_make_runtime_profile()]
        mock_execute.return_value = _make_service_result(
            '{"container":".c","item":".i","title":"h2","link":"a"}'
        )

        result = await analyze_with_providers(
            "<html><body></body></html>",
            "list",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
        )

        assert isinstance(result, dict)
        for key in ("container", "item", "title", "link"):
            assert key in result, f"Expected key '{key}' in result"

    # ------------------------------------------------------------------
    # 2. Content mode – happy path
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.validate_content_rules",
           return_value={
               "title": "h1", "body": "div.content", "date": "time",
               "image": "img", "author": "span.author",
           })
    @patch("core.ai.parse_selector_response",
           return_value={
               "title": "h1", "body": "div.content", "date": "time",
               "image": "img", "author": "span.author",
           })
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.detect_vue_template", return_value=("cleaned", False, None))
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_content_returns_valid_rules(
        self,
        mock_clean,
        mock_detect_vue,
        mock_resolve,
        mock_execute,
        mock_parse,
        mock_validate,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """Content mode returns a dict containing all 5 required keys."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = [_make_runtime_profile()]
        mock_execute.return_value = _make_service_result(
            '{"title":"h1","body":"div.content","date":"time","image":"img","author":"span.author"}'
        )

        result = await analyze_with_providers(
            "<html><body><article></article></body></html>",
            "content",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
        )

        assert isinstance(result, dict)
        for key in ("title", "body", "date", "image", "author"):
            assert key in result, f"Expected key '{key}' in result"

    # ------------------------------------------------------------------
    # 3. Content mode – Vue template flags are preserved
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.validate_content_rules",
           return_value={
               "title": "h1", "body": "div.content", "date": "time",
               "image": "img", "author": "span.author",
           })
    @patch("core.ai.parse_selector_response",
           return_value={
               "title": "h1", "body": "div.content", "date": "time",
               "image": "img", "author": "span.author",
           })
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.detect_vue_template", return_value=("cleaned", True, "jsonField"))
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_content_preserves_vue_flags(
        self,
        mock_clean,
        mock_detect_vue,
        mock_resolve,
        mock_execute,
        mock_parse,
        mock_validate,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """Content mode with a Vue template adds is_vue_template and vue_json_field to result."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = [_make_runtime_profile()]
        mock_execute.return_value = _make_service_result(
            '{"title":"h1","body":"div.content","date":"time","image":"img","author":"span.author"}'
        )

        result = await analyze_with_providers(
            "<html><body><div id='app'></div></body></html>",
            "content",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
        )

        assert result.get("is_vue_template") is True
        assert result.get("vue_json_field") == "jsonField"

    # ------------------------------------------------------------------
    # 4. No provider available – raises
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_no_provider_raises(
        self,
        mock_clean,
        mock_resolve,
        mock_execute,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """Raises NoProviderAvailableError when the resolved chain is empty."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = []
        mock_execute.side_effect = NoProviderAvailableError([])

        with pytest.raises(NoProviderAvailableError):
            await analyze_with_providers(
                "<html></html>",
                "list",
                user_id=1,
                db=fake_db,
                tables=fake_tables,
                kek_backend=fake_kek,
            )

    # ------------------------------------------------------------------
    # 5. Unparseable LLM response – returns {}
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.parse_selector_response", side_effect=ValueError("no JSON found"))
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_invalid_json_returns_empty(
        self,
        mock_clean,
        mock_resolve,
        mock_execute,
        mock_parse,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """Returns {} when the LLM response cannot be parsed as JSON."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = [_make_runtime_profile()]
        mock_execute.return_value = _make_service_result("not json at all")

        result = await analyze_with_providers(
            "<html></html>",
            "list",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
        )

        assert result == {}

    # ------------------------------------------------------------------
    # 6. Validation failure – returns {}
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.validate_list_rules", side_effect=ValueError("missing required field: 'item'"))
    @patch("core.ai.parse_selector_response", return_value={"container": ".c"})
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_validation_failure_returns_empty(
        self,
        mock_clean,
        mock_resolve,
        mock_execute,
        mock_parse,
        mock_validate,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """Returns {} when parsed rules fail schema validation (missing fields)."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = [_make_runtime_profile()]
        mock_execute.return_value = _make_service_result('{"container": ".c"}')

        result = await analyze_with_providers(
            "<html></html>",
            "list",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
        )

        assert result == {}

    # ------------------------------------------------------------------
    # 7. Environment-only fallback profile works
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.validate_list_rules",
           return_value={"container": ".c", "item": ".i", "title": "h2", "link": "a"})
    @patch("core.ai.parse_selector_response",
           return_value={"container": ".c", "item": ".i", "title": "h2", "link": "a"})
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_env_only_works(
        self,
        mock_clean,
        mock_resolve,
        mock_execute,
        mock_parse,
        mock_validate,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """Analysis succeeds when the chain contains only the env-fallback profile."""
        from core.ai import analyze_with_providers

        env_profile = MagicMock()
        env_profile.provider_id = None
        env_profile.label = "environment-fallback"
        env_profile.is_environment_fallback = True

        mock_resolve.return_value = [env_profile]
        mock_execute.return_value = _make_service_result(
            '{"container":".c","item":".i","title":"h2","link":"a"}'
        )

        result = await analyze_with_providers(
            "<html></html>",
            "list",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
        )

        assert result != {}
        assert "container" in result

    # ------------------------------------------------------------------
    # 8. debug_writer receives save() calls
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    @patch("core.ai.validate_list_rules",
           return_value={"container": ".c", "item": ".i", "title": "h2", "link": "a"})
    @patch("core.ai.parse_selector_response",
           return_value={"container": ".c", "item": ".i", "title": "h2", "link": "a"})
    @patch("core.ai.execute_with_fallback", new_callable=AsyncMock)
    @patch("core.ai.resolve_chain", new_callable=AsyncMock)
    @patch("core.sanitizer.clean_html_for_ai", return_value="cleaned")
    async def test_analyze_debug_writer_saves_artifacts(
        self,
        mock_clean,
        mock_resolve,
        mock_execute,
        mock_parse,
        mock_validate,
        fake_db,
        fake_tables,
        fake_kek,
    ):
        """debug_writer.save() is called at least twice when a writer is provided."""
        from core.ai import analyze_with_providers

        mock_resolve.return_value = [_make_runtime_profile()]
        mock_execute.return_value = _make_service_result(
            '{"container":".c","item":".i","title":"h2","link":"a"}'
        )

        debug_writer = MagicMock()

        await analyze_with_providers(
            "<html></html>",
            "list",
            user_id=1,
            db=fake_db,
            tables=fake_tables,
            kek_backend=fake_kek,
            debug_writer=debug_writer,
        )

        assert debug_writer.save.call_count >= 2, (
            f"Expected debug_writer.save to be called at least twice, "
            f"got {debug_writer.save.call_count} calls"
        )
