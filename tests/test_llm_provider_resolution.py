"""Issue #499: `LLM_PROVIDER` was independently read (`os.getenv("LLM_PROVIDER",
"openai").lower()`) and branched on in four separate `agent/main.py` functions
-- `_resolve_agent_model`, `_resolve_agent_model_settings`,
`_local_reasoning_output_tail`, and `_configure_hosted_openai_compatible_backend`.
That's four places to keep in sync (and four places a future provider's typo
or default-value drift could disagree with the others) for what is really one
decision: which provider is configured right now.

These tests pin two things:

1. `agent._resolve_llm_provider()` (plain terms: the one function that reads
   the LLM_PROVIDER environment variable and normalizes it to lowercase) is
   the single source of truth other code should call instead of re-reading
   the environment.
2. Each of the four call sites' existing behavior, for every currently
   supported provider value ("openai" default, "anthropic", "local",
   "runpod", plus an unset/mixed-case env var), is unchanged now that it
   goes through the shared resolver.
"""

import inspect
import re

import pytest
from agents.models.default_models import get_default_model_settings
from openai.types.shared import Reasoning

import agent.main as agent_main

# ---------------------------------------------------------------------------
# 1. Only one place reads LLM_PROVIDER from the environment.
# ---------------------------------------------------------------------------


def test_only_resolve_llm_provider_reads_the_env_var_directly():
    """`os.getenv("LLM_PROVIDER"` (any case/quote spelling) should appear
    exactly once in agent/main.py's source -- inside `_resolve_llm_provider`
    itself. Everywhere else must call that function instead of re-reading
    the environment, so the four call sites can never drift out of sync."""
    source = inspect.getsource(agent_main)
    hits = re.findall(r'os\.getenv\(\s*["\']LLM_PROVIDER["\']', source)
    assert len(hits) == 1, (
        "expected exactly one direct os.getenv('LLM_PROVIDER') read in "
        f"agent/main.py, found {len(hits)}"
    )


def test_resolve_llm_provider_exists_and_is_called_by_source():
    assert hasattr(agent_main, "_resolve_llm_provider")
    source = inspect.getsource(agent_main._resolve_agent_model)
    assert "_resolve_llm_provider()" in source
    source = inspect.getsource(agent_main._resolve_agent_model_settings)
    assert "_resolve_llm_provider()" in source
    source = inspect.getsource(agent_main._local_reasoning_output_tail)
    assert "_resolve_llm_provider()" in source
    source = inspect.getsource(agent_main._configure_hosted_openai_compatible_backend)
    assert "_resolve_llm_provider()" in source


# ---------------------------------------------------------------------------
# 2. The resolver itself: reads LLM_PROVIDER, normalizes, defaults to openai.
# ---------------------------------------------------------------------------


def test_resolve_llm_provider_defaults_to_openai_when_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert agent_main._resolve_llm_provider() == "openai"


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("openai", "openai"),
        ("OpenAI", "openai"),
        ("ANTHROPIC", "anthropic"),
        ("Local", "local"),
        ("RunPod", "runpod"),
        ("  Local  ".strip(), "local"),
    ],
)
def test_resolve_llm_provider_lowercases(monkeypatch, raw, expected):
    monkeypatch.setenv("LLM_PROVIDER", raw)
    assert agent_main._resolve_llm_provider() == expected


# ---------------------------------------------------------------------------
# 3. Existing behavior of the four call sites is unchanged for every
#    currently-supported provider value, set via the real environment
#    variable (i.e. exercised through the shared resolver end to end).
# ---------------------------------------------------------------------------


def test_resolve_agent_model_openai_default(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert agent_main._resolve_agent_model() == "gpt-5.5"


def test_resolve_agent_model_openai_explicit_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "OpenAI")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-9000")
    assert agent_main._resolve_agent_model() == "gpt-9000"


def test_resolve_agent_model_local_default(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "local")
    monkeypatch.delenv("LOCAL_AGENT_MODEL", raising=False)
    assert agent_main._resolve_agent_model() == "gpt-oss:20b"


def test_resolve_agent_model_local_explicit_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "LOCAL")
    monkeypatch.setenv("LOCAL_AGENT_MODEL", "qwen3.8:27b")
    assert agent_main._resolve_agent_model() == "qwen3.8:27b"


def test_resolve_agent_model_runpod_requires_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "runpod")
    monkeypatch.delenv("RUNPOD_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="RUNPOD_MODEL"):
        agent_main._resolve_agent_model()


def test_resolve_agent_model_runpod_explicit_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "RunPod")
    monkeypatch.setenv("RUNPOD_MODEL", "meta-llama/Llama-3-70b")
    assert agent_main._resolve_agent_model() == "meta-llama/Llama-3-70b"


def test_resolve_agent_model_anthropic_returns_litellm_model(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    from agents.extensions.models.litellm_model import LitellmModel

    result = agent_main._resolve_agent_model()
    assert isinstance(result, LitellmModel)
    assert result.model == "anthropic/claude-sonnet-5"


def test_resolve_agent_model_settings_local_is_special_cased(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Local")
    settings = agent_main._resolve_agent_model_settings()
    assert settings.temperature == 1.0
    assert settings.top_p == 0.95
    assert isinstance(settings.reasoning, Reasoning)
    assert settings.reasoning.effort == "xhigh"


@pytest.mark.parametrize("provider", ["openai", "anthropic", "runpod", None])
def test_resolve_agent_model_settings_non_local_uses_sdk_default(monkeypatch, provider):
    if provider is None:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("LLM_PROVIDER", provider.upper())
    assert agent_main._resolve_agent_model_settings() == get_default_model_settings()


def test_local_reasoning_output_tail_local_appends_instructions(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "LOCAL")
    tail = agent_main._local_reasoning_output_tail()
    assert "Output format" in tail
    assert tail != ""


@pytest.mark.parametrize("provider", ["openai", "anthropic", "runpod", None])
def test_local_reasoning_output_tail_non_local_is_empty(monkeypatch, provider):
    if provider is None:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("LLM_PROVIDER", provider.upper())
    assert agent_main._local_reasoning_output_tail() == ""


def test_configure_hosted_openai_compatible_backend_local(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "Local")
    monkeypatch.delenv("LOCAL_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LOCAL_LLM_API_KEY", raising=False)
    captured = {}

    def fake_set_default_openai_client(client, use_for_tracing=False):
        captured["base_url"] = str(client.base_url)
        captured["api_key"] = client.api_key

    monkeypatch.setattr(agent_main, "set_default_openai_client", fake_set_default_openai_client)
    monkeypatch.setattr(agent_main, "set_default_openai_api", lambda *_: None)
    monkeypatch.setattr(agent_main, "set_tracing_disabled", lambda *_: None)

    agent_main._configure_hosted_openai_compatible_backend()
    assert captured["base_url"] == "http://localhost:11434/v1/"
    assert captured["api_key"] == "unused"


def test_configure_hosted_openai_compatible_backend_runpod_requires_creds(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "RUNPOD")
    monkeypatch.delenv("RUNPOD_ENDPOINT_ID", raising=False)
    monkeypatch.delenv("RUNPOD_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="RUNPOD_ENDPOINT_ID"):
        agent_main._configure_hosted_openai_compatible_backend()


def test_configure_hosted_openai_compatible_backend_runpod(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "RunPod")
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "abc123")
    monkeypatch.setenv("RUNPOD_API_KEY", "secret")
    captured = {}

    def fake_set_default_openai_client(client, use_for_tracing=False):
        captured["base_url"] = str(client.base_url)
        captured["api_key"] = client.api_key

    monkeypatch.setattr(agent_main, "set_default_openai_client", fake_set_default_openai_client)
    monkeypatch.setattr(agent_main, "set_default_openai_api", lambda *_: None)
    monkeypatch.setattr(agent_main, "set_tracing_disabled", lambda *_: None)

    agent_main._configure_hosted_openai_compatible_backend()
    assert captured["base_url"] == "https://api.runpod.ai/v2/abc123/openai/v1/"
    assert captured["api_key"] == "secret"


@pytest.mark.parametrize("provider", ["openai", "anthropic", None])
def test_configure_hosted_openai_compatible_backend_noop_for_non_hosted(monkeypatch, provider):
    if provider is None:
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
    else:
        monkeypatch.setenv("LLM_PROVIDER", provider)
    calls = []
    monkeypatch.setattr(
        agent_main, "set_default_openai_client", lambda *a, **k: calls.append("client")
    )
    monkeypatch.setattr(agent_main, "set_default_openai_api", lambda *a, **k: calls.append("api"))
    monkeypatch.setattr(agent_main, "set_tracing_disabled", lambda *a, **k: calls.append("tracing"))
    agent_main._configure_hosted_openai_compatible_backend()
    assert calls == []
