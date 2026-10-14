"""Loopback sidecar for scoped, reversible SCOPE learning (protocol 3)."""
import ipaddress
import json
import logging
import secrets
import time
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, model_validator

from config import ServerConfig
from prompts import EVOLVECLAW_DOMAINS, get_custom_prompts
from memory_store import MemoryStore, RevisionConflict
from task_optimizer import TaskScopedOptimizer
from scope.models import create_litellm_model
from scope.models.openai_adapter import OpenAIAdapter
from scope.models.anthropic_adapter import AnthropicAdapter

logger = logging.getLogger("evolveclaw.server")
cfg = ServerConfig()
app = FastAPI(title="EvolveClaw SCOPE Server", version="0.5.0")
memory_store = MemoryStore(cfg.SCOPE_DATA_PATH, cfg.SCOPE_MAX_STRATEGIC_PER_DOMAIN)
optimizer = None
start_time = time.time()


@app.middleware("http")
async def local_gateway_only(request: Request, call_next):
    host = request.client.host if request.client else ""
    try:
        local = ipaddress.ip_address(host).is_loopback
    except ValueError:
        local = host in ("localhost", "testclient")
    if request.headers.get("origin") or (not local and not cfg.AUTH_TOKEN):
        return JSONResponse({"detail": "Use the authenticated Gateway controls"}, status_code=403)
    if cfg.AUTH_TOKEN and not secrets.compare_digest(request.headers.get("authorization", ""), f"Bearer {cfg.AUTH_TOKEN}"):
        return JSONResponse({"detail": "Sidecar authorization required"}, status_code=401)
    return await call_next(request)


def _create_model(provider, model_name, api_key, base_url):
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if base_url:
        kwargs["base_url"] = base_url
    if provider == "anthropic":
        from anthropic import AsyncAnthropic
        return AnthropicAdapter(AsyncAnthropic(**kwargs), model=model_name)
    if provider == "openai":
        from openai import AsyncOpenAI
        return OpenAIAdapter(AsyncOpenAI(**kwargs), model=model_name)
    if provider == "litellm":
        return create_litellm_model(model_name, api_key=api_key, base_url=base_url)
    raise ValueError("Unsupported SCOPE provider")


def init_optimizer(provider, model_name, api_key, base_url):
    global optimizer
    model = _create_model(provider, model_name, api_key, base_url)
    rates = {"input": cfg.INPUT_COST_PER_MILLION, "output": cfg.OUTPUT_COST_PER_MILLION}
    optimizer = TaskScopedOptimizer(synthesizer_model=model, exp_path=cfg.SCOPE_DATA_PATH,
        memory_store=memory_store, estimate_usage=cfg.ESTIMATE_USAGE, cost_rates=rates,
        enable_quality_analysis=cfg.SCOPE_QUALITY_ANALYSIS,
        quality_analysis_frequency=cfg.SCOPE_QUALITY_FREQUENCY,
        auto_accept_threshold=cfg.SCOPE_ACCEPT_THRESHOLD,
        strategic_confidence_threshold=cfg.SCOPE_STRATEGIC_THRESHOLD,
        max_rules_per_task=cfg.SCOPE_MAX_RULES_PER_TASK,
        max_strategic_rules_per_domain=cfg.SCOPE_MAX_STRATEGIC_PER_DOMAIN,
        synthesis_mode=cfg.SCOPE_SYNTHESIS_MODE, custom_prompts=get_custom_prompts(),
        custom_domains=EVOLVECLAW_DOMAINS)


if cfg.has_explicit_llm_config():
    init_optimizer(cfg.SCOPE_PROVIDER or "openai", cfg.SCOPE_MODEL or "gpt-4o-mini",
                   cfg.SCOPE_API_KEY, cfg.SCOPE_BASE_URL)


class BoundedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def bounded(self):
        if len(json.dumps(self.model_dump(), allow_nan=False)) > 128000:
            raise ValueError("Request exceeds the bounded trace size")
        return self


class Scope(BoundedRequest):
    audience_key: str = Field(min_length=1, max_length=256)
    project_key: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def valid_scope(self):
        if any(not v.strip() or v == "*" for v in (self.audience_key, self.project_key)):
            raise ValueError("Trusted, concrete scope is required")
        return self


class StepRequest(BoundedRequest):
    agent_name: str = Field(min_length=1, max_length=200)
    scope: Scope | None = None
    agent_role: str = Field(default="OpenClaw AI Assistant", max_length=1000)
    task: str = Field(min_length=1, max_length=20000)
    model_output: str | None = Field(default=None, max_length=48000)
    tool_calls: str | None = Field(default=None, max_length=24000)
    observations: str | None = Field(default=None, max_length=24000)
    error: str | None = Field(default=None, max_length=4000)
    current_system_prompt: str = Field(default="", max_length=64000)
    task_id: str | None = Field(default=None, max_length=256)
    conversation_history: str | None = Field(default=None, max_length=12000)


class ResetRequest(BoundedRequest):
    agent_name: str = Field(min_length=1, max_length=200)
    scope: Scope | None = None
    task_id: str | None = Field(default=None, max_length=256)


class ConfigureRequest(BoundedRequest):
    provider: Literal["openai", "anthropic", "litellm"]
    model: str = Field(min_length=1, max_length=200)
    api_key: str = Field(max_length=2000)
    base_url: str | None = Field(default=None, max_length=2000)


class MemoryQuery(BoundedRequest):
    agent_name: str = Field(min_length=1, max_length=200)
    scope: Scope
    operation: Literal["list", "history", "detail", "usage", "status", "export"] = "list"
    args: dict = Field(default_factory=dict)
    authorize_legacy: bool = False


class MemoryMutation(BoundedRequest):
    agent_name: str = Field(min_length=1, max_length=200)
    scope: Scope
    operation: Literal["disable", "restore", "assign_scope", "pause", "resume", "promote"]
    args: dict = Field(default_factory=dict)
    expected_revision: int = Field(ge=0)
    authorize_legacy: bool = False


class OutcomeRequest(BoundedRequest):
    agent_name: str = Field(min_length=1, max_length=200)
    scope: Scope
    task_id: str | None = Field(default=None, max_length=256)
    evidence_id: str | None = Field(default=None, max_length=100)
    rule_ids: list[str] = Field(default_factory=list, max_length=100)
    result: Literal["success", "failure", "unknown"]
    source: Literal["fixture", "user_feedback", "external_verifier", "agent_run"]
    details: dict = Field(default_factory=dict)


def store():
    # Supports isolated test/embedding optimizers without a separate singleton database.
    return optimizer.memory_store if optimizer is not None else memory_store


def scope_dict(scope):
    return scope.model_dump() if scope else None


def scoped_query(audience_key, project_key):
    if audience_key is None and project_key is None:
        return None
    if audience_key is None or project_key is None:
        raise HTTPException(422, "Both trusted audience and project keys are required")
    try:
        return Scope(audience_key=audience_key, project_key=project_key).model_dump()
    except ValueError:
        raise HTTPException(422, "Invalid scope")


def memory_error(exc):
    if isinstance(exc, RevisionConflict):
        return HTTPException(409, str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(403, str(exc))
    if isinstance(exc, KeyError):
        return HTTPException(404, "Record not found in this scope")
    return HTTPException(422, str(exc))


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.5.0", "protocol_version": 3, "configured": optimizer is not None}


@app.post("/configure")
async def configure(req: ConfigureRequest):
    if cfg.has_explicit_llm_config() and optimizer is not None:
        return {"status": "skipped", "reason": "server has explicit credentials"}
    try:
        init_optimizer(req.provider, req.model, req.api_key, req.base_url)
    except Exception as exc:
        logger.warning("Model configuration failed (%s)", type(exc).__name__)
        return {"status": "error", "reason": "Model configuration failed"}
    return {"status": "ok"}


@app.get("/rules/{agent_name}")
async def get_rules(agent_name: str, audience_key: str | None = None, project_key: str | None = None):
    scope = scoped_query(audience_key, project_key)
    result = {"protocol_version": 3, "rules": "", "rule_count": 0, "guidelines": [],
              "configured": optimizer is not None, "revision": 0, "paused": False}
    if not scope:
        return result
    snapshot = store().guidance(agent_name, scope)
    guidelines = snapshot["guidelines"]
    return {**result, "rules": "\n".join(f"- {g}" for g in guidelines), "rule_count": len(guidelines),
            "guidelines": guidelines, "revision": snapshot["revision"], "paused": snapshot["paused"]}


@app.post("/step")
async def on_step_complete(req: StepRequest):
    scope = scope_dict(req.scope)
    base = {"protocol_version": 3, "guideline": None, "guideline_type": None, "guideline_id": None,
            "evidence_id": None, "revision": store().revision(req.agent_name, scope) if scope else 0}
    if not scope:
        return {**base, "skipped": True, "reason": "trusted scope unavailable"}
    if optimizer is None:
        return {**base, "skipped": True, "reason": "optimizer not configured yet"}
    if store().paused(req.agent_name, scope):
        return {**base, "skipped": True, "reason": "learning paused"}
    if not any((req.model_output, req.error, req.observations)):
        return {**base, "skipped": True, "reason": "no context provided"}
    output = req.model_output or ""
    if req.conversation_history:
        output = (f"## Recent conversation history:\n{req.conversation_history[-4000:]}\n\n"
                  f"## Current turn response:\n{output[-12000:]}")
    try:
        result = await optimizer.on_step_complete(agent_name=req.agent_name, scope=scope,
            agent_role=req.agent_role, task=req.task[:2000], model_output=output[-18000:] or None,
            tool_calls=req.tool_calls[-12000:] if req.tool_calls else None,
            observations=req.observations[-12000:] if req.observations else None,
            error=Exception(req.error[:1000]) if req.error else None,
            current_system_prompt=req.current_system_prompt[:32000], task_id=req.task_id, truncate_context=False)
    except Exception as exc:
        logger.warning("SCOPE analysis failed (%s)", type(exc).__name__)
        return {**base, "revision": store().revision(req.agent_name, scope), "skipped": True,
                "reason": "memory changed during analysis" if isinstance(exc, RevisionConflict) else "analysis failed"}
    if not result:
        return {**base, "revision": store().revision(req.agent_name, scope), "skipped": True, "reason": "no guideline generated"}
    return {**base, "guideline": result.text, "guideline_type": result.type, "guideline_id": result.rule_id,
            "evidence_id": result.evidence_id, "revision": result.revision, "skipped": False}


@app.post("/reset")
async def reset(req: ResetRequest):
    scope = scope_dict(req.scope)
    if scope:
        if optimizer is not None:
            await optimizer.reset_tactical(agent_name=req.agent_name, task_id=req.task_id, scope=scope)
        else:
            store().reset_tactical(req.agent_name, scope, req.task_id)
    return {"status": "ok", "revision": store().revision(req.agent_name, scope) if scope else 0}


@app.get("/stats/{agent_name}")
async def stats(agent_name: str, audience_key: str | None = None, project_key: str | None = None):
    scope = scoped_query(audience_key, project_key)
    if not scope:
        return {"protocol_version": 3, "strategic_count": 0, "total_steps_analyzed": 0,
                "guidelines_synthesized": 0, "recent_synthesis_rate": 0, "uptime_seconds": time.time()-start_time}
    snapshot = store().query(agent_name, scope, "status", {"limit": 200})
    learned, steps = snapshot["activity"]["accepted"], snapshot["activity"]["steps"]
    return {**snapshot, "strategic_count": len([r for r in store().active_rules(agent_name, scope) if r["type"] == "strategic"]),
            "total_steps_analyzed": steps, "guidelines_synthesized": learned,
            "recent_synthesis_rate": learned / steps if steps else 0, "uptime_seconds": time.time()-start_time}


@app.post("/memory/query")
async def query(req: MemoryQuery):
    try:
        return store().query(req.agent_name, scope_dict(req.scope), req.operation, req.args, req.authorize_legacy)
    except (ValueError, PermissionError, KeyError) as exc:
        raise memory_error(exc)


@app.post("/memory/mutate")
async def mutate(req: MemoryMutation):
    try:
        return store().mutate(req.agent_name, scope_dict(req.scope), req.operation, req.args,
                              req.expected_revision, req.authorize_legacy)
    except (ValueError, PermissionError, KeyError) as exc:
        raise memory_error(exc)


@app.post("/outcome")
async def outcome(req: OutcomeRequest):
    try:
        return store().record_outcome(req.agent_name, scope_dict(req.scope), req.task_id, req.result,
                                     req.source, req.evidence_id, req.rule_ids, req.details)
    except (ValueError, PermissionError, KeyError) as exc:
        raise memory_error(exc)


if __name__ == "__main__":
    uvicorn.run(app, host=cfg.HOST, port=cfg.PORT, log_level="info")
