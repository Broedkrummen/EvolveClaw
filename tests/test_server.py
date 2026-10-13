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
                                      task_id=task, model_output="answer", error=Exception("problem"))


@pytest.mark.asyncio
async def test_task_cap_and_reset_preserve_other_tasks(tmp_path):
    opt = optimizer(tmp_path)
    assert await step(opt, "A")
    assert await step(opt, "A") is None
    assert await step(opt, "B")
    await opt.reset_tactical(agent_name="agent", task_id="A")
    assert await step(opt, "A")
    assert await step(opt, "B") is None


@pytest.mark.asyncio
async def test_unpersisted_strategic_result_falls_back_to_tactical(tmp_path):
    opt = optimizer(tmp_path, scope="strategic", confidence=0.8)
    assert (await step(opt))[1] == "tactical"
    assert opt.strategic_guidelines("agent") == []


@pytest.mark.asyncio
async def test_strategic_rules_survive_reset_and_new_optimizer(tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    result = await step(opt)
    assert result[1] == "strategic"
    await opt.reset_tactical(agent_name="agent", task_id="A")
    restored = optimizer(tmp_path)
    assert restored.strategic_guidelines("agent") == [result[0]]


@pytest.mark.asyncio
async def test_consolidated_strategic_advice_does_not_return_as_raw_tactical(tmp_path):
    opt = optimizer(tmp_path, scope="strategic")
    async def consolidate(**kwargs):
        opt.strategic_store.rules = {"agent": {"general": [{
            "rule": "Consolidated authoritative guidance", "rationale": "merged", "confidence": 0.9,
        }]}}
        opt.strategic_store._save_rules(force_overwrite=True)
        return True
    # Exercise the actual wrapper's promotion capture around a consolidating store.
    async def promote(**kwargs):
        result = await consolidate(**kwargs)
        opt._promotion_succeeded = result
        return result
    opt.strategic_store.add_strategic_rule = promote
    assert (await step(opt))[1] == "strategic"
    assert opt.strategic_guidelines("agent") == ["Consolidated authoritative guidance"]


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
    result = client.post("/step", json={"agent_name": "agent", "task": "request", "task_id": "A", "error": "problem",
                                       "model_output": "THE CURRENT ANSWER", "conversation_history": "old context " * 100})
    assert result.json()["guideline_type"] == "strategic"
    assert "THE CURRENT ANSWER" in seen["model_output"]
    assert seen["truncate_context"] is False
    assert client.get("/rules/agent").json()["rule_count"] == 1
    assert client.get("/stats/agent").json()["strategic_count"] == 1
    assert client.post("/reset", json={"agent_name": "agent", "task_id": "A"}).json()["status"] == "ok"
    assert ("agent", "A") not in opt.task_counters
    assert len(opt.strategic_guidelines("agent")) == 1
