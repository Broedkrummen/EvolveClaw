"""Authored pilot cases, public observations, and separately held scoring keys.

The runner never passes ScoringKey objects to an agent or memory adapter. A paid
adapter must additionally restrict its filesystem/tools to the exported public
fixture directory: Python module boundaries are not a security sandbox.
"""
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Scope:
    audience_key: str
    project_key: str

    def to_dict(self):
        return {"audience_key": self.audience_key, "project_key": self.project_key}


@dataclass(frozen=True)
class ToolFixture:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass(frozen=True)
class Task:
    task_id: str
    instruction: str
    scope: Scope
    tools: tuple[ToolFixture, ...]
    topic: str
    phase: str = "future"

    def public_request(self):
        # Results are returned only if the assistant calls the advertised tool.
        return {"task_id": self.task_id, "instruction": self.instruction,
                "scope": self.scope.to_dict(), "topic": self.topic,
                "tools": [{"name": t.name, "arguments": t.arguments} for t in self.tools]}


@dataclass(frozen=True)
class Feedback:
    text: str
    scope: Scope
    topic: str
    # An explicit simulated user instruction, not the evaluator's answer key.
    directive: str
    value: str | None = None

    def public_request(self):
        return {"text": self.text, "scope": self.scope.to_dict(), "topic": self.topic,
                "directive": self.directive, "value": self.value}


@dataclass(frozen=True)
class Rollback:
    scope: Scope
    text: str = "Undo the last lesson I gave you; that advice was wrong."


@dataclass(frozen=True)
class ScoringKey:
    required_fields: dict[str, Any]
    metric_tags: tuple[str, ...] = ()
    mistake_key: str | None = None


@dataclass(frozen=True)
class Sequence:
    sequence_id: str
    family_id: str
    cluster_id: str
    category: str
    split: str
    events: tuple[Task | Feedback | Rollback, ...]
    scoring_keys: dict[str, ScoringKey] = field(repr=False)

    def manifest_entry(self):
        return {"sequence_id": self.sequence_id, "family_id": self.family_id,
                "cluster_id": self.cluster_id, "category": self.category,
                "split": self.split, "fixture_status": "authored",
                "task_count": sum(isinstance(e, Task) for e in self.events)}


class FakeWorld:
    """No network, accounts, files, or irreversible actions. Each task is isolated."""

    def __init__(self, task: Task):
        self._fixtures = {t.name: t for t in task.tools}
        self.calls = []

    def call(self, name: str, arguments: dict[str, Any]):
        from copy import deepcopy
        fixture = self._fixtures.get(name)
        if fixture is None:
            raise ValueError(f"Unadvertised simulated tool: {name}")
        if arguments != fixture.arguments:
            raise ValueError(f"Invalid simulated arguments for {name}")
        result = deepcopy(fixture.result)
        self.calls.append({"name": name, "arguments": deepcopy(arguments), "result": result})
        return deepcopy(result)


def _status_sequence(family, category, tool, variant):
    audience = Scope("sim:user-a", "sim:project-a")
    topic = "verify-tool-result"
    seq_id = f"pilot.{family}.{variant:02d}"
    instruction = f"Use {tool} for this request and report whether it was completed."
    training = Task(f"{seq_id}.learn", instruction, audience,
                    (ToolFixture(tool, {"item": f"initial-{variant}"},
                                 {"status": "failed", "error": "Service unavailable"}),), topic, "learning")
    feedback = Feedback("That operation failed. Check the returned status before claiming it was completed.",
                        audience, topic, "use-tool-status")
    failed = Task(f"{seq_id}.failure", instruction, audience,
                  (ToolFixture(tool, {"item": f"fresh-{variant}"},
                               {"status": "failed", "error": "Permission denied"}),), topic)
    succeeded = Task(f"{seq_id}.success", instruction, audience,
                     (ToolFixture(tool, {"item": f"another-{variant}"},
                                  {"status": "completed", "receipt": f"fake-{variant}"}),), topic)
    keys = {training.task_id: ScoringKey({"completed": False}, mistake_key=topic),
            failed.task_id: ScoringKey({"completed": False}, ("tool_recovery",), topic),
            succeeded.task_id: ScoringKey({"completed": True}, ("tool_recovery",), topic)}
    return Sequence(seq_id, family, family, category, "pilot", (training, feedback, failed, succeeded), keys)


def _current_sequence(family, category, variant):
    scope = Scope("sim:user-a", "sim:project-a")
    topic = "use-current-verified-source"
    seq_id = f"pilot.{family}.{variant:02d}"
    if family == "current-price":
        values = [f"${80 + variant}", f"${100 + variant}", f"${120 + variant}", f"${130 + variant}"]
        instruction = "Find the current verified price for the item, and give its source ID."
        tool = "shop.price_history"
    else:
        values = ["Monday", "Tuesday", "Wednesday", "Thursday"]
        instruction = "Find the latest verified opening day for the museum, and give its source ID."
        tool = "research.sources"

    def task(suffix, records, phase="future"):
        return Task(f"{seq_id}.{suffix}", instruction, scope,
                    (ToolFixture(tool, {"item": f"item-{variant}"}, {"records": records}),), topic, phase)

    def record(index, verified=True):
        return {"source_id": f"source-{index}", "value": values[index],
                "updated": f"2026-10-{index + 1:02d}", "verified": verified}

    initial = task("learn", [record(0), record(1)], "learning")
    feedback = Feedback(f"The updated verified source says {values[1]}. Use the newest verified source; older records can be stale.",
                        scope, topic, "use-current-verified-source")
    update = task("update", [record(0), record(1), record(2)])
    conflict = task("unverified", [record(1), record(2), record(3, False)])
    keys = {initial.task_id: ScoringKey({"value": values[1], "source_id": "source-1"}, mistake_key=topic),
            update.task_id: ScoringKey({"value": values[2], "source_id": "source-2"}, ("stale_advice",), topic),
            conflict.task_id: ScoringKey({"value": values[2], "source_id": "source-2"}, ("stale_advice",), topic)}
    return Sequence(seq_id, family, family, category, "pilot", (initial, feedback, update, conflict), keys)


def _scoped_sequence(family, variant):
    first = Scope("sim:user-a", "sim:project-a")
    second = (Scope("sim:user-b", "sim:project-a") if family == "user-preference"
              else Scope("sim:user-a", "sim:project-b"))
    seq_id = f"pilot.{family}.{variant:02d}"
    preference = "plant-based" if family == "user-preference" else "kebab-case"
    other = "omnivore" if family == "user-preference" else "camelCase"
    topic = "dietary-preference" if family == "user-preference" else "project-format"
    instruction = ("Choose the snack category using this user's usual dietary preference."
                   if family == "user-preference" else "Choose the naming style used by this project.")

    def task(suffix, scope, default, phase="future"):
        return Task(f"{seq_id}.{suffix}", instruction, scope,
                    (ToolFixture("context.preference", {"topic": topic}, {"default": default}),), topic, phase)

    initial = task("learn", first, other, "learning")
    correction = Feedback(f"For this user and project, remember the preference is {preference}.",
                          first, topic, "remember-preference", preference)
    same = task("same-scope", first, other)
    separate = task("separate-scope", second, other)
    keys = {initial.task_id: ScoringKey({"value": preference}, mistake_key=topic),
            same.task_id: ScoringKey({"value": preference}, ("scope_reuse",), topic),
            separate.task_id: ScoringKey({"value": other}, ("scope_leakage",), topic)}
    return Sequence(seq_id, family, family, "planning" if family == "user-preference" else "documents",
                    "pilot", (initial, correction, same, separate), keys)


def _rollback_sequence(variant):
    scope = Scope("sim:user-a", "sim:project-a")
    seq_id = f"pilot.rollback.{variant:02d}"
    topic = "plan-choice"

    def task(suffix, phase="future"):
        return Task(f"{seq_id}.{suffix}", "Choose the affordable plan within this project's budget.", scope,
                    (ToolFixture("shop.plans", {"account": f"fake-{variant}"},
                                 {"affordable_default": "standard", "options": ["standard", "premium"]}),), topic, phase)

    initial = task("initial", "learning")
    # Deliberately wrong, ordinary user feedback exercises undo. No world action is replayed.
    fault = Feedback("Remember: always choose premium for this project.", scope, topic,
                     "remember-preference", "premium")
    bad = task("before-undo")
    restored = task("after-undo")
    keys = {initial.task_id: ScoringKey({"value": "standard"}, mistake_key=topic),
            bad.task_id: ScoringKey({"value": "standard"}, ("rollback_before",), topic),
            restored.task_id: ScoringKey({"value": "standard"}, ("rollback_recurrence",), topic)}
    return Sequence(seq_id, "rollback", "rollback", "shopping", "pilot",
                    (initial, fault, bad, Rollback(scope), restored), keys)


def pilot_sequences():
    """20 sequence fixtures in 10 families, not 20 independent task families."""
    sequences = []
    status_families = [("calendar-failure", "planning", "calendar.create"),
                       ("email-failure", "communication", "email.send"),
                       ("document-failure", "documents", "document.save"),
                       ("data-failure", "structured_data", "data.import"),
                       ("booking-failure", "shopping", "booking.reserve")]
    for variant in (1, 2):
        sequences.extend(_status_sequence(*entry, variant) for entry in status_families)
        sequences.extend([_current_sequence("current-price", "shopping", variant),
                          _current_sequence("current-source", "research", variant),
                          _scoped_sequence("user-preference", variant),
                          _scoped_sequence("project-format", variant),
                          _rollback_sequence(variant)])
    return sorted(sequences, key=lambda s: s.sequence_id)


def planned_manifest():
    """List authored pilot/development cases and reserve held-out authoring slots."""
    from .development_scenarios import development_sequences
    rows = [s.manifest_entry() for s in pilot_sequences()]
    rows.extend(s.manifest_entry() for s in development_sequences())
    for split, families, variants in (("heldout", 500, 1),):
        for family_number in range(1, families + 1):
            family = f"{split}-family-{family_number:03d}"
            for variant in range(1, variants + 1):
                rows.append({"sequence_id": f"{family}.{variant:02d}", "family_id": family,
                             "cluster_id": family, "split": split, "category": "pending-authoring",
                             "fixture_status": "planned", "task_count": None})
    return rows


def validate_manifest(rows):
    seen_ids = set()
    families = {}
    clusters = {}
    for row in rows:
        seq_id, split = row["sequence_id"], row["split"]
        if seq_id in seen_ids:
            raise ValueError(f"Duplicate sequence ID: {seq_id}")
        seen_ids.add(seq_id)
        for key, index in (("family_id", families), ("cluster_id", clusters)):
            value = row[key]
            if value in index and index[value] != split:
                raise ValueError(f"{key} {value} crosses splits")
            index[value] = split
