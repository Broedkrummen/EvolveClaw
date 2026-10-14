"""Explicitly scripted mechanics adapters; no claims about actual AI efficacy."""
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from .scenarios import Feedback, Scope, Task, FakeWorld


CONDITIONS = ("learning-off", "repaired-v0.2", "improved")


@dataclass
class ScriptRule:
    rule_id: str
    topic: str
    directive: str
    value: str | None
    scope: Scope
    active: bool = True


class ScriptedMemory:
    """Transparent surrogates for pipeline tests, not actual SCOPE integrations.

    The repaired surrogate deliberately uses agent-wide retrieval and has no
    rollback. The improved surrogate scopes retrieval and records reversible
    changes. These choices manufacture differences and prove only scoring flow.
    """

    def __init__(self, condition: str, directory: Path):
        if condition not in CONDITIONS:
            raise ValueError(f"Unknown condition: {condition}")
        self.condition = condition
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=False)
        self.rules: list[ScriptRule] = []
        self.history = []
        self._persist()

    def _persist(self):
        (self.directory / "memory.json").write_text(json.dumps({
            "adapter": "scripted-surrogate", "condition": self.condition,
            "rules": [asdict(r) for r in self.rules], "history": self.history}, indent=2) + "\n")

    def feedback(self, feedback: Feedback):
        if self.condition == "learning-off":
            return {"changed": False, "reason": "learning-disabled"}
        rule = ScriptRule(f"rule-{len(self.rules) + 1}", feedback.topic, feedback.directive,
                          feedback.value, feedback.scope)
        self.rules.append(rule)
        self.history.append({"revision": len(self.history) + 1, "operation": "learn",
                             "rule_id": rule.rule_id, "evidence": feedback.text})
        self._persist()
        return {"changed": True, "rule_id": rule.rule_id}

    def retrieve(self, topic: str, scope: Scope):
        for rule in reversed(self.rules):
            if rule.active and rule.topic == topic and (
                    self.condition == "repaired-v0.2" or rule.scope == scope):
                return rule
        return None

    def rollback(self, scope: Scope):
        if self.condition != "improved":
            return {"changed": False, "reason": "rollback-unavailable-in-surrogate"}
        for rule in reversed(self.rules):
            if rule.active and rule.scope == scope:
                rule.active = False
                self.history.append({"revision": len(self.history) + 1, "operation": "rollback",
                                     "rule_id": rule.rule_id})
                self._persist()
                return {"changed": True, "rule_id": rule.rule_id}
        return {"changed": False, "reason": "no-active-rule"}


class ScriptedAssistant:
    """Deterministic shortcuts that let the harness exercise mistakes and undo."""

    def __init__(self, memory: ScriptedMemory):
        self.memory = memory

    def run_task(self, task: Task, world: FakeWorld) -> dict[str, Any]:
        results = [world.call(t.name, t.arguments) for t in task.tools]
        result = results[0]
        rule = self.memory.retrieve(task.topic, task.scope)
        if task.topic == "verify-tool-result":
            return {"completed": result["status"] == "completed" if rule else True}
        if task.topic == "use-current-verified-source":
            records = result["records"]
            if rule:
                records = [r for r in records if r["verified"]]
                selected = max(records, key=lambda r: r["updated"]) if records else None
            else:
                selected = records[0] if records else None
            return {"value": selected["value"] if selected else None,
                    "source_id": selected["source_id"] if selected else None}
        return {"value": rule.value if rule else result.get("default", result.get("affordable_default"))}
