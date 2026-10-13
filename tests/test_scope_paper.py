"""Exercise the actual SDK algorithms with injected, non-network models."""
from dataclasses import FrozenInstanceError
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from evaluation.scope_paper import PaperConfig, ScopePaperController


class MetaModel:
    def __init__(self, *, scope="strategic", confidence=.9, consolidate=False):
        self.scope = scope
        self.confidence = confidence
        self.consolidate = consolidate
        self.calls = []
        self.candidates = 0

    async def generate(self, messages):
        prompt = "\n".join(b["text"] for m in messages for b in m.content)
        if prompt.startswith("You are a rule classifier"):
            kind, value = "classifier", {"is_duplicate": False, "scope": self.scope,
                                         "confidence": self.confidence, "domain": "tool_usage", "reason": "test"}
        elif prompt.startswith("You are a prompt engineering expert evaluating"):
            kind, value = "selector", {"selected_index": 1, "rationale": "Choose second actual candidate"}
        elif prompt.startswith("You are a rule optimization analyzer"):
            kind, value = "analysis", ({"conflicts": [[0, 1]], "subsumption": [[2, 3]],
                                       "consolidation": [[4, 5, 6]]} if self.consolidate else
                                      {"conflicts": [], "subsumption": [], "consolidation": []})
        elif prompt.startswith("You are resolving a conflict"):
            kind, value = "conflict", {"rule": "Resolve conflicting validation advice.", "rationale": "test"}
        elif prompt.startswith("Verify if the general rule"):
            kind, value = "subsumption", {"subsumed": True, "reasoning": "test"}
        elif prompt.startswith("You are merging similar rules"):
            kind, value = "merge", {"rule": "Consolidated validation procedure.", "rationale": "test"}
        else:
            self.candidates += 1
            kind = "corrective" if "analyzing agent execution errors" in prompt else "enhancement"
            value = {"update_text": f"Validate response using lesson {self.candidates}.",
                     "rationale": "Use the observed step, not a hidden task answer.", "confidence": "high"}
        self.calls.append((kind, prompt))
        return SimpleNamespace(content=json.dumps(value))


TASK = {"task_id": "task-1", "instruction": "Check the simulated operation result.",
        "scope": {"audience_key": "user-a", "project_key": "project-a"}}
NAMESPACE = TASK["scope"]


class ScopePaperTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_whole_executions_and_two_candidates_with_real_selector(self):
        import asyncio
        with tempfile.TemporaryDirectory() as directory:
            model = MetaModel()
            controller = ScopePaperController(model, Path(directory))
            started, barrier, original_inputs = set(), asyncio.Event(), []

            async def execute(task, perspective, guidance):
                original_inputs.append(task["instruction"])
                task["instruction"] = "executor-local mutation"
                started.add(perspective)
                if len(started) == 2:
                    barrier.set()
                await asyncio.wait_for(barrier.wait(), 1)
                before = guidance.prompt("Planner", "Base instructions")
                result = await guidance.observe_step("Planner", "Base instructions", model_output="Called tool",
                                                     observations={"status": "failed"}, error="Tool returned failure")
                after = guidance.prompt("Planner", "Base instructions")
                return {"before": before, "after": after, "accepted": result["accepted"]}

            results = await controller.run_task(TASK, execute, namespace=NAMESPACE)
            self.assertEqual(started, {"efficiency", "thoroughness"})
            self.assertEqual(original_inputs, [TASK["instruction"], TASK["instruction"]])
            self.assertEqual(len([c for c in model.calls if c[0] == "corrective"]), 4)
            self.assertEqual(len([c for c in model.calls if c[0] == "selector"]), 2)
            self.assertEqual(len([c for c in model.calls if c[0] == "classifier"]), 2)
            self.assertEqual({r.learning_events[0]["guideline"] for r in results},
                             {"Validate response using lesson 2.", "Validate response using lesson 4."})
            for result in results:
                self.assertEqual(result.status, "completed", result.error)
                self.assertEqual(result.meta_model_calls, 4)
                self.assertEqual(result.response["before"], "Base instructions")
                self.assertIn(result.learning_events[0]["guideline"], result.response["after"])
                self.assertTrue(result.response["accepted"])
            # Synthesis saw the controller's original request, not mutations by either executor.
            self.assertTrue(all(TASK["instruction"] in p for k, p in model.calls if k == "corrective"))
            self.assertEqual(len(list(Path(directory).rglob("strategic.json"))), 2)

    async def test_persistent_strategic_and_isolated_role_perspective_namespace(self):
        with tempfile.TemporaryDirectory() as directory:
            model = MetaModel()
            path = Path(directory)
            controller = ScopePaperController(model, path)

            async def learn(task, perspective, guidance):
                await guidance.observe_step("Planner", "Base", model_output="An observation")
                return {"own": guidance.prompt("Planner", "Base"), "other_role": guidance.prompt("Browser", "Base")}

            first = await controller.run_task(TASK, learn, namespace=NAMESPACE)
            self.assertTrue(all(r.response["other_role"] == "Base" for r in first))

            async def read(task, perspective, guidance):
                return {"prompt": guidance.prompt("Planner", "Base")}

            restarted = ScopePaperController(model, path)
            second = await restarted.run_task({**TASK, "task_id": "task-2"}, read, namespace=NAMESPACE)
            for old, new in zip(first, second):
                self.assertEqual(old.response["own"], new.response["prompt"])
                self.assertEqual(new.meta_model_calls, 0)
            self.assertNotEqual(second[0].response["prompt"], second[1].response["prompt"])
            other = await restarted.run_task(TASK, read, namespace={**NAMESPACE, "project_key": "project-b"})
            self.assertTrue(all(r.response["prompt"] == "Base" for r in other))

    async def test_low_confidence_strategic_becomes_tactical_and_resets(self):
        with tempfile.TemporaryDirectory() as directory:
            model = MetaModel(scope="strategic", confidence=.6)
            controller = ScopePaperController(model, Path(directory))

            async def learn(task, perspective, guidance):
                event = await guidance.observe_step("Planner", "Base", model_output="Successful tool output")
                return {"prompt": guidance.prompt("Planner", "Base"), "event": event}

            first = await controller.run_task(TASK, learn, namespace=NAMESPACE)
            for result in first:
                self.assertEqual(result.response["event"]["scope"], "tactical")
                self.assertIn("Tactical guidelines", result.response["prompt"])
            self.assertEqual(list(Path(directory).rglob("strategic.json")), [])

            async def read(task, perspective, guidance):
                return {"prompt": guidance.prompt("Planner", "Base")}

            second = await controller.run_task({**TASK, "task_id": "task-2"}, read, namespace=NAMESPACE)
            self.assertTrue(all(r.response["prompt"] == "Base" for r in second))

    async def test_error_quality_frequency_immutable_trace_and_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            model = MetaModel(confidence=.49)
            controller = ScopePaperController(model, Path(directory), config=PaperConfig(quality_frequency=2))
            retained = []

            async def execute(task, perspective, guidance):
                retained.append(guidance)
                observation = {"value": "original"}
                skipped = await guidance.observe_step("Planner", "Base", model_output="Success", observations=observation)
                observation["value"] = "mutated"
                error = await guidance.observe_step("Planner", "Base", error="Invalid argument")
                quality = await guidance.observe_step("Planner", "Base", model_output="Success")
                return {"skipped": skipped, "error": error, "quality": quality}

            results = await controller.run_task(TASK, execute, namespace=NAMESPACE)
            for result in results:
                self.assertEqual(result.response["skipped"]["reason"], "quality-frequency")
                self.assertEqual(result.response["error"]["reason"], "below-acceptance-threshold")
                self.assertEqual(result.response["quality"]["reason"], "below-acceptance-threshold")
                self.assertIn("original", result.steps[0].observations)
                self.assertNotIn("mutated", result.steps[0].observations)
                with self.assertRaises(FrozenInstanceError):
                    result.steps[0].role = "changed"
            with self.assertRaisesRegex(RuntimeError, "closed"):
                retained[0].prompt("Planner", "Base")
            self.assertEqual(len([k for k, _ in model.calls if k == "corrective"]), 4)
            self.assertEqual(len([k for k, _ in model.calls if k == "enhancement"]), 4)
            self.assertEqual(list(Path(directory).rglob("strategic.json")), [])

    async def test_tactical_cap_resets_and_does_not_block_strategic_learning(self):
        with tempfile.TemporaryDirectory() as directory:
            model = MetaModel(scope="tactical", confidence=.9)
            controller = ScopePaperController(model, Path(directory),
                                             config=PaperConfig(perspectives=("efficiency",)))

            async def execute(task, perspective, guidance):
                events = [await guidance.observe_step("Planner", "Base", model_output=f"Step {i}") for i in range(22)]
                model.scope = "strategic"
                strategic = await guidance.observe_step("Planner", "Base", model_output="Reusable correction")
                return {"events": events, "strategic": strategic}

            result = (await controller.run_task(TASK, execute, namespace=NAMESPACE))[0]
            self.assertEqual(result.status, "completed", result.error)
            self.assertEqual(sum(e["accepted"] for e in result.response["events"]), 20)
            self.assertEqual(result.response["events"][-1]["reason"], "tactical-task-cap")
            self.assertTrue(result.response["strategic"]["accepted"])
            model.scope = "tactical"

            async def next_task(task, perspective, guidance):
                return await guidance.observe_step("Planner", "Base", model_output="Next task")

            next_result = (await controller.run_task({**TASK, "task_id": "task-2"}, next_task, namespace=NAMESPACE))[0]
            self.assertTrue(next_result.response["accepted"])

    async def test_real_sdk_consolidation_conflict_subsumption_then_merge(self):
        with tempfile.TemporaryDirectory() as directory:
            model = MetaModel(consolidate=True)
            controller = ScopePaperController(model, Path(directory),
                                             config=PaperConfig(perspectives=("efficiency",)))

            async def execute(task, perspective, guidance):
                events = [await guidance.observe_step("Planner", "Base", model_output=f"Step {i}") for i in range(11)]
                return {"last": events[-1]}

            result = (await controller.run_task(TASK, execute, namespace=NAMESPACE))[0]
            self.assertEqual(result.status, "completed", result.error)
            self.assertEqual(result.response["last"]["optimization"], {"triggered": True, "before": 11, "after": 7})
            self.assertEqual([k for k, _ in model.calls if k in ("analysis", "conflict", "subsumption", "merge")],
                             ["analysis", "conflict", "subsumption", "merge"])
            memory = json.loads(next(Path(directory).rglob("strategic.json")).read_text())
            self.assertEqual(len(memory["rules"]["tool_usage"]), 7)
            self.assertFalse(any("_opt_id" in r for r in memory["rules"]["tool_usage"]))

    async def test_injected_budget_error_cannot_be_swallowed_by_sdk(self):
        class BudgetExceededModel:
            async def generate(self, messages):
                raise RuntimeError("Injected model budget exhausted")

        with tempfile.TemporaryDirectory() as directory:
            controller = ScopePaperController(BudgetExceededModel(), Path(directory))

            async def execute(task, perspective, guidance):
                await guidance.observe_step("Planner", "Base", model_output="Observed step")
                return {"unreachable": True}

            results = await controller.run_task(TASK, execute, namespace=NAMESPACE)
            self.assertTrue(all(r.status == "error" and "budget exhausted" in r.error for r in results))
            self.assertTrue(all(r.response is None for r in results))
            self.assertEqual(list(Path(directory).rglob("strategic.json")), [])

    def test_configuration_rejects_unknown_perspectives_and_nonfinite_threshold(self):
        with self.assertRaises(ValueError):
            PaperConfig(perspectives=("invented-persona",))
        with self.assertRaises(ValueError):
            PaperConfig(accept_threshold=float("nan"))


if __name__ == "__main__":
    unittest.main()
