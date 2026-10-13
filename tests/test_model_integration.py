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
import importlib.util
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

    def test_heldout_is_planned_and_priced_cli_defaults_to_plan(self):
        for split in ("heldout",):
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

    @unittest.skipUnless(importlib.util.find_spec("evaluation.development_scenarios"), "Development authoring module pending")
    def test_authored_development_split_has_family_clusters(self):
        plan = evaluation_plan(configuration(), split="development", conditions=("learning-off",))
        self.assertEqual(plan["sequence_runs"], 100)
        self.assertEqual(plan["family_clusters"], 20)
        self.assertTrue(all(sequence_id.startswith("development.") for sequence_id in plan["sequence_ids"]))

    def test_exact_sequence_selection_rejects_unknown_and_duplicate_ids(self):
        sequences = pilot_sequences()
        first = sequences[0]
        second = next(sequence for sequence in sequences if sequence.family_id != first.family_id)
        plan = evaluation_plan(configuration(), conditions=("learning-off",), sequence_ids=[second.sequence_id, first.sequence_id])
        self.assertEqual(plan["sequence_ids"], [second.sequence_id, first.sequence_id])
        self.assertEqual(plan["family_clusters"], 2)
        for ids in ([first.sequence_id, first.sequence_id], ["not-authored"]):
            with self.assertRaises(ValueError):
                evaluation_plan(configuration(), sequence_ids=ids)

    def test_native_token_plan_cli_needs_no_fake_prices_or_secret_lookup(self):
        first = pilot_sequences()[0].sequence_id
        original_get = os.environ.get
        def no_native_secret(name, default=None):
            if name == "OPENCLAW_MANAGED_AUTH":
                raise AssertionError("No secret in plan")
            return original_get(name, default)
        with tempfile.TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO), \
             patch("evaluation.models.os.environ.get", side_effect=no_native_secret):
            output = Path(tmp) / "token-plan"
            main(["--provider", "xiaomi-mimo", "--model", "mimo-v2.6-flash",
                  "--base-url", "https://token-plan-ams.xiaomimimo.com/v1",
                  "--execution-backend", "native-openclaw", "--max-total-tokens", "2000000",
                  "--max-quota-credits", "250000000", "--quota-uncached-input-credits", "100",
                  "--quota-cached-input-credits", "2", "--quota-output-credits", "200",
                  "--split", "pilot", "--sequence-id", first, "--output", str(output)])
            plan = json.loads((output / "plan.json").read_text())
            self.assertEqual(plan["model_configuration"]["api_key_env"], "OPENCLAW_MANAGED_AUTH")
            self.assertIsNone(plan["model_configuration"]["max_cost_usd"])
            self.assertIsNone(plan["model_configuration"]["input_usd_per_million"])
            self.assertEqual(plan["model_configuration"]["max_total_tokens"], 2_000_000)
            self.assertEqual(plan["provider_settings"]["thinking"], "disabled")
            self.assertEqual(plan["provider_settings"]["currency_pricing_status"], "unknown")

    def test_token_only_actual_algorithm_mock_run_reports_unknown_currency(self):
        config = configuration(provider="xiaomi-mimo", model="mimo-v2.6-flash", max_cost_usd=None,
            input_usd_per_million=None, output_usd_per_million=None, max_total_tokens=2_000_000,
            max_quota_credits=250_000_000, quota_uncached_input_credits=100,
            quota_cached_input_credits=2, quota_output_credits=200)
        with tempfile.TemporaryDirectory() as tmp:
            summary = asyncio.run(run_model_evaluation(config, Path(tmp) / "token-only",
                conditions=("repaired-v0.2", "improved"), sequence_limit=1,
                transport=FixtureTransport(), offline_mock=True))
        self.assertEqual(summary["live_api_calls"], 0)
        self.assertIsNone(summary["usage"]["accounted_budget_usd"])
        self.assertEqual(summary["usage"]["cost_status"], "unknown")
        self.assertGreater(summary["usage"]["known_total_tokens"], 0)
        for condition in ("repaired-v0.2", "improved"):
            self.assertIsNone(summary["conditions"][condition]["usage"]["accounted_budget_usd"])
            self.assertGreater(summary["conditions"][condition]["usage"]["known_total_tokens"], 0)

    def test_native_cli_warm_worker_is_closed_on_success_and_failure(self):
        instances = []
        class Native:
            def __init__(self, *args, **kwargs):
                self.options, self.closed = kwargs, False
                instances.append(self)
            async def close(self):
                self.closed = True
        for fail in (False, True):
            async def execute(*args, **kwargs):
                if fail:
                    raise RuntimeError("Injected evaluation failure")
                return {"efficacy_evidence": False, "evidence_kind": "injected-test"}
            with tempfile.TemporaryDirectory() as tmp, patch("sys.stdout", new_callable=io.StringIO), \
                 patch("evaluation.openclaw_transport.NativeOpenClawTransport", new=Native), \
                 patch("evaluation.run_models.run_model_evaluation", new=execute):
                arguments = ["--execute", "--provider", "xiaomi-mimo", "--model", "mimo-v2.6-flash",
                    "--base-url", "https://token-plan-ams.xiaomimimo.com/v1", "--execution-backend", "native-openclaw",
                    "--max-total-tokens", "2000000", "--max-quota-credits", "250000000",
                    "--quota-uncached-input-credits", "100", "--quota-cached-input-credits", "2", "--quota-output-credits", "200",
                    "--openclaw-cli", "/explicit/openclaw", "--openclaw-config", "/explicit/native.json",
                    "--openclaw-workspace", "/explicit/workspace", "--openclaw-warm-worker", "--node-path", "/explicit/node",
                    "--split", "pilot", "--sequence-limit", "1", "--output", str(Path(tmp) / "native")]
                if fail:
                    with self.assertRaisesRegex(RuntimeError, "Injected evaluation failure"):
                        main(arguments)
                else:
                    main(arguments)
                self.assertTrue(instances[-1].closed)
                self.assertTrue(instances[-1].options["warm_worker"])
                self.assertEqual(instances[-1].options["node_path"], Path("/explicit/node"))

    def test_parallel_sequence_jobs_preserve_memory_isolation_and_canonical_order(self):
        class Delayed(FixtureTransport):
            def __init__(self):
                super().__init__()
                self.active, self.maximum = 0, 0
            async def __call__(self, *args):
                self.active += 1
                self.maximum = max(self.maximum, self.active)
                try:
                    await asyncio.sleep(.002)
                    return await super().__call__(*args)
                finally:
                    self.active -= 1
        first = pilot_sequences()[0]
        second = next(sequence for sequence in pilot_sequences() if sequence.family_id != first.family_id)
        ids = [second.sequence_id, first.sequence_id]
        transport = Delayed()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "parallel"
            summary = asyncio.run(run_model_evaluation(configuration(), output, conditions=("learning-off", "improved"),
                sequence_ids=ids, transport=transport, offline_mock=True, max_concurrent_sequences=3))
            rows = json.loads((output / "sequence_results.json").read_text())
            self.assertEqual([(row["condition"], row["sequence_id"]) for row in rows],
                             [(condition, sequence_id) for condition in ("learning-off", "improved") for sequence_id in ids])
            stores = list((output / "run-001/improved").glob("*/memory/scoped-state/memory.sqlite3"))
            self.assertEqual(len(stores), 2)
            self.assertEqual(summary["max_concurrent_sequences"], 3)
            self.assertGreater(transport.maximum, 1)
            self.assertLessEqual(transport.maximum, 3)
            self.assertEqual(transport.active, 0)

    def test_parallel_budget_failure_cancels_and_joins_pending_jobs(self):
        class Pending(FixtureTransport):
            def __init__(self):
                super().__init__()
                self.dispatched, self.active, self.cancelled = 0, 0, False
            async def __call__(self, *args):
                self.dispatched += 1
                number = self.dispatched
                self.active += 1
                try:
                    if number == 2:
                        await asyncio.Event().wait()
                    await asyncio.sleep(.005)
                    return await super().__call__(*args)
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise
                finally:
                    self.active -= 1
        transport = Pending()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "parallel-capped"
            with self.assertRaises(BudgetExceeded):
                asyncio.run(run_model_evaluation(configuration(max_calls=2), output, conditions=("learning-off",),
                    sequence_limit=2, transport=transport, offline_mock=True, max_concurrent_sequences=2))
            incomplete = json.loads((output / "incomplete.json").read_text())
            self.assertEqual(incomplete["usage"]["request_count"], 2)
            self.assertFalse((output / "summary.json").exists())
            self.assertTrue(transport.cancelled)
            self.assertEqual(transport.active, 0)
            self.assertEqual(transport.dispatched, 2)

    def test_native_evidence_excludes_model_text_headers_and_diagnostics(self):
        from types import SimpleNamespace
        from evaluation.run_models import native_transport_evidence
        transport = SimpleNamespace(config_sha256="pinned-hash", budget_contract={"max_provider_attempts": None},
            events=[{"status": "completed", "config_sha256": "pinned-hash", "model": "mimo-v2.6-flash",
                     "final": "private-response", "headers": {"Authorization": "private-header"}, "stderr": "private-diagnostic",
                     "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 110,
                               "prompt_tokens_details": {"cached_tokens": 80}, "private": "not-exported"},
                     "worker": {"openclaw_version": "2026.10.2", "entry_source_sha256": "entry-hash",
                                "internal_entry": True, "persistent_worker": True, "model_requests_serialized": True,
                                "private": "not-exported"}}])
        evidence = native_transport_evidence(transport)
        text = json.dumps(evidence)
        for private in ("private-response", "private-header", "private-diagnostic", "not-exported"):
            self.assertNotIn(private, text)
        self.assertEqual(evidence["worker"]["entry_source_sha256"], "entry-hash")
        self.assertEqual(evidence["events"][0]["usage"]["total_tokens"], 110)

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
