"""Pinned SCOPE with scoped transactional persistence and metered learning."""
import asyncio
from contextvars import ContextVar
from dataclasses import dataclass
import math
import re

from scope import SCOPEOptimizer
from scope.memory_optimizer import MemoryOptimizer
from memory_store import MemoryStore, RevisionConflict, checked_scope

_stage = ContextVar("learning_stage", default="synthesis")


def _get(value, key):
    return value.get(key) if isinstance(value, dict) else getattr(value, key, None)


def opposite(a, b):
    def parts(text):
        words = re.findall(r"\w+", text.casefold())
        return (any(w in {"never", "not", "avoid", "without"} for w in words),
                [w for w in words if w not in {"always", "never", "not", "do", "avoid", "without"}])
    left, right = parts(a), parts(b)
    return left[0] != right[0] and left[1] == right[1]


@dataclass
class LearningResult:
    text: str
    type: str
    rule_id: str
    revision: int
    evidence_id: str

    def __getitem__(self, index):
        return (self.text, self.type)[index]


class MeteredModel:
    def __init__(self, model, owner):
        self.adapter, self.owner = model, owner
        self.model = getattr(model, "model", None)

    async def generate(self, messages):
        response, error = None, None
        try:
            response = await self.adapter.generate(messages)
            return response
        except Exception as exc:
            error = type(exc).__name__
            raise
        finally:
            owner = self.owner
            if owner._scope:
                usage = _get(_get(response, "raw_response"), "usage")
                inputs = _get(usage, "prompt_tokens")
                outputs = _get(usage, "completion_tokens")
                inputs = inputs if inputs is not None else _get(usage, "input_tokens")
                outputs = outputs if outputs is not None else _get(usage, "output_tokens")
                known = all(isinstance(v, int) and not isinstance(v, bool) and v >= 0 for v in (inputs, outputs))
                status = "actual" if known else "unknown"
                if not known:
                    inputs = outputs = None
                    if owner.estimate_usage and response is not None:
                        inputs = math.ceil(sum(len(str(_get(m, "content") or "")) for m in messages) / 4)
                        outputs = math.ceil(len(str(_get(response, "content") or "")) / 4)
                        status = "estimated"
                rates, cost = owner.cost_rates, None
                if status != "unknown" and rates and all(rates.get(k) is not None for k in ("input", "output")):
                    cost = (inputs * rates["input"] + outputs * rates["output"]) / 1_000_000
                owner.memory_store.record_usage(owner._agent, owner._scope, _stage.get(), status,
                    inputs, outputs, model=self.model, error=error, cost=cost)


class ScopedStrategicStore:
    def __init__(self, owner, model, enabled, prompts):
        self.owner, self.model, self.enabled, self.prompts = owner, model, enabled, prompts
        self.rules = {}

    def get_strategic_rules(self, agent_name, max_rules_per_domain=None):
        result = {}
        if self.owner._scope:
            for rule in self.owner.memory_store.active_rules(agent_name, self.owner._scope):
                if rule["type"] == "strategic":
                    result.setdefault(rule["domain"], []).append({"rule": rule["text"],
                        "confidence": rule["confidence"], "rationale": rule.get("rationale", ""),
                        "id": rule["id"], "source_task_id": rule["task_id"], "added_timestamp": rule["created_at"]})
        self.rules[agent_name] = result
        return result

    def get_strategic_rules_text(self, agent_name, max_rules_per_domain=None):
        return "\n".join(f"- {r['rule']}" for entries in self.get_strategic_rules(agent_name).values() for r in entries)

    def get_rule_count(self, agent_name=None):
        return sum(len(v) for v in self.get_strategic_rules(agent_name or self.owner._agent).values())

    async def add_strategic_rule(self, agent_name, rule_text, rationale, confidence, domain, source_task_id=None):
        owner, scope = self.owner, self.owner._scope
        rule = owner.memory_store.add_rule(agent_name, scope, rule_text, "strategic", domain,
            confidence, owner._task_id, owner._evidence_id, owner._expected_revision, rationale)
        if not rule:
            return False
        owner._accepted, owner._expected_revision = rule, rule["revision"]
        revision, rules = owner.memory_store.domain_snapshot(agent_name, scope, domain)
        if len(rules) <= owner.memory_store.max_rules_per_domain:
            return True
        candidates = [{"rule": r["text"], "confidence": r["confidence"],
                       "rationale": r.get("rationale", ""), "_opt_id": i} for i, r in enumerate(rules)]
        candidates.sort(key=lambda r: -r["confidence"])
        token = _stage.set("consolidation")
        try:
            replacements = candidates
            if self.enabled:
                replacements = await MemoryOptimizer(self.model, custom_prompts=self.prompts).optimize_rules(
                    candidates, target_count=max(1, int(owner.memory_store.max_rules_per_domain * .8)))
            if not replacements:
                replacements = candidates
            committed = owner.memory_store.consolidate(agent_name, scope, domain, replacements, revision)
            if committed is not None:
                owner._expected_revision = committed
        except RevisionConflict:
            # Another accepted rule/control wins. Retrieval enforces the bound without deleting it.
            pass
        finally:
            _stage.reset(token)
        return True


class TaskScopedOptimizer(SCOPEOptimizer):
    def __init__(self, *, memory_store=None, estimate_usage=False, cost_rates=None, **kwargs):
        self._scope, self._agent, self._task_id = None, "", None
        self._evidence_id, self._expected_revision, self._accepted = None, 0, None
        self._classification = {}
        self.estimate_usage, self.cost_rates = estimate_usage, cost_rates
        if cost_rates and any(v is not None and (not math.isfinite(v) or v < 0) for v in cost_rates.values()):
            raise ValueError("Explicit usage prices must be finite and nonnegative")
        self.memory_store = memory_store or MemoryStore(kwargs["exp_path"], kwargs.get("max_strategic_rules_per_domain", 10))
        source = kwargs["synthesizer_model"]
        model = MeteredModel(source, self)
        consolidation_model = MeteredModel(kwargs.get("optimizer_model") or source, self)
        kwargs.update(synthesizer_model=model, optimizer_model=consolidation_model)
        if kwargs.get("quality_analysis_frequency", 1) < 1 or kwargs.get("max_rules_per_task", 20) < 1:
            raise ValueError("Learning frequency and task limit must be positive")
        super().__init__(**kwargs)
        self.strategic_store = ScopedStrategicStore(self, consolidation_model,
            kwargs.get("enable_rule_optimization", True), kwargs.get("custom_prompts") or {})
        self.lock, self.task_counters = asyncio.Lock(), {}

    async def _classify_and_check_duplicate(self, **kwargs):
        token = _stage.set("classification")
        try:
            classification = await super()._classify_and_check_duplicate(**kwargs)
        finally:
            _stage.reset(token)
        rules = self.memory_store.active_rules(kwargs["agent_name"], self._scope, self._task_id)
        if classification["is_duplicate"] and any(opposite(r["text"], kwargs["update_text"]) for r in rules):
            classification["is_duplicate"] = False
        if not isinstance(classification.get("is_duplicate"), bool):
            raise ValueError("Classifier supplied an invalid duplicate decision")
        confidence = classification.get("confidence")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError("Classifier supplied invalid confidence")
        if classification.get("scope") not in ("tactical", "strategic"):
            raise ValueError("Classifier supplied invalid scope")
        self._classification = classification
        return classification

    async def on_step_complete(self, *, agent_name, task_id=None, scope=None, **kwargs):
        if not scope:
            return None
        scope = checked_scope(scope)
        async with self.lock:
            if self.memory_store.paused(agent_name, scope):
                return None
            self._scope, self._agent, self._task_id = scope, agent_name, task_id
            self._expected_revision, self._accepted = self.memory_store.revision(agent_name, scope), None
            self._classification = {}
            key = (agent_name, scope["audience_key"], scope["project_key"], task_id)
            applied, successful = self.task_counters.get(key, (0, 0))
            if applied >= self.max_rules_per_task:
                self._scope = None
                return None
            self._applied_rules_count[agent_name], self._successful_steps_count[agent_name] = applied, successful
            prior_rules = list(self._get_applied_rules(repr(key), agent_name))
            trace = {k: (str(v)[:32000] if v is not None else None) for k, v in kwargs.items()
                     if k in ("task", "model_output", "tool_calls", "observations", "error", "current_system_prompt")}
            evidence = self.memory_store.record_evidence(agent_name, scope, task_id, trace)
            self._evidence_id = evidence["id"]
            analysis_result = "no_guideline"
            try:
                result = await super().on_step_complete(agent_name=agent_name, task_id=repr(key), **kwargs)
                if not result:
                    return None
                if self.memory_store.revision(agent_name, scope) != self._expected_revision or self.memory_store.paused(agent_name, scope):
                    analysis_result = "stale_proposal"
                    return None
                if self._accepted is None:
                    self._accepted = self.memory_store.add_rule(agent_name, scope, result[0], "tactical",
                        self._classification.get("domain", "general"), self._classification.get("confidence", .5),
                        task_id, self._evidence_id, self._expected_revision)
                if self._accepted is None:
                    return None
                rule = self._accepted
                analysis_result = "accepted"
                return LearningResult(rule["text"], rule["type"], rule["id"],
                    self.memory_store.revision(agent_name, scope), self._evidence_id)
            except Exception:
                analysis_result = "failed"
                raise
            finally:
                self.memory_store.record_analysis(agent_name, scope, self._evidence_id, analysis_result)
                if self._accepted is None:
                    self._applied_rules_count[agent_name] = applied
                    self._applied_rules_by_task.setdefault(repr(key), {})[agent_name] = prior_rules
                self.task_counters[key] = (self._applied_rules_count.get(agent_name, applied),
                                          self._successful_steps_count.get(agent_name, successful))
                self._scope = None

    async def reset_tactical(self, *, agent_name, task_id=None, scope=None):
        if not scope:
            return
        scope = checked_scope(scope)
        async with self.lock:
            for key in list(self.task_counters):
                if key[:3] == (agent_name, scope["audience_key"], scope["project_key"]) and (task_id is None or key[3] == task_id):
                    self.task_counters.pop(key)
                    self._applied_rules_by_task.pop(repr(key), None)
            self.memory_store.reset_tactical(agent_name, scope, task_id)

    def strategic_guidelines(self, agent_name, scope=None):
        if not scope:
            return []
        return [r["text"] for r in self.memory_store.active_rules(agent_name, scope) if r["type"] == "strategic"]

    def get_strategic_rules_for_agent(self, agent_name, scope=None):
        return "\n".join(f"- {text}" for text in self.strategic_guidelines(agent_name, scope))
