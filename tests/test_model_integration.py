"""Mock transports execute real optimizers; these establish no model efficacy."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from evaluation.models import BudgetedModel, BudgetExceeded, ModelConfig
from evaluation.run_models import (
    ActualMemoryAdapter, CONDITIONS, HISTORICAL_V02_COMMIT, REPOSITORY,
    TerminalGuidance, evaluation_plan, main, run_model_evaluation,
)
from evaluation.scenarios import pilot_sequences
from evaluation.scope_paper import ScopePaperController


def configuration(**overrides):
    values = dict(provider="openai-compatible", model="mock-selected-model",
        base_url="https://mock-provider.invalid/v1", api_key_env="EVOLVECLAW_EVAL_MOCK_KEY",
        max_cost_usd=10., input_usd_per_million=1., output_usd_per_million=2., max_calls=1000)
    values.update(overrides)
    return ModelConfig(**values)


class FixtureTransport:
    """Only public inputs determine answers; no fixture keys or scorer access."""
    def __init__(self):
        self.requests = []
        self.learning = 0

    async def __call__(self, url, payload, headers, timeout):
        self.requests.append(deepcopy(payload))
        messages = payload["messages"]
        text = "\n".join(message["content"] for message in messages)
        if "selected_index" in text and "candidate prompt updates" in text:
            response = {"selected_index": 0, "rationale": "Offline candidate-selection mechanics"}
        elif "=== PROPOSED UPDATE ===" in text:
            response = {"is_duplicate": False, "scope": "strategic", "confidence": .9,
                        "domain": "error_handling", "reason": "Offline classifier mechanics"}
        elif "update_text" in text and ("analyzing" in text or "Generate a SHORT" in text):
            self.learning += 1
            response = {"update_text": f"Check observed tool status before claiming completion ({self.learning}).",
                        "rationale": "An observed simulated result is available", "confidence": "high"}
        elif messages[0]["role"] == "system":
            task = json.loads(messages[1]["content"])
            if len(messages) == 2 and task["tools"] and task.get("executing_role") == "Planner":
                response = {"tool_calls": [], "delegations": [{"role": "Browser", "instruction": task["instruction"]}], "answer": None}
            elif len(messages) == 2 and task["tools"]:
                response = {"tool_calls": task["tools"], "answer": None}
            elif task["tools"]:
                observations = json.loads(messages[-1]["content"].split(": ", 1)[1])
                result = observations[0]["result"]
                answer = {"completed": result["completed"] if "completed" in result else result.get("status") == "completed"}
                response = {"tool_calls": [], "answer": answer}
            else:
                response = {"tool_calls": [], "answer": {"acknowledged": True}}
        elif "consolidation" in text and "subsumption" in text:
            response = {"consolidation": [], "subsumption": [], "conflicts": []}
        else:
            raise AssertionError("Unexpected mock prompt; do not fabricate an optimizer result")
        return {"choices": [{"message": {"content": json.dumps(response)}}],
                "usage": {"prompt_tokens": 80, "completion_tokens": 30}}


class ModelIntegrationTests(unittest.TestCase):
    def test_plan_does_not_read_credentials_create_clients_or_call_models(self):
        with patch("evaluation.models.BudgetedModel", side_effect=AssertionError("No model in plan")), \
             patch("evaluation.models.os.environ.get", side_effect=AssertionError("No credentials in plan")):
            plan = evaluation_plan(configuration(), sequence_limit=1)
        self.assertEqual(plan["api_calls"], 0)
        self.assertFalse(plan["spending_authorized_by_plan"])
        self.assertFalse(plan["efficacy_evidence"])
        self.assertEqual(plan["baseline_commit"], HISTORICAL_V02_COMMIT)
        self.assertEqual(plan["conditions"], list(CONDITIONS))
        self.assertFalse(plan["model_configuration"]["opt_in"])

    def test_planned_splits_are_rejected_and_cli_defaults_to_plan(self):
        for split in ("development", "heldout"):
            with self.assertRaisesRegex(ValueError, "no executable fixtures"):
                evaluation_plan(configuration(), split=split)
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO):
            output = Path(tmp) / "plan"
            main(["--provider", "openai-compatible", "--model", "explicit-model",
                  "--base-url", "https://mock-provider.invalid/v1", "--api-key-env", "EXPLICIT_ENV_NAME",
                  "--max-cost-usd", "1", "--input-usd-per-million", "1", "--output-usd-per-million", "2",
                  "--split", "pilot", "--sequence-limit", "1", "--output", str(output)])
            self.assertEqual(json.loads((output / "plan.json").read_text())["api_calls"], 0)
            self.assertEqual(list(output.iterdir()), [output / "plan.json"])

    def test_execution_requires_explicit_mode_before_creating_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "no-opt-in"
            with self.assertRaisesRegex(ValueError, "opt_in"):
                asyncio.run(run_model_evaluation(configuration(), output, sequence_limit=1))
            self.assertFalse(output.exists())
            with self.assertRaisesRegex(ValueError, "offline_mock"):
                asyncio.run(run_model_evaluation(configuration(), output, transport=FixtureTransport()))
            self.assertFalse(output.exists())

    def test_mock_provider_runs_actual_historical_current_sdk_and_paper_algorithms(self):
        transport = FixtureTransport()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "actual-algorithms"
            original_get = os.environ.get
            def no_mock_secret_read(name, default=None):
                if name == "EVOLVECLAW_EVAL_MOCK_KEY":
                    raise AssertionError("Mock must not read the selected credential")
                return original_get(name, default)
            with patch("evaluation.models.os.environ.get", side_effect=no_mock_secret_read):
                summary = asyncio.run(run_model_evaluation(configuration(), output, sequence_limit=1,
                                      transport=transport, offline_mock=True))
            self.assertEqual(summary["sequence_runs"], 5)
            self.assertEqual(summary["live_api_calls"], 0)
            self.assertFalse(summary["efficacy_evidence"])
            self.assertFalse(summary["surrogate_learning_algorithm"])
            self.assertEqual(summary["primary_comparison"]["paired_sequences"], 1)
            self.assertGreater(summary["usage"]["request_count"], 0)
            self.assertEqual(summary["usage"]["request_count"], len(transport.requests))
            for condition in CONDITIONS:
                files = list((output / "run-001" / condition).glob("*/memory/adapter_metadata.json"))
                if condition == "scope_paper_k2_n2":
                    files = list((output / "run-001" / condition).glob("*/adapter_metadata.json"))
                self.assertEqual(len(files), 1, condition)
                metadata = json.loads(files[0].read_text())
                self.assertEqual(metadata["condition"], condition)
                if condition == "repaired-v0.2":
                    self.assertEqual(metadata["historical_source"]["commit"], HISTORICAL_V02_COMMIT)
                    original = subprocess.run(["git", "show", f"{HISTORICAL_V02_COMMIT}:server/task_optimizer.py"],
                                              cwd=REPOSITORY, check=True, capture_output=True).stdout
                    archived = files[0].parent / "historical-source/server/task_optimizer.py"
                    self.assertEqual(archived.read_bytes(), original)
                    self.assertEqual(metadata["historical_source"]["source_sha256"]["server/task_optimizer.py"],
                                     sha256(original).hexdigest())
                if condition == "scope_sdk_reference":
                    self.assertTrue(metadata["unmodified_upstream_defaults"])
                    self.assertFalse(metadata["task_counter_reset_supported"])
            state = list((output / "run-001/improved").glob("*/memory/scoped-state/memory.sqlite3"))
            self.assertEqual(len(state), 1)
            requests = json.dumps(transport.requests)
            for private_name in ("required_fields", "metric_tags", "mistake_key", "scoring_keys", "failed_fields"):
                self.assertNotIn(private_name, requests)
            paper_trace = list((output / "run-001/scope_paper_k2_n2").glob("*/scorer_only_trace.json"))[0]
            rows = json.loads(paper_trace.read_text())
            for row in rows:
                if row["event"] == "task":
                    self.assertEqual(row["response_selection"], "fixed-efficiency-before-scoring")
                    self.assertEqual({p["perspective"] for p in row["perspectives"]}, {"efficiency", "thoroughness"})
                    self.assertEqual(len(row["callbacks"]), 2)
                    calls = [callback["runs"][0]["tool_calls"] for callback in row["callbacks"]]
                    self.assertEqual([len(c) for c in calls], [1, 1])
                    for callback in row["callbacks"]:
                        self.assertTrue(callback["runs"][0]["hierarchical"])
                        self.assertEqual({i["role"] for i in callback["runs"][0]["role_invocations"]}, {"Planner", "Browser"})
            with self.assertRaises(FileExistsError):
                asyncio.run(run_model_evaluation(configuration(), output, sequence_limit=1,
                            transport=transport, offline_mock=True))

    def test_shared_budget_stops_upstream_swallowed_failure_without_complete_report(self):
        transport = FixtureTransport()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "capped"
            with self.assertRaises(BudgetExceeded):
                asyncio.run(run_model_evaluation(configuration(max_calls=2), output,
                    conditions=("repaired-v0.2",), sequence_limit=1, transport=transport, offline_mock=True))
            aborted = json.loads((output / "incomplete.json").read_text())
            self.assertEqual(aborted["usage"]["request_count"], 2)
            self.assertEqual(len(transport.requests), 2)
            self.assertFalse(aborted["efficacy_evidence"])
            self.assertFalse((output / "summary.json").exists())

    def test_actual_scoping_and_feedback_history_undo_preserve_unrelated_rule(self):
        async def exercise(directory):
            model = BudgetedModel(configuration(opt_in=True), transport=FixtureTransport())
            improved = ActualMemoryAdapter("improved", model, directory / "improved")
            repaired = ActualMemoryAdapter("repaired-v0.2", model, directory / "repaired")
            scope = {"audience_key": "sim:user-a", "project_key": "sim:project-a"}
            other = {**scope, "project_key": "sim:project-b"}
            public = {"task_id": "feedback-turn", "instruction": "Check tool status before claiming completion.",
                      "scope": scope, "tools": [], "topic": "tool-status"}
            async def learn(adapter, task_id, feedback):
                task = {**public, "task_id": task_id}
                guidance = TerminalGuidance(adapter.condition, adapter, task, "session-a")
                await guidance.observe_step("Planner", "Base instructions", model_output="Operation failed.",
                    observations="Public fake tool reported failure.", error=RuntimeError("Observed fake tool failure"))
                return await adapter.finish(guidance, {"completed": False}, feedback=feedback)
            first = await learn(improved, "feedback-turn", True)
            self.assertTrue(first["accepted"])
            self.assertEqual(improved.guidelines(other, "session-b")["strategic"], [])
            await learn(repaired, "feedback-turn", True)
            self.assertTrue(repaired.guidelines(other, "session-b")["strategic"])
            unrelated = await learn(improved, "later-autonomous-turn", False)
            self.assertTrue(unrelated["accepted"])
            undo = improved.rollback(scope, "session-a")
            self.assertTrue(undo["changed"])
            active = improved.optimizer.memory_store.active_rules(improved.agent_name, scope)
            self.assertEqual([r["id"] for r in active], [unrelated["rule_id"]])
            self.assertFalse(repaired.rollback(scope, "session-a")["supported"])
        with tempfile.TemporaryDirectory() as tmp:
            asyncio.run(exercise(Path(tmp)))

    def test_pure_paper_namespace_does_not_route_memory_by_user_or_project(self):
        original = ScopePaperController.run_task
        for family in ("user-preference", "project-format"):
            sequence = next(s for s in pilot_sequences() if s.family_id == family)
            namespaces, scopes = [], []
            async def capture(controller, public_task, execute, *, namespace):
                namespaces.append(deepcopy(namespace))
                scopes.append(deepcopy(public_task["scope"]))
                return await original(controller, public_task, execute, namespace=namespace)
            with tempfile.TemporaryDirectory() as tmp, \
                 patch("evaluation.run_models.pilot_sequences", return_value=[sequence]), \
                 patch.object(ScopePaperController, "run_task", new=capture):
                output = Path(tmp) / "paper"
                summary = asyncio.run(run_model_evaluation(configuration(), output,
                    conditions=("scope_paper_k2_n2",), transport=FixtureTransport(), offline_mock=True))
                self.assertEqual(summary["sequence_runs"], 1)
                self.assertGreater(len({json.dumps(scope, sort_keys=True) for scope in scopes}), 1)
                self.assertTrue(all(ns == {"sequence_id": sequence.sequence_id} for ns in namespaces))
                metadata = json.loads(next((output / "run-001/scope_paper_k2_n2").glob("*/adapter_metadata.json")).read_text())
                self.assertIn("no-user-project-routing", metadata["memory_namespace_policy"])

    def test_missing_historical_source_never_substitutes_current_optimizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "baseline-missing"
            with patch("evaluation.run_models._archive_historical", side_effect=ValueError("Genuine source unavailable")):
                with self.assertRaisesRegex(ValueError, "Genuine source unavailable"):
                    asyncio.run(run_model_evaluation(configuration(), output, conditions=("repaired-v0.2",),
                                sequence_limit=1, transport=FixtureTransport(), offline_mock=True))
            self.assertFalse((output / "summary.json").exists())
            self.assertEqual(json.loads((output / "incomplete.json").read_text())["usage"]["request_count"], 0)


if __name__ == "__main__":
    unittest.main()
