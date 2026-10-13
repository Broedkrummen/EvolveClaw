"""Explicit, budgeted fixture evaluation of actual learning implementations.

Planning never creates a model or reads a credential. Execution uses only the
advertised FakeWorld tools; scorer keys never reach an assistant or learner.
This evaluates sidecar algorithms with a small fixture agent, not OpenClaw's
native chat/hook integration or the paper's unpublished benchmark harness and
exact research prompts.
"""
from __future__ import annotations

import argparse
import asyncio
from copy import deepcopy
from dataclasses import asdict, replace
from hashlib import sha256
import importlib.metadata
import importlib.util
import inspect
import json
from pathlib import Path
from statistics import mean
import subprocess
import sys
from time import perf_counter
from typing import Any

from .reporting import _metric_rows, paired_cluster_comparison
from .scenarios import Feedback, Rollback, Task, pilot_sequences, planned_manifest, validate_manifest
from .scoring import score_response

CONDITIONS = ("learning-off", "repaired-v0.2", "improved", "scope_sdk_reference", "scope_paper_k2_n2")
HISTORICAL_V02_COMMIT = "03ecaf210c412ee5ae685d8282d3f7e5ed634765"
SDK_VERSION = "0.1.3"
REPOSITORY = Path(__file__).resolve().parents[1]
# Both application conditions use the shipped sidecar defaults rather than the
# importing process's .env. The historical source archive records these inputs.
APPLICATION_SETTINGS = {
    "enable_quality_analysis": True, "quality_analysis_frequency": 3,
    "auto_accept_threshold": "medium", "strategic_confidence_threshold": .85,
    "max_rules_per_task": 20, "max_strategic_rules_per_domain": 10,
    "synthesis_mode": "efficiency",
}


def _write(path: Path, value: Any):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def _module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load evaluation source: {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _archive_historical(directory: Path, repository: Path = REPOSITORY):
    """Read exact immutable repair files; never substitute the current optimizer."""
    directory.mkdir(parents=True, exist_ok=False)
    sources = {}
    for relative in ("server/task_optimizer.py", "server/prompts.py", "server/config.py",
                     "server/server.py", "plugin/src/index.ts"):
        try:
            data = subprocess.run(["git", "show", f"{HISTORICAL_V02_COMMIT}:{relative}"],
                                  cwd=repository, check=True, capture_output=True).stdout
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ValueError("Genuine repaired-v0.2 source is unavailable; no baseline was substituted") from exc
        target = directory / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        sources[relative] = sha256(data).hexdigest()
    return {"commit": HISTORICAL_V02_COMMIT, "source_sha256": sources,
            "execution": "isolated-exact-historical-optimizer-and-prompts",
            "native_openclaw_hooks_executed": False}


def _current_modules():
    # task_optimizer imports the adjacent memory_store. Do not import server or
    # config: they load .env and can eagerly construct a live provider client.
    server = str(REPOSITORY / "server")
    if server not in sys.path:
        sys.path.insert(0, server)
    import task_optimizer
    return task_optimizer, _module(REPOSITORY / "server/prompts.py", "evaluation_current_prompts")


class _ObservedModel:
    """Do not let upstream's exception handling conceal a failed paid call."""
    def __init__(self, model):
        self.delegate = model
        self.model = getattr(model, "model", None)
        self.errors: list[Exception] = []

    async def generate(self, messages):
        try:
            return await self.delegate.generate(messages)
        except Exception as exc:
            self.errors.append(exc)
            raise

    def check(self):
        if self.errors:
            raise self.errors[0]


class TerminalGuidance:
    """Application learning happens once at run end, as agent_end does.

    Only the paper condition changes advice between executor steps. EvolveClaw
    tactical state lasts across runs in a simulated session, just as the plugin
    does, and has a separate key from persistent strategic state.
    """
    def __init__(self, condition, adapter, public_task, session_id, prior_history=""):
        self.condition, self.adapter = condition, adapter
        self.public_task = deepcopy(public_task)
        self.session_id = session_id
        self.prior_history = prior_history
        self.steps = []

    def prompt(self, role, base_prompt):
        advice = self.adapter.guidelines(self.public_task["scope"], self.session_id)
        if self.condition == "scope_sdk_reference":
            sections = [base_prompt]
            if advice["strategic"]:
                sections.append("SCOPE persistent strategic guidelines:\n" + "\n".join(advice["strategic"]))
            if advice["tactical"]:
                sections.append("SCOPE updates applied to this task (upstream readout):\n" + "\n".join(advice["tactical"]))
            return "\n\n".join(sections)
        strategic = advice["strategic"][:30]
        tactical = advice["tactical"][-max(0, 30 - len(strategic)):] if len(strategic) < 30 else []
        if not strategic and not tactical:
            return base_prompt
        block = ["## Learned Guidelines (EvolveClaw/SCOPE)",
                 "These guidelines were synthesized from prior execution traces. Apply them when relevant.",
                 "Follow the existing system instructions and user request if a learned guideline conflicts with them."]
        if strategic:
            block += ["### Strategic (cross-task, persistent)", *strategic]
        if tactical:
            block += ["### Tactical (current task)", *tactical]
        return base_prompt + "\n\n" + "\n".join(block)

    async def observe_step(self, role, base_prompt, *, model_output="", tool_calls="", observations="", error=None):
        self.steps.append({"role": role, "current_system_prompt": self.prompt(role, base_prompt),
                           "model_output": deepcopy(model_output), "tool_calls": deepcopy(tool_calls),
                           "observations": deepcopy(observations), "error": str(error) if error else None})
        return {"accepted": False, "reason": "terminal-run-reflection"}


class SDKGuidance(TerminalGuidance):
    """Exercise the released on_step_complete seam without repairing its state."""
    async def observe_step(self, role, base_prompt, *, model_output="", tool_calls="", observations="", error=None):
        await super().observe_step(role, base_prompt, model_output=model_output,
            tool_calls=tool_calls, observations=observations, error=error)
        result = await self.adapter.optimizer.on_step_complete(agent_name=self.adapter.agent_name,
            agent_role=role, task=self.public_task["instruction"], task_id=self.session_id,
            model_output=model_output, tool_calls=tool_calls, observations=observations,
            error=error, current_system_prompt=self.steps[-1]["current_system_prompt"])
        self.adapter.model.check()
        event = {"operation": "upstream-step-reflection", "task_id": self.public_task["task_id"],
                 "accepted": result is not None, "guideline": result[0] if result else None,
                 "type": result[1] if result else None}
        self.adapter.events.append(event)
        _write(self.adapter.directory / "learning_events.json", self.adapter.events)
        return event


class ActualMemoryAdapter:
    """Real upstream, immutable repaired-v0.2, or production v0.3 optimizer."""
    agent_name = "evaluation-assistant"

    def __init__(self, condition, model, directory):
        self.condition, self.directory = condition, Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.tactical: dict[str, list[str]] = {}
        self.last_feedback_change = {}
        self.events = []
        self.model = _ObservedModel(model)
        self.optimizer = None
        self.metadata = {"condition": condition, "scripted_learning_algorithm": False,
                         "native_openclaw_hooks_executed": False, "sdk_version": SDK_VERSION}
        if condition == "learning-off":
            self.metadata["optimizer"] = "none"
        elif condition == "scope_sdk_reference":
            from scope import SCOPEOptimizer
            self.optimizer = SCOPEOptimizer(synthesizer_model=self.model, exp_path=str(self.directory / "sdk-state"))
            self.metadata.update(optimizer="scope.SCOPEOptimizer", unmodified_upstream_defaults=True,
                                 task_counter_reset_supported=False, rollback_supported=False,
                reflection_boundary="each-executor-step", applied_rules_readout="upstream-private-read-helper",
                default_configuration={name: parameter.default for name, parameter in inspect.signature(SCOPEOptimizer).parameters.items()
                    if parameter.default is not inspect.Parameter.empty},
                source_sha256={"optimizer": sha256(Path(inspect.getsourcefile(SCOPEOptimizer)).read_bytes()).hexdigest()})
        elif condition == "repaired-v0.2":
            archive = self.directory / "historical-source"
            self.metadata["historical_source"] = _archive_historical(archive)
            name = sha256(str(archive).encode()).hexdigest()[:16]
            module = _module(archive / "server/task_optimizer.py", f"evaluation_v02_optimizer_{name}")
            prompts = _module(archive / "server/prompts.py", f"evaluation_v02_prompts_{name}")
            self.optimizer = module.TaskScopedOptimizer(synthesizer_model=self.model,
                exp_path=str(self.directory / "sdk-state"), **APPLICATION_SETTINGS,
                custom_prompts=prompts.get_custom_prompts(), custom_domains=prompts.EVOLVECLAW_DOMAINS)
            self.metadata.update(optimizer="historical.TaskScopedOptimizer", rollback_supported=False,
                                 application_defaults=APPLICATION_SETTINGS)
        elif condition == "improved":
            module, prompts = _current_modules()
            prices = getattr(model, "config", None)
            self.optimizer = module.TaskScopedOptimizer(synthesizer_model=self.model,
                exp_path=str(self.directory / "scoped-state"), **APPLICATION_SETTINGS,
                cost_rates={"input": prices.input_usd_per_million, "output": prices.output_usd_per_million} if prices else None,
                custom_prompts=prompts.get_custom_prompts(), custom_domains=prompts.EVOLVECLAW_DOMAINS)
            self.metadata.update(optimizer="task_optimizer.TaskScopedOptimizer", rollback_supported=True,
                application_defaults=APPLICATION_SETTINGS,
                source_sha256={file: sha256((REPOSITORY / file).read_bytes()).hexdigest() for file in
                               ("server/task_optimizer.py", "server/memory_store.py", "server/prompts.py")})
        else:
            raise ValueError(f"Unsupported terminal learning condition: {condition}")
        _write(self.directory / "adapter_metadata.json", self.metadata)

    def guidelines(self, scope, session_id):
        if self.optimizer is None:
            return {"strategic": [], "tactical": []}
        if self.condition == "improved":
            strategic = self.optimizer.strategic_guidelines(self.agent_name, scope)
        elif self.condition == "repaired-v0.2":
            strategic = self.optimizer.strategic_guidelines(self.agent_name)
        else:
            strategic = [rule["rule"] for domain in self.optimizer.strategic_store.get_strategic_rules(self.agent_name).values()
                         for rule in domain]
            applied = [r["rule"] for r in self.optimizer._get_applied_rules(session_id, self.agent_name)]
            return {"strategic": strategic, "tactical": [text for text in applied if text not in strategic]}
        return {"strategic": strategic, "tactical": list(self.tactical.get(session_id, []))}

    async def finish(self, guidance, response, *, feedback=False):
        if self.optimizer is None:
            return {"accepted": False, "reason": "learning-disabled"}
        scope = deepcopy(guidance.public_task["scope"])
        steps = guidance.steps
        # This aggregate is public execution context only. No scoring result,
        # answer key, fixture outcome label, or evaluator success is passed here.
        tool_calls = json.dumps([s["tool_calls"] for s in steps if s["tool_calls"]], allow_nan=False)
        observations = json.dumps([s["observations"] for s in steps if s["observations"]], allow_nan=False)
        error = next((s["error"] for s in reversed(steps) if s["error"]), None)
        output = json.dumps(response, allow_nan=False)
        if guidance.prior_history:
            label = "Recent conversation history (previous turns)" if self.condition == "repaired-v0.2" else "Recent conversation history"
            output = (f"## {label}:\n{guidance.prior_history[-4000:]}\n\n"
                      f"## Current turn response:\n{output[:12000]}")
        kwargs = dict(agent_name=self.agent_name, agent_role="OpenClaw AI Assistant",
            task=guidance.public_task["instruction"][:2000], task_id=guidance.session_id,
            model_output=output[:18000],
            tool_calls=tool_calls[:12000], observations=observations[:12000],
            error=RuntimeError(error[:1000]) if error else None,
            current_system_prompt=(steps[-1]["current_system_prompt"] if steps else "")[:32000])
        if self.condition != "scope_sdk_reference":
            # The repaired sidecar explicitly disables SDK's 200-character cut.
            kwargs["truncate_context"] = False
        if self.condition == "improved":
            kwargs["scope"] = scope
        result = await self.optimizer.on_step_complete(**kwargs)
        self.model.check()
        if result and result[1] == "tactical":
            self.tactical.setdefault(guidance.session_id, []).append(result[0])
            self.tactical[guidance.session_id] = self.tactical[guidance.session_id][-30:]
        event = {"operation": "feedback" if feedback else "terminal-reflection", "scope": scope,
                 "task_id": guidance.public_task["task_id"], "session_id": guidance.session_id,
                 "accepted": result is not None,
                 "guideline": result[0] if result else None, "type": result[1] if result else None}
        if self.condition == "improved" and result:
            event["rule_id"] = result.rule_id
            if feedback:
                snapshot = self.optimizer.memory_store.query(self.agent_name, scope)
                # The authored owner request targets the change from their last
                # feedback turn. It does not choose a rule using a scored error.
                history = next((h for h in snapshot["history"] if h["operation"] == "learn"
                                and result.rule_id in h["rule_ids"]), None)
                if history:
                    self.last_feedback_change[guidance.session_id] = history["id"]
        self.events.append(event)
        _write(self.directory / "learning_events.json", self.events)
        return event

    def rollback(self, scope, session_id):
        if self.condition != "improved":
            return {"supported": False, "changed": False, "reason": "condition-has-no-rollback"}
        history_id = self.last_feedback_change.get(session_id)
        if not history_id:
            return {"supported": True, "changed": False, "reason": "no-accepted-feedback-change"}
        store = self.optimizer.memory_store
        snapshot = store.mutate(self.agent_name, scope, "restore", {"history_id": history_id},
                                store.revision(self.agent_name, scope))
        # Management handlers invalidate in-memory tactical injection too.
        self.tactical[session_id] = []
        event = {"supported": True, "changed": True, "operation": "owner-history-undo",
                 "history_id": history_id, "revision": snapshot["revision"]}
        self.events.append(event)
        _write(self.directory / "learning_events.json", self.events)
        return event


def _session(sequence_id, scope):
    return sha256(json.dumps([sequence_id, scope], sort_keys=True).encode()).hexdigest()


def selected_sequences(split, sequence_limit=None):
    if split not in ("pilot", "development", "heldout"):
        raise ValueError("Unknown evaluation split")
    sequences = [s for s in pilot_sequences() if s.split == split]
    if not sequences:
        raise ValueError(f"{split} has planned authoring slots only; no executable fixtures")
    if sequence_limit is not None:
        if isinstance(sequence_limit, bool) or sequence_limit < 1:
            raise ValueError("sequence_limit must be positive")
        sequences = sequences[:sequence_limit]
    return sequences


def evaluation_plan(config, *, split="pilot", conditions=CONDITIONS, repetitions=1, sequence_limit=None):
    if not conditions or len(set(conditions)) != len(conditions) or any(c not in CONDITIONS for c in conditions):
        raise ValueError("Select unique supported conditions")
    if isinstance(repetitions, bool) or not isinstance(repetitions, int) or repetitions < 1:
        raise ValueError("repetitions must be a positive integer")
    sequences = selected_sequences(split, sequence_limit)
    validate_manifest(planned_manifest())
    config.validate(require_opt_in=False)
    public_count = sum(sum(isinstance(e, (Task, Feedback)) for e in s.events) for s in sequences)
    return {"schema_version": 1, "mode": "plan", "api_calls": 0,
            "spending_authorized_by_plan": False, "efficacy_evidence": False,
            "split": split, "conditions": list(conditions), "repetitions": repetitions,
            "sequence_ids": [s.sequence_id for s in sequences],
            "sequence_runs": len(sequences) * len(conditions) * repetitions,
            "family_clusters": len({s.cluster_id for s in sequences}),
            "assistant_runs_before_tool_continuations": public_count * repetitions *
                sum(2 if c == "scope_paper_k2_n2" else 1 for c in conditions),
            "model_configuration": asdict(config),
            "baseline_commit": HISTORICAL_V02_COMMIT,
            "memory_namespace_policies": {
                "repaired-v0.2": "agent-wide-strategic; session-tactical",
                "improved": "trusted-user-project-scoped-strategic; session-tactical",
                "scope_sdk_reference": "agent-wide-strategic; upstream-task-applied-state",
                "scope_paper_k2_n2": "sequence-only-experiment; role-and-perspective; no-user-project-routing"},
            "cost_estimate": {"status": "unknown", "amount": None,
                              "reason": "Learning proposals, continuation steps, and consolidation vary by run"},
            "execution_limits": ["Fixture agent, not native OpenClaw runtime",
                "Only the 20 authored pilot sequences are executable",
                "Paper K2/N2 and role-step hierarchy with authored executor prompts, not an exact benchmark reproduction",
                "Paper primary response is preselected efficiency; no gold-answer best-of-perspectives selector",
                "No evaluator success labels are supplied to any learner"]}


def _condition_reports(results, conditions, usage):
    reports = {}
    for condition in conditions:
        condition_results = [row for row in results if row["condition"] == condition]
        records = [record for row in condition_results for record in row["records"]]
        categories = sorted({row["category"] for row in condition_results})
        requests = [call for call in usage["calls"] if call["stage"].startswith(condition + ":")]
        elapsed = [record["elapsed_seconds"] for record in records]
        reports[condition] = {"adapter": "actual-learning-algorithm", "metrics": _metric_rows(records),
            "by_category": {category: _metric_rows([record for row in condition_results if row["category"] == category
                                                     for record in row["records"]]) for category in categories},
            "usage": {"requests": len(requests),
                      "assistant_requests": sum(":assistant" in call["stage"] for call in requests),
                      "learning_requests": sum(call["stage"].endswith(":learning") for call in requests),
                      "unknown_usage_requests": sum(call["usage_status"] == "unknown" for call in requests),
                      "accounted_budget_usd": sum(call["accounted_cost_usd"] for call in requests)},
            "latency_seconds": {"task_runs": len(elapsed), "mean": mean(elapsed), "maximum": max(elapsed)}}
    return reports


async def _run_sequence(sequence, condition, directory, model, max_steps):
    from .real_agent import FakeWorldModelAgent
    from .scope_paper import PaperConfig, ScopePaperController
    directory.mkdir(parents=True, exist_ok=False)
    learner_model = model.for_stage(f"{condition}:learning")
    if condition == "scope_paper_k2_n2":
        adapter = None
        controller = ScopePaperController(learner_model, directory / "memory",
                                          config=PaperConfig(candidates=2, perspectives=("efficiency", "thoroughness")))
        _write(directory / "adapter_metadata.json", {"condition": condition, "controller": "ScopePaperController",
                "candidates": 2, "perspectives": ["efficiency", "thoroughness"],
                "primary_perspective": "efficiency", "full_paper_benchmark_reproduction": False,
                "hierarchical_executor": True,
                "memory_namespace_policy": "sequence-only-experiment; separate-role-and-perspective; no-user-project-routing",
                "role_invocation_step_limits": {"Planner": 20, "Web Search": 3, "Analyzer": 3, "Browser": 5},
                "executor_prompts": "authored-for-FakeWorld-not-original-research-prompts"})
    else:
        adapter = ActualMemoryAdapter(condition, learner_model, directory / "memory")
        controller = None
    records, public_events, trace = [], [], []
    failed_before, corrected, history = set(), set(), {}
    for index, event in enumerate(sequence.events):
        scope = event.scope.to_dict()
        session_id = _session(sequence.sequence_id, scope)
        if isinstance(event, Rollback):
            public = {"event": "rollback", "scope": scope, "text": event.text}
            result = adapter.rollback(scope, session_id) if adapter else {
                "supported": False, "changed": False, "reason": "published-controller-has-no-rollback"}
            public_events.append(public)
            trace.append({"event": "rollback", "request": public, "memory": result})
            continue
        feedback = isinstance(event, Feedback)
        if feedback:
            public = {"event": "feedback", **event.public_request()}
            # Public user correction is supplied verbatim. No private fixture
            # expectation is included, including on deliberately wrong feedback.
            from .scenarios import Scope
            task = Task(f"{sequence.sequence_id}.feedback-{index}", event.text,
                        Scope(**scope), (), event.topic, "feedback")
            corrected.add((scope["audience_key"], scope["project_key"], event.topic))
        else:
            task = event
            public = {"event": "task", **task.public_request()}
        public_events.append(public)
        started = perf_counter()
        if controller:
            callbacks = []
            async def execute(public_task, perspective, guidance):
                # A fresh fixture agent and bind create a different FakeWorld
                # for every parallel callback. Neither world nor mutable trace
                # is shared with a sibling perspective, run, or condition.
                agent = FakeWorldModelAgent(model.for_stage(f"{condition}:assistant:{perspective}"),
                                           max_steps=max_steps, hierarchical=True)
                response = await agent.bind(deepcopy(task))(deepcopy(public_task), perspective, guidance)
                callbacks.append({"perspective": perspective, "runs": deepcopy(agent.last_runs)})
                return response
            # Experiment isolation is required, but the published paper does
            # not add EvolveClaw's user/project memory admission or routing.
            # Scope labels remain normal public task context for the model.
            perspectives = await controller.run_task(task.public_request(), execute,
                                                       namespace={"sequence_id": sequence.sequence_id})
            primary = next(p for p in perspectives if p.perspective == "efficiency")
            if any(p.status != "completed" for p in perspectives):
                _write(directory / "incomplete_perspectives.json", [p.to_dict() for p in perspectives])
                raise RuntimeError("Paper execution failed; no complete-condition comparison is available")
            response = primary.response if isinstance(primary.response, dict) else {}
            details = {"perspectives": [p.to_dict() for p in perspectives], "callbacks": callbacks,
                       "response_selection": "fixed-efficiency-before-scoring"}
            learning = None
        else:
            guidance_type = SDKGuidance if condition == "scope_sdk_reference" else TerminalGuidance
            actual_task_id = task.task_id if condition == "scope_sdk_reference" else session_id
            prior = history.get(session_id, [])
            prior_history = "\n".join(f"[{role}]: {content[:300]}" for role, content in prior[-10:])
            guidance = guidance_type(condition, adapter, task.public_request(), actual_task_id, prior_history)
            agent = FakeWorldModelAgent(model.for_stage(f"{condition}:assistant"), max_steps=max_steps)
            response = await agent.bind(deepcopy(task))(task.public_request(), "default", guidance)
            learning = await adapter.finish(guidance, response, feedback=feedback) if condition != "scope_sdk_reference" else {
                "accepted": False, "reason": "already-observed-each-executor-step"}
            details = {"steps": deepcopy(guidance.steps), "runs": deepcopy(agent.last_runs), "memory": learning}
        history.setdefault(session_id, []).extend([("user", task.instruction), ("assistant", json.dumps(response))])
        elapsed = perf_counter() - started
        row = {"event": "feedback" if feedback else "task", "request": public, "response": response, **details}
        if not feedback:
            key = sequence.scoring_keys[task.task_id]
            score = score_response(response, key)
            mistake_context = (scope["audience_key"], scope["project_key"], key.mistake_key)
            eligible = mistake_context in failed_before and mistake_context in corrected
            record = {"task_id": task.task_id, "phase": task.phase, **score,
                      "repeated_mistake_eligible": eligible, "repeated_mistake": bool(eligible and not score["success"]),
                      "elapsed_seconds": elapsed}
            records.append(record)
            row["scoring"] = record
            if not score["success"] and key.mistake_key:
                failed_before.add(mistake_context)
            if controller:
                row["perspective_scoring"] = {p.perspective: score_response(
                    p.response if isinstance(p.response, dict) else {}, key) for p in perspectives}
        trace.append(row)
    _write(directory / "public_requests.json", public_events)
    # This is explicitly scorer-only output; the assistant has no filesystem
    # capability. It must never become a future retrieval or learning source.
    _write(directory / "scorer_only_trace.json", trace)
    return {"sequence_id": sequence.sequence_id, "family_id": sequence.family_id,
            "cluster_id": sequence.cluster_id, "category": sequence.category, "split": sequence.split,
            "condition": condition, "adapter": "actual-learning-algorithm",
            "surrogate": False, "future_success_rate": mean(r["success"] for r in records if r["phase"] == "future"),
            "records": records}


async def run_model_evaluation(config, output: Path, *, split="pilot", conditions=CONDITIONS,
                               repetitions=1, sequence_limit=None, max_steps=5,
                               transport=None, offline_mock=False):
    """Execution requires opt-in, except explicitly marked injected mock mode."""
    from .models import BudgetedModel
    plan = evaluation_plan(config, split=split, conditions=conditions, repetitions=repetitions,
                           sequence_limit=sequence_limit)
    if offline_mock and transport is None:
        raise ValueError("offline_mock requires an injected transport")
    if transport is not None and not offline_mock:
        raise ValueError("Injected transports must be explicitly marked offline_mock")
    config.validate(require_opt_in=not offline_mock)
    if importlib.metadata.version("scope-optimizer") != SDK_VERSION:
        raise ValueError(f"Evaluation requires scope-optimizer=={SDK_VERSION}")
    if isinstance(max_steps, bool) or not isinstance(max_steps, int) or max_steps < 1:
        raise ValueError("max_steps must be a positive integer")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    _write(output / "plan.json", plan)
    sequences = selected_sequences(split, sequence_limit)
    scorer = output / "scorer-only"
    scorer.mkdir()
    _write(scorer / "scoring_keys.json", {sequence.sequence_id: {
        task_id: asdict(key) for task_id, key in sequence.scoring_keys.items()} for sequence in sequences})
    model = BudgetedModel(replace(config, opt_in=True) if offline_mock else config, transport=transport)
    results = []
    try:
        for repetition in range(1, repetitions + 1):
            for condition in conditions:
                for sequence in sequences:
                    directory = output / f"run-{repetition:03d}" / condition / sequence.sequence_id
                    result = await _run_sequence(sequence, condition, directory, model, max_steps)
                    result["repetition"] = repetition
                    results.append(result)
                    _write(output / "sequence_results.json", results)
    except Exception as exc:
        _write(output / "incomplete.json", {"status": "aborted", "error_type": type(exc).__name__,
               "completed_sequence_runs": len(results), "efficacy_evidence": False,
               "usage": model.ledger.snapshot()})
        raise
    # Repetitions are repeated measurements, not extra independent families.
    aggregate = []
    for condition in conditions:
        for sequence in sequences:
            rows = [r for r in results if r["condition"] == condition and r["sequence_id"] == sequence.sequence_id]
            aggregate.append({**rows[0], "future_success_rate": mean(r["future_success_rate"] for r in rows)})
    comparison = None
    if "repaired-v0.2" in conditions and "improved" in conditions:
        comparison = paired_cluster_comparison(aggregate)
        comparison["inference_warning"] = (
            "Pilot fixtures only; fixed model and budgets, small family count, and family dependence limit inference. "
            "Offline mock responses establish no task-quality efficacy." if offline_mock else
            "Fixture agent pilot only; small family count and family dependence limit inference. "
            "This is not a native OpenClaw deployment or held-out benchmark.")
    usage = model.ledger.snapshot()
    summary = {"schema_version": 1, "status": "completed", "split": split,
               "evidence_kind": "mock-provider-mechanics" if offline_mock else "real-model-fixture-pilot",
               "live_api_calls": 0 if offline_mock else usage["request_count"],
               "mock_provider": offline_mock, "surrogate_learning_algorithm": False,
               "scripted_model": offline_mock,
               "efficacy_evidence": False, "task_quality_measured": not offline_mock,
               "deployment_efficacy_established": False,
               "sequence_runs": len(results), "repetitions": repetitions,
               "family_clusters": len({s.cluster_id for s in sequences}),
               "conditions": _condition_reports(results, conditions, usage),
               "primary_comparison": comparison, "usage": usage,
               "baseline_commit": HISTORICAL_V02_COMMIT,
               "limitations": plan["execution_limits"]}
    _write(output / "summary.json", summary)
    return summary


def main(argv=None):
    from .models import ModelConfig
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly enable paid calls; omission writes only a plan")
    parser.add_argument("--provider", required=True, choices=("openai-compatible", "anthropic"))
    parser.add_argument("--model", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key-env", required=True, help="Name of the secret environment variable, never the secret value")
    parser.add_argument("--input-usd-per-million", required=True, type=float)
    parser.add_argument("--output-usd-per-million", required=True, type=float)
    parser.add_argument("--max-cost-usd", required=True, type=float)
    parser.add_argument("--max-calls", type=int, default=200)
    parser.add_argument("--max-input-tokens", type=int, default=32768)
    parser.add_argument("--max-output-tokens", type=int, default=1024)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    parser.add_argument("--temperature", type=float, default=.3)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--split", required=True, choices=("pilot", "development", "heldout"))
    parser.add_argument("--conditions", nargs="+", choices=CONDITIONS, default=list(CONDITIONS))
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--sequence-limit", type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    config = ModelConfig(provider=args.provider, model=args.model, base_url=args.base_url,
                         api_key_env=args.api_key_env, max_cost_usd=args.max_cost_usd,
                         input_usd_per_million=args.input_usd_per_million,
                         output_usd_per_million=args.output_usd_per_million,
                         max_input_tokens=args.max_input_tokens, max_output_tokens=args.max_output_tokens,
                         max_calls=args.max_calls, timeout_seconds=args.timeout_seconds,
                         temperature=args.temperature, opt_in=args.execute)
    options = dict(split=args.split, conditions=tuple(args.conditions), repetitions=args.repetitions,
                   sequence_limit=args.sequence_limit)
    if args.execute:
        result = asyncio.run(run_model_evaluation(config, args.output, max_steps=args.max_steps, **options))
    else:
        result = evaluation_plan(config, **options)
        args.output.resolve().mkdir(parents=True, exist_ok=False)
        _write(args.output.resolve() / "plan.json", result)
    print(json.dumps({"mode": "execute" if args.execute else "plan", "output": str(args.output.resolve()),
                      "evidence_kind": result.get("evidence_kind", "planning-only"),
                      "efficacy_evidence": result["efficacy_evidence"]}, indent=2))


if __name__ == "__main__":
    main()
