"""Isolated released-SDK reference, preserving upstream SCOPE 0.1.3 behavior.

This is neither EvolveClaw's repaired wrapper nor a reproduction of the complete
paper. All optimizer prompts, domains, thresholds, and algorithms are SDK defaults.
No provider model is created and no environment credentials are discovered.
"""
from collections import deque
from copy import deepcopy
import hashlib
import importlib.metadata
import inspect
import json
from pathlib import Path
from types import SimpleNamespace

from .models import ModelConfig


SDK_VERSION = "0.1.3"
REFERENCE_CONDITION = "scope_sdk_reference"
KNOWN_LIMITATIONS = [
    "Released SDK reference, not full-paper replication or an actual task-quality result.",
    "Strategic advice is keyed by agent, without EvolveClaw user/project audience isolation.",
    "SCOPE 0.1.3 exposes no public tactical/task-counter reset API; this runner does not repair its counters.",
    "Applied-rule readout uses upstream's private read helper and can include promoted strategic advice.",
    "Upstream JSON persistence, duplicate heuristics, consolidation, and concurrency limitations remain unchanged.",
    "SDK defaults disable Best-of-N, use thoroughness synthesis, and disable guideline history logging.",
    "No automatic rule rollback or externally validated task-outcome gate is added.",
]


def _json_write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


class ScriptedScopeModel:
    """Injected offline responses; real SDK reflection/classification still execute."""
    offline_scripted = True

    def __init__(self, responses):
        self.responses = deque(deepcopy(responses))
        self.requests = []
        self.model = "scripted-offline-no-provider"

    async def generate(self, messages):
        self.requests.append([{"role": message.role, "content": deepcopy(message.content)} for message in messages])
        if not self.responses:
            raise AssertionError("Unexpected SDK model call: scripted responses exhausted")
        response = self.responses.popleft()
        return SimpleNamespace(content=json.dumps(response), raw_response=None)


class ScopeSDKReference:
    """Direct upstream optimizer with an explicitly supplied model and own state.

    An injected model is required. Offline mode requires a model explicitly
    marked offline_scripted=True (a local fake or AsyncMock can set this flag).
    Paid mode accepts only an explicitly configured BudgetedModel; no remote
    provider is selected or created by this reference adapter itself.
    """
    condition = REFERENCE_CONDITION

    def __init__(self, directory: Path, model, *, resume=False, model_mode="offline-scripted",
                 real_model_config: ModelConfig | None = None):
        if model is None or not callable(getattr(model, "generate", None)):
            raise ValueError("Supply a model implementing async generate(messages); no model is created implicitly")
        if model_mode == "real-opt-in":
            from .models import BudgetedModel
            if not isinstance(model, BudgetedModel):
                raise ValueError("Real reference runs require the explicit budgeted provider/model adapter")
            model.config.validate()
            if real_model_config is not None:
                real_model_config.validate()
                if real_model_config != model.config:
                    raise ValueError("Reference model configuration differs from the supplied budgeted model")
        elif model_mode != "offline-scripted" or getattr(model, "offline_scripted", None) is not True:
            raise ValueError("Offline reference requires an explicitly marked offline_scripted model")
        installed_version = importlib.metadata.version("scope-optimizer")
        if installed_version != SDK_VERSION:
            raise ValueError(f"Expected scope-optimizer=={SDK_VERSION}, found {installed_version}")
        from scope import SCOPEOptimizer
        from scope import prompts
        from scope.strategic_store import StrategicMemoryStore
        self.directory = Path(directory).resolve()
        metadata_path = self.directory / "reference_metadata.json"
        if resume:
            if not metadata_path.is_file():
                raise ValueError("Resume requires an existing isolated SDK-reference run")
            previous = json.loads(metadata_path.read_text())
            if previous.get("sdk_version") != SDK_VERSION or previous.get("condition") != REFERENCE_CONDITION:
                raise ValueError("Reference state provenance mismatch")
        else:
            self.directory.mkdir(parents=True, exist_ok=False)
        self.model = model
        # Only these two mandatory arguments: every optional SDK setting remains
        # its actual released default. No application optimizer/store/prompts.
        self.optimizer = SCOPEOptimizer(synthesizer_model=model, exp_path=str(self.directory / "sdk-state"))
        defaults = {name: parameter.default for name, parameter in inspect.signature(SCOPEOptimizer).parameters.items()
                    if parameter.default is not inspect.Parameter.empty}
        source_paths = {"optimizer": inspect.getsourcefile(SCOPEOptimizer),
                        "strategic_store": inspect.getsourcefile(StrategicMemoryStore),
                        "prompts": prompts.__file__}
        self.metadata = {"condition": REFERENCE_CONDITION, "sdk_version": installed_version,
                         "optimizer_class": f"{type(self.optimizer).__module__}.{type(self.optimizer).__qualname__}",
                         "actual_upstream_optimizer": True, "surrogate_optimizer": False,
                         "scripted_model": model_mode == "offline-scripted", "evidence_kind": "mechanics-only",
                         "task_quality_measured": False, "full_paper_replication": False,
                         "model_mode": model_mode, "default_configuration": defaults,
                         "allowed_domains": list(self.optimizer.allowed_domains),
                         "source_sha256": {key: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                           for key, path in source_paths.items()},
                         "known_limitations": KNOWN_LIMITATIONS, "live_api_calls": 0,
                         "paid_evaluation_cost": {"status": "unknown", "amount": None}}
        _json_write(metadata_path, self.metadata)
        self.events = []

    async def on_step_complete(self, **step):
        # Caller may supply normal execution observations, tool failures, and
        # ordinary user feedback. Evaluator golden answers must never enter step.
        before = len(getattr(self.model, "requests", []))
        result = await self.optimizer.on_step_complete(**step)
        after = len(getattr(self.model, "requests", []))
        self.events.append({"operation": "on_step_complete", "agent_name": step.get("agent_name"),
                            "task_id": step.get("task_id"), "result": result,
                            "scripted_generate_calls": after - before})
        _json_write(self.directory / "reference_events.json", self.events)
        if self.metadata["model_mode"] == "real-opt-in":
            budget = self.model.ledger.snapshot()
            native = any(call.get("transport_kind") == "native-openclaw" for call in budget["calls"])
            self.metadata["live_api_calls"] = None if native else sum(not call["injected_transport"] for call in budget["calls"])
            self.metadata["model_execution_requests"] = budget["request_count"]
            self.metadata["provider_attempt_count_status"] = "unknown-native-host" if native else "recorded-direct-requests"
            self.metadata["budget"] = budget
            _json_write(self.directory / "reference_metadata.json", self.metadata)
        return result

    def retrieve(self, agent_name: str):
        return self.optimizer.get_strategic_rules_for_agent(agent_name)

    def snapshot(self, agent_name: str, task_id: str | None = None):
        return {"condition": REFERENCE_CONDITION, "sdk_version": SDK_VERSION,
                "strategic_guidelines": self.retrieve(agent_name),
                "applied_rules_readout": deepcopy(self.optimizer._get_applied_rules(task_id, agent_name)),
                "applied_rules_api": "upstream-private-read-helper",
                "statistics": self.optimizer.get_statistics(),
                "public_task_reset_supported": False,
                "evidence_kind": "mechanics-only", "actual_upstream_optimizer": True,
                "task_quality_measured": False}

    def reset_task(self, agent_name: str, task_id: str):
        # The released SDK has no public reset method. Do not silently patch
        # private counters or pretend task boundaries reset them correctly.
        return {"supported": False, "changed": False, "agent_name": agent_name, "task_id": task_id,
                "reason": "SCOPE 0.1.3 has no public tactical/task-counter reset API"}


async def run_reference_smoke(directory: Path):
    strategic_text = "Check returned tool status before claiming an operation completed."
    tactical_text = "For this simulated import task, the file uses semicolon-delimited fields."
    model = ScriptedScopeModel([
        {"update_text": strategic_text, "rationale": "The fake calendar tool reported failure.", "confidence": "high"},
        {"is_duplicate": False, "scope": "strategic", "confidence": .9,
         "domain": "error_handling", "reason": "Reusable tool-status lesson."},
        {"update_text": tactical_text, "rationale": "The current file has a task-specific delimiter.", "confidence": "high"},
        {"is_duplicate": False, "scope": "tactical", "confidence": .9,
         "domain": "data_validation", "reason": "Current-file detail only."},
    ])
    reference = ScopeSDKReference(directory, model)
    first = await reference.on_step_complete(agent_name="sim-agent", agent_role="assistant",
                    task="Create a fake calendar appointment and report its status.", task_id="calendar-a",
                    model_output="Appointment created.", observations="Fake calendar returned status=failed.",
                    error=RuntimeError("The simulated tool failed."))
    second = await reference.on_step_complete(agent_name="sim-agent", agent_role="assistant",
                    task="Import the simulated structured-data file.", task_id="import-b",
                    model_output="Import did not succeed.", observations="Header is name;amount;date.",
                    error=RuntimeError("Incorrect delimiter in the simulated import."))
    if first != (strategic_text, "strategic") or second != (tactical_text, "tactical"):
        raise AssertionError("Upstream reflection/classification did not return the scripted expected mechanics")
    restored = ScopeSDKReference(directory, ScriptedScopeModel([]), resume=True)
    if strategic_text not in restored.retrieve("sim-agent") or tactical_text in restored.retrieve("sim-agent"):
        raise AssertionError("Strategic/tactical persistence boundary failed")
    if len(model.requests) != 4 or model.responses:
        raise AssertionError("Expected actual upstream synthesis and classification calls for both steps")
    report = {**reference.metadata, "scripted_generate_calls": len(model.requests),
              "snapshot": reference.snapshot("sim-agent", "import-b"),
              "restored_guidelines": restored.retrieve("sim-agent"),
              "reset": reference.reset_task("sim-agent", "import-b"),
              "checks": ["direct-upstream-class", "default-prompts-domains-settings", "error-reflection",
                         "classifier", "strategic-persistence", "tactical-not-persisted", "reset-limitation-visible"]}
    _json_write(reference.directory / "scripted_model_requests.json", model.requests)
    _json_write(reference.directory / "reference_smoke_report.json", report)
    return report
