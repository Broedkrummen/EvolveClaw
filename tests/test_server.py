import importlib
import sys
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from scope.synthesizer import Guideline
from task_optimizer import TaskScopedOptimizer
from memory_store import RevisionConflict
import asyncio
import json
from scope.models import ModelResponse

TRUSTED = {"audience_key": "owner:agent", "project_key": "project:A"}


def optimizer(tmp_path, scope="tactical", confidence=0.9, max_rules=1):
    opt = TaskScopedOptimizer(synthesizer_model=SimpleNamespace(), exp_path=str(tmp_path),
                             max_rules_per_task=max_rules, quality_analysis_frequency=1)
    opt.synthesizer.generate_update_from_error = AsyncMock(return_value=Guideline(
        update_text="Check the schema before processing the result", rationale="Observed error", confidence=confidence))
    opt._classify_and_check_duplicate = AsyncMock(return_value={
        "scope": scope, "domain": "general", "confidence": confidence,
        "is_duplicate": False, "reason": "test", "refined_rule": "Check the schema before processing the result"})
    return opt


async def step(opt, task="A"):
    return await opt.on_step_complete(agent_name="agent", agent_role="assistant", task="request",
                                      task_id=task, scope=TRUSTED, model_output="answer", error=Exception("problem"))


@pytest.mark.asyncio
async def test_task_cap_and_reset_preserve_other_tasks(tmp_path):
    opt = optimizer(tmp_path)
    assert await step(opt, "A")
    assert await step(opt, "A") is None
    assert await step(opt, "B")
    await opt.reset_tactical(agent_name="agent", task_id="A", scope=TRUSTED)
    assert await step(opt, "A")
    assert await step(opt, "B") is None


@pytest.mark.asyncio
async def test_unpersisted_strategic_result_falls_back_to_tactical(tmp_path):
    opt = optimizer(tmp_path, scope="strategic", confidence=0.8)
    assert (await step(opt))[1] == "tactical"
    assert opt.strategic_guidelines("agent", TRUSTED) == []


@pytest.mark.asyncio
async def test_strategic_rules_survive_reset_and_new_optimizer(tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    result = await step(opt)
    assert result[1] == "strategic"
    await opt.reset_tactical(agent_name="agent", task_id="A", scope=TRUSTED)
    restored = optimizer(tmp_path)
    assert restored.strategic_guidelines("agent", TRUSTED) == [result[0]]


@pytest.mark.asyncio
async def test_consolidated_strategic_advice_does_not_return_as_raw_tactical(tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    opt.memory_store.max_rules_per_domain = 1
    opt.memory_store.add_rule("agent", TRUSTED, "Initial guidance", expected_revision=0)
    from unittest.mock import patch
    with patch("task_optimizer.MemoryOptimizer.optimize_rules", new=AsyncMock(return_value=[{
        "rule": "Consolidated authoritative guidance", "rationale": "merged", "confidence": .9}])):
        assert (await step(opt))[1] == "strategic"
    assert opt.strategic_guidelines("agent", TRUSTED) == ["Consolidated authoritative guidance"]


def test_existing_dotenv_memory_path_wins_over_managed_default(tmp_path):
    config = Path(__file__).parents[1] / "server" / "config.py"
    (tmp_path / "config.py").write_text(config.read_text())
    (tmp_path / ".env").write_text("EVOLVECLAW_SCOPE_DATA=existing-custom-memory\n")
    env = {**os.environ, "EVOLVECLAW_SCOPE_DATA_DEFAULT": "managed-default"}
    env.pop("EVOLVECLAW_SCOPE_DATA", None)
    result = subprocess.run([sys.executable, "-c", "from config import ServerConfig; print(ServerConfig.SCOPE_DATA_PATH)"],
                            cwd=tmp_path, env=env, capture_output=True, text=True, check=True)
    assert result.stdout.strip() == "existing-custom-memory"


@pytest.fixture
def server(monkeypatch, tmp_path):
    for name in ("EVOLVECLAW_SCOPE_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EVOLVECLAW_SCOPE_DATA", str(tmp_path))
    sys.modules.pop("server", None)
    sys.modules.pop("config", None)
    return importlib.import_module("server")


def test_unconfigured_server_is_live_and_explicit_configuration_is_supported(server, monkeypatch):
    client = TestClient(server.app)
    assert client.get("/health").json()["configured"] is False
    assert client.get("/rules/agent").json()["configured"] is False
    initialized = []
    monkeypatch.setattr(server, "init_optimizer", lambda *args: initialized.append(args))
    result = client.post("/configure", json={"provider": "openai", "model": "test", "api_key": "fake", "base_url": "https://example.invalid/v1"})
    assert result.json()["status"] == "ok"
    assert initialized[0][-1] == "https://example.invalid/v1"


def test_openai_adapter_preserves_custom_endpoint(server):
    model = server._create_model("openai", "test", "fake", "https://example.invalid/v1")
    assert str(model.client.base_url) == "https://example.invalid/v1/"


def test_step_history_preserves_current_answer_and_reports_actual_rule_count(server, tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    seen = {}
    original = opt.on_step_complete
    async def capture(**kwargs):
        seen.update(kwargs)
        return await original(**kwargs)
    opt.on_step_complete = capture
    server.optimizer = opt
    client = TestClient(server.app)
    result = client.post("/step", json={"agent_name": "agent", "scope": TRUSTED, "task": "request", "task_id": "A", "error": "problem",
                                       "model_output": "THE CURRENT ANSWER", "conversation_history": "old context " * 100})
    assert result.json()["guideline_type"] == "strategic"
    assert "THE CURRENT ANSWER" in seen["model_output"]
    assert seen["truncate_context"] is False
    assert client.get("/rules/agent", params=TRUSTED).json()["rule_count"] == 1
    assert client.get("/stats/agent", params=TRUSTED).json()["strategic_count"] == 1
    assert client.post("/reset", json={"agent_name": "agent", "task_id": "A", "scope": TRUSTED}).json()["status"] == "ok"
    assert ("agent", TRUSTED["audience_key"], TRUSTED["project_key"], "A") not in opt.task_counters
    assert len(opt.strategic_guidelines("agent", TRUSTED)) == 1


def test_protocol_requires_scope_and_enforces_checked_management(server, tmp_path):
    server.optimizer = optimizer(tmp_path, scope="strategic")
    client = TestClient(server.app)
    assert client.get("/health").json()["protocol_version"] == 3
    assert client.post("/step", json={"agent_name": "agent", "task": "request", "model_output": "answer"}).json()["reason"] == "trusted scope unavailable"
    learned = client.post("/step", json={"agent_name": "agent", "task": "request", "error": "problem", "scope": TRUSTED}).json()
    assert learned["guideline_id"] and learned["evidence_id"]
    assert client.get("/rules/agent").json()["guidelines"] == []
    assert client.get("/rules/agent", params=TRUSTED).json()["rule_count"] == 1
    disabled = client.post("/memory/mutate", json={"agent_name": "agent", "scope": TRUSTED,
        "operation": "disable", "args": {"rule_id": learned["guideline_id"]}, "expected_revision": learned["revision"]})
    assert disabled.status_code == 200
    stale = client.post("/memory/mutate", json={"agent_name": "agent", "scope": TRUSTED,
        "operation": "restore", "args": {"rule_id": learned["guideline_id"]}, "expected_revision": learned["revision"]})
    assert stale.status_code == 409
    assert client.get("/rules/agent", params=TRUSTED).json()["rule_count"] == 0
    denied = client.post("/memory/query", json={"agent_name": "agent", "scope": {**TRUSTED, "audience_key": "other"},
        "operation": "detail", "args": {"rule_id": learned["guideline_id"]}})
    assert denied.status_code == 404


def test_sidecar_rejects_browser_origins_and_requires_optional_token(server):
    client = TestClient(server.app)
    assert client.get("/health", headers={"Origin": "https://attacker.invalid"}).status_code == 403
    server.cfg.AUTH_TOKEN = "test-secret"
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"Authorization": "Bearer test-secret"}).status_code == 200


def test_remote_sidecar_requires_explicit_token_and_rejects_browser_origins(server):
    client = TestClient(server.app, client=("192.0.2.1", 1234))
    assert client.get("/health").status_code == 403
    server.cfg.AUTH_TOKEN = "test-remote-secret"
    assert client.get("/health").status_code == 401
    headers = {"Authorization": "Bearer test-remote-secret"}
    assert client.get("/health", headers=headers).status_code == 200
    assert client.get("/health", headers={**headers, "Origin": "https://example.invalid"}).status_code == 403


def test_long_step_keeps_latest_answer_and_tool_observations(server, tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    captured = {}
    original = opt.on_step_complete
    async def capture(**kwargs):
        captured.update(kwargs)
        return await original(**kwargs)
    opt.on_step_complete = capture
    server.optimizer = opt
    client = TestClient(server.app)
    result = client.post("/step", json={"agent_name": "agent", "scope": TRUSTED, "task": "request", "task_id": "A",
        "error": "problem", "conversation_history": "old history " * 400,
        "model_output": "x" * 40000 + "FINAL CURRENT ANSWER", "tool_calls": "t" * 20000 + "LATEST TOOL",
        "observations": "o" * 20000 + "LATEST OBSERVATION"})
    assert result.status_code == 200
    assert "FINAL CURRENT ANSWER" in captured["model_output"]
    assert captured["tool_calls"].endswith("LATEST TOOL")
    assert captured["observations"].endswith("LATEST OBSERVATION")


def test_request_bounds_and_outcome_provenance(server):
    client = TestClient(server.app)
    assert client.post("/step", json={"agent_name": "agent", "scope": TRUSTED,
        "task": "task", "model_output": "a" * 48001}).status_code == 422
    assert client.post("/memory/mutate", json={"agent_name": "agent", "scope": TRUSTED,
        "operation": "pause"}).status_code == 422
    result = client.post("/outcome", json={"agent_name": "agent", "scope": TRUSTED,
        "task_id": "task", "result": "success", "source": "agent_run"}).json()
    assert result["result"] == "unknown" and result["validated"] is False


@pytest.mark.asyncio
async def test_pause_during_synthesis_prevents_commit_and_does_not_consume_task_cap(tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    started, release = asyncio.Event(), asyncio.Event()
    async def delayed(**kwargs):
        started.set()
        await release.wait()
        return Guideline("Advice generated before pause", "Observed", confidence="high")
    opt.synthesizer.generate_update_from_error = delayed
    job = asyncio.create_task(step(opt))
    await started.wait()
    opt.memory_store.mutate("agent", TRUSTED, "pause", {}, 0)
    release.set()
    with pytest.raises(RevisionConflict):
        await job
    assert opt.strategic_guidelines("agent", TRUSTED) == []
    assert list(opt.task_counters.values())[0][0] == 0


class ModelFixture:
    model = "fixture-model"
    def __init__(self, actual=False):
        self.prompts, self.actual = [], actual
    async def generate(self, messages):
        content = messages[0].content[0]["text"]
        self.prompts.append(content)
        if "PROPOSED UPDATE" in content:
            data = {"is_duplicate": False, "scope": "strategic", "confidence": .9,
                    "domain": "general", "reason": "Fixture classification"}
        else:
            data = {"update_text": "Keep source references with verified claims", "rationale": "Fixture",
                    "confidence": "high"}
        raw = {"usage": {"prompt_tokens": 40, "completion_tokens": 10}} if self.actual else None
        return ModelResponse(json.dumps(data), raw_response=raw)


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["efficiency", "thoroughness"])
async def test_both_quality_modes_and_classification_are_preserved_and_metered(tmp_path, mode):
    model = ModelFixture(actual=True)
    opt = TaskScopedOptimizer(synthesizer_model=model, exp_path=str(tmp_path),
        synthesis_mode=mode, quality_analysis_frequency=1)
    result = await opt.on_step_complete(agent_name="agent", scope=TRUSTED, agent_role="assistant",
        task="research", task_id="task", model_output="Completed task with a missed source link")
    assert result.type == "strategic"
    assert len(model.prompts) == 2
    usage = opt.memory_store.query("agent", TRUSTED)["usage"]
    assert usage["actual"]["calls"] == 2 and usage["actual"]["input_tokens"] == 80
    assert usage["by_stage"] == {"synthesis": 1, "classification": 1}
    assert usage["cost"]["status"] == "unknown" and usage["cost"]["amount"] is None


@pytest.mark.asyncio
@pytest.mark.parametrize("estimate", [False, True])
async def test_missing_provider_usage_is_unknown_unless_estimation_explicit(tmp_path, estimate):
    opt = TaskScopedOptimizer(synthesizer_model=ModelFixture(), exp_path=str(tmp_path),
        estimate_usage=estimate, quality_analysis_frequency=1)
    await opt.on_step_complete(agent_name="agent", scope=TRUSTED, agent_role="assistant",
        task="request", model_output="Answer", task_id="task")
    usage = opt.memory_store.query("agent", TRUSTED)["usage"]
    assert usage["estimated" if estimate else "unknown"]["calls"] == 2
    assert usage["cost"]["amount"] is None
