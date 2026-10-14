"""Experimental SCOPE v2 controller; execution and model budgets belong to callers.

This controls the published algorithm, not the unpublished research hierarchy.
No model client, network connection, hidden-answer selector, or OpenClaw runtime
is constructed here. See docs/scope-paper-implementation.md for fidelity limits.
"""
from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import math
import os
from pathlib import Path
from types import MappingProxyType
from typing import Any, Awaitable, Callable

DOMAINS = ("tool_usage", "data_validation", "error_handling", "efficiency",
           "analysis_methodology", "safety", "general")
PERSPECTIVES = ("efficiency", "thoroughness")
ROLE_STEP_LIMITS = MappingProxyType({"Planner": 20, "Web Search": 3, "Analyzer": 3, "Browser": 5})
PAPER_URL = "https://arxiv.org/html/2512.15374v2"


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False)


def _text(value: Any) -> str:
    return value if isinstance(value, str) else _json(value)


def _confidence(value: Any) -> float:
    if isinstance(value, bool):
        raise ValueError("Boolean confidence is invalid")
    result = float(value)
    if not math.isfinite(result) or not 0 <= result <= 1:
        raise ValueError("Confidence must be finite and within [0, 1]")
    return result


def _response_json(response: Any) -> dict:
    content = response.content if hasattr(response, "content") else response
    if not isinstance(content, str):
        raise ValueError("The model must return JSON text in response.content")
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Incomplete JSON fence")
        text = "\n".join(lines[1:-1])
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("The classifier must return an object")
    return value


@dataclass(frozen=True)
class PaperConfig:
    candidates: int = 2
    perspectives: tuple[str, ...] = PERSPECTIVES
    quality_frequency: int = 1
    accept_threshold: float = 0.5
    strategic_threshold: float = 0.85
    max_tactical_per_task: int = 20
    max_strategic_per_domain: int = 10
    target_strategic: int = 8
    optimization_iterations: int = 2

    def __post_init__(self):
        for name in ("candidates", "quality_frequency", "max_tactical_per_task",
                     "max_strategic_per_domain", "target_strategic", "optimization_iterations"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if (not self.perspectives or len(set(self.perspectives)) != len(self.perspectives)
                or any(p not in PERSPECTIVES for p in self.perspectives)):
            raise ValueError("Perspectives must be a unique nonempty selection of the published personas")
        _confidence(self.accept_threshold)
        _confidence(self.strategic_threshold)
        if self.accept_threshold > self.strategic_threshold:
            raise ValueError("Acceptance threshold cannot exceed strategic promotion threshold")
        if self.target_strategic > self.max_strategic_per_domain:
            raise ValueError("Optimization target cannot exceed domain capacity")


@dataclass(frozen=True)
class StepTrace:
    index: int
    role: str
    current_system_prompt: str
    model_output: str
    tool_calls: str
    observations: str
    error: str | None


@dataclass(frozen=True)
class PerspectiveResult:
    perspective: str
    task_id: str
    status: str
    response: Any
    steps: tuple[StepTrace, ...]
    learning_events: tuple[dict, ...]
    meta_model_calls: int
    error: str | None = None

    def to_dict(self) -> dict:
        return deepcopy(asdict(self))


class _ObservedModel:
    """Preserve injected budgets even when the upstream SDK catches failures."""
    def __init__(self, model: Any):
        self.model = model
        self.calls = 0
        self.failures: list[Exception] = []

    async def generate(self, messages):
        self.calls += 1
        try:
            return await self.model.generate(messages)
        except Exception as exc:
            self.failures.append(exc)
            raise

    def raise_if_failed(self):
        if self.failures:
            raise self.failures[0]


class _RoleMemory:
    def __init__(self, path: Path):
        self.path = path
        self.rules: dict[str, list[dict]] = {domain: [] for domain in DOMAINS}
        if path.exists():
            data = json.loads(path.read_text())
            if data.get("schema_version") != 1 or not isinstance(data.get("rules"), dict):
                raise ValueError("Invalid experimental strategic memory")
            for domain, rules in data["rules"].items():
                if domain not in DOMAINS or not isinstance(rules, list):
                    raise ValueError("Invalid strategic memory domain")
                self.rules[domain] = [self.validate_rule(rule) for rule in rules]

    @staticmethod
    def validate_rule(rule: Any) -> dict:
        if not isinstance(rule, dict) or not isinstance(rule.get("rule"), str) or not rule["rule"].strip():
            raise ValueError("Strategic rules require nonempty text")
        result = deepcopy(rule)
        result["confidence"] = _confidence(rule.get("confidence", 0.85))
        _json(result)
        return result

    def all_rules(self) -> list[dict]:
        return deepcopy([r for rules in self.rules.values() for r in rules])

    def persist(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(_json({"schema_version": 1, "rules": self.rules}) + "\n")
        os.replace(temporary, self.path)


class ScopePaperGuidance:
    """One task/perspective; role-local advice changes only after observed steps.

    Call prompt() again before each model invocation. The executor owns tool
    orchestration and determines whether an actual environment step errored.
    """
    def __init__(self, controller: ScopePaperController, task_json: str,
                 perspective: str, namespace_hash: str):
        self.controller = controller
        self._task_json = task_json
        self.perspective = perspective
        self.namespace_hash = namespace_hash
        self.task_id = json.loads(task_json)["task_id"]
        self._roles: dict[str, _RoleMemory] = {}
        self._tactical: dict[str, list[dict]] = {}
        self._successful: dict[str, int] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._models: dict[str, _ObservedModel] = {}
        self._steps: list[StepTrace] = []
        self._events: list[dict] = []
        self._closed = False

    def _check_open(self):
        if self._closed:
            raise RuntimeError("This task's guidance is closed")

    def _role(self, role: str) -> _RoleMemory:
        self._check_open()
        if not isinstance(role, str) or not role.strip():
            raise ValueError("A stable nonempty role is required")
        if role not in self._roles:
            role_hash = sha256(role.encode()).hexdigest()
            path = self.controller.directory / self.namespace_hash / self.perspective / role_hash / "strategic.json"
            self._roles[role] = _RoleMemory(path)
            self._tactical[role] = []
            self._successful[role] = 0
            self._locks[role] = asyncio.Lock()
            self._models[role] = _ObservedModel(self.controller.model)
        return self._roles[role]

    @property
    def steps(self) -> tuple[StepTrace, ...]:
        return tuple(self._steps)

    @property
    def learning_events(self) -> tuple[dict, ...]:
        return tuple(deepcopy(self._events))

    def prompt(self, role: str, base_prompt: str) -> str:
        memory = self._role(role)
        if not isinstance(base_prompt, str):
            raise ValueError("base_prompt must be text")
        strategic = [r["rule"] for r in memory.all_rules()]
        tactical = [r["rule"] for r in self._tactical[role]]
        sections = [base_prompt]
        if strategic:
            sections.append("Strategic guidelines (persistent for this role and experiment scope):\n" + "\n".join(strategic))
        if tactical:
            sections.append("Tactical guidelines (this task only):\n" + "\n".join(tactical))
        return "\n\n".join(sections)

    async def observe_step(self, role: str, base_prompt: str, *, model_output: Any = "",
                           tool_calls: Any = "", observations: Any = "", error: Any = None) -> dict:
        memory = self._role(role)
        async with self._locks[role]:
            self._check_open()
            trace = StepTrace(len(self._steps) + 1, role, self.prompt(role, base_prompt),
                              _text(model_output), _text(tool_calls), _text(observations),
                              str(error) if error is not None else None)
            self._steps.append(trace)
            event = {"step": trace.index, "role": role, "analysis": "error" if error is not None else "quality",
                     "accepted": False}
            if error is None:
                self._successful[role] += 1
                if self._successful[role] % self.controller.config.quality_frequency:
                    event["reason"] = "quality-frequency"
                    self._events.append(event)
                    return deepcopy(event)
                if not trace.model_output and not trace.observations:
                    event["reason"] = "no-observed-context"
                    self._events.append(event)
                    return deepcopy(event)
            proposal = await self._synthesize(role, trace)
            self._check_open()
            if proposal is None or not proposal.update_text.strip():
                event["reason"] = "no-guideline"
                self._events.append(event)
                return deepcopy(event)
            classification = await self._classify(role, proposal, memory)
            self._check_open()
            if classification is None:
                event["reason"] = "invalid-classification"
            elif classification["is_duplicate"]:
                event["reason"] = "duplicate"
            elif any(r["rule"] == proposal.update_text.strip()
                     for r in [*memory.all_rules(), *self._tactical[role]]):
                event["reason"] = "duplicate-exact"
            elif classification["confidence"] < self.controller.config.accept_threshold:
                event["reason"] = "below-acceptance-threshold"
            else:
                strategic = (classification["scope"] == "strategic" and
                             classification["confidence"] >= self.controller.config.strategic_threshold)
                effective_scope = "strategic" if strategic else "tactical"
                rule = {"rule": proposal.update_text.strip(), "rationale": proposal.rationale,
                        "confidence": classification["confidence"], "source_task_id": self.task_id}
                if not strategic and len(self._tactical[role]) >= self.controller.config.max_tactical_per_task:
                    event["reason"] = "tactical-task-cap"
                else:
                    if strategic:
                        event["optimization"] = await self._promote(role, memory, classification["domain"], rule)
                    else:
                        self._tactical[role].append(rule)
                    event.update(accepted=True, scope=effective_scope,
                                 classifier_scope=classification["scope"],
                                 confidence=classification["confidence"], guideline=rule["rule"])
            self._events.append(event)
            return deepcopy(event)

    async def _synthesize(self, role: str, trace: StepTrace):
        from scope.synthesizer import GuidelineSynthesizer
        model = self._models[role]
        synthesizer = GuidelineSynthesizer(
            model, candidate_models=[model] * (self.controller.config.candidates - 1),
            use_best_of_n=self.controller.config.candidates > 1,
            use_thoroughness_mode=self.perspective == "thoroughness")
        summary = _json({"model_output": trace.model_output, "tool_calls": trace.tool_calls,
                         "observations": trace.observations})
        common = dict(agent_name=role, agent_role=role,
                      task=json.loads(self._task_json)["instruction"], last_step_summary=summary,
                      current_system_prompt=trace.current_system_prompt,
                      applied_rules=deepcopy(self._tactical[role]))
        if trace.error is not None:
            result = await synthesizer.generate_update_from_error(
                **common, error_type="EnvironmentStepError", error_message=trace.error)
        else:
            result = await synthesizer.generate_update_from_quality(**common)
        model.raise_if_failed()
        return result

    async def _classify(self, role: str, proposal: Any, memory: _RoleMemory) -> dict | None:
        from scope.prompts import CLASSIFICATION_PROMPT
        from scope.memory_optimizer import SimpleMessage
        initial = {"low": .3, "medium": .6, "high": .9}.get(str(proposal.confidence).lower())
        if initial is None:
            try:
                initial = _confidence(proposal.confidence)
            except (TypeError, ValueError):
                return None
        rules = {"strategic": memory.all_rules(), "tactical": deepcopy(self._tactical[role])}
        prompt = CLASSIFICATION_PROMPT.format(
            update_text=proposal.update_text, rationale=proposal.rationale,
            initial_confidence=initial, all_rules_context=_json(rules), allowed_domains=", ".join(DOMAINS))
        response = await self._models[role].generate([SimpleMessage("user", [{"type": "text", "text": prompt}])])
        try:
            result = _response_json(response)
            if not isinstance(result.get("is_duplicate"), bool) or result.get("scope") not in ("strategic", "tactical"):
                return None
            result["confidence"] = _confidence(result["confidence"])
            if result["scope"] == "strategic" and result.get("domain") not in DOMAINS:
                return None
            return result
        except (KeyError, TypeError, ValueError):
            return None

    async def _promote(self, role: str, memory: _RoleMemory, domain: str, rule: dict) -> dict:
        from scope.memory_optimizer import MemoryOptimizer
        rules = memory.rules[domain]
        if any(r["rule"] == rule["rule"] for r in rules):
            return {"triggered": False, "duplicate_exact": True}
        updated = [*deepcopy(rules), rule]
        details = {"triggered": False, "before": len(updated), "after": len(updated)}
        config = self.controller.config
        if len(updated) > config.max_strategic_per_domain:
            details["triggered"] = True
            optimizer = MemoryOptimizer(self._models[role])
            optimized = await optimizer.optimize_rules(
                deepcopy(updated), target_count=config.target_strategic,
                max_iterations=config.optimization_iterations)
            self._models[role].raise_if_failed()
            self._check_open()
            updated = [memory.validate_rule(r) for r in optimized]
            # Published target is aspirational. The released SDK also applies a
            # confidence-ranked hard cap if semantic consolidation is insufficient.
            if len(updated) > config.max_strategic_per_domain:
                details["fallback"] = "confidence-ranked-cap"
                updated = sorted(updated, key=lambda r: r["confidence"], reverse=True)[:config.max_strategic_per_domain]
            details["after"] = len(updated)
        memory.rules[domain] = updated
        self._check_open()
        memory.persist()
        return details


Executor = Callable[[dict, str, ScopePaperGuidance], Awaitable[Any]]


class ScopePaperController:
    def __init__(self, model: Any, directory: Path, *, config: PaperConfig | None = None):
        if not callable(getattr(model, "generate", None)):
            raise ValueError("An explicitly supplied async generate() model is required")
        self.model = model
        self.directory = Path(directory)
        self.config = config or PaperConfig()
        self._namespace_locks: dict[str, asyncio.Lock] = {}

    async def run_task(self, public_task: dict, execute: Executor, *, namespace: dict | str) -> tuple[PerspectiveResult, ...]:
        if not isinstance(public_task, dict) or not isinstance(public_task.get("instruction"), str) or not public_task["instruction"].strip():
            raise ValueError("public_task requires a nonempty instruction")
        if not isinstance(public_task.get("task_id"), str) or not public_task["task_id"].strip():
            raise ValueError("public_task requires a task_id")
        if not namespace or not isinstance(namespace, (dict, str)):
            raise ValueError("An explicit experiment namespace is required")
        task_json = _json(deepcopy(public_task))
        namespace_hash = sha256(_json(namespace).encode()).hexdigest()
        lock = self._namespace_locks.setdefault(namespace_hash, asyncio.Lock())
        async with lock:
            async def run(perspective: str) -> PerspectiveResult:
                guidance = ScopePaperGuidance(self, task_json, perspective, namespace_hash)
                response, error, status = None, None, "completed"
                try:
                    response = json.loads(_json(await execute(json.loads(task_json), perspective, guidance)))
                except Exception as exc:
                    status, error = "error", f"{type(exc).__name__}: {str(exc)[:500]}"
                finally:
                    guidance._closed = True
                return PerspectiveResult(perspective, guidance.task_id, status, response,
                                         guidance.steps, guidance.learning_events,
                                         sum(m.calls for m in guidance._models.values()), error)
            return tuple(await asyncio.gather(*(run(p) for p in self.config.perspectives)))
