"""Evaluation harness mechanics. These tests establish no real-model efficacy."""
import json
from pathlib import Path
import tempfile
import unittest
import asyncio
import importlib.util
from unittest.mock import patch

from evaluation.reporting import paired_cluster_comparison
from evaluation.runner import run_pilot
from evaluation.scenarios import FakeWorld, Feedback, Task, planned_manifest, pilot_sequences, validate_manifest
from evaluation.scoring import score_response
from evaluation.storage_smoke import run_storage_smoke


class EvaluationTests(unittest.TestCase):
    @unittest.skipUnless(importlib.util.find_spec("scope"), "Optional scope-optimizer==0.1.3 is required for actual SDK reference")
    def test_scope_reference_runs_upstream_defaults_and_persists(self):
        from scope import SCOPEOptimizer
        from scope.prompts import CLASSIFICATION_PROMPT
        from evaluation.scope_reference import ScopeSDKReference, ScriptedScopeModel, run_reference_smoke
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "reference"
            report = asyncio.run(run_reference_smoke(path))
            self.assertEqual(report["condition"], "scope_sdk_reference")
            self.assertEqual(report["sdk_version"], "0.1.3")
            self.assertTrue(report["actual_upstream_optimizer"])
            self.assertFalse(report["task_quality_measured"])
            self.assertFalse(report["full_paper_replication"])
            self.assertEqual(report["scripted_generate_calls"], 4)
            self.assertEqual(report["live_api_calls"], 0)
            restored = ScopeSDKReference(path, ScriptedScopeModel([]), resume=True)
            self.assertIs(type(restored.optimizer), SCOPEOptimizer)
            self.assertIs(restored.optimizer._classification_prompt, CLASSIFICATION_PROMPT)
            self.assertEqual(restored.optimizer.allowed_domains, SCOPEOptimizer.ALLOWED_DOMAINS)
            self.assertEqual(restored.optimizer._custom_prompts, {})
            self.assertFalse(restored.optimizer.synthesizer.use_best_of_n)
            self.assertFalse(restored.reset_task("agent", "task")["supported"])
            with self.assertRaises(FileExistsError):
                ScopeSDKReference(path, ScriptedScopeModel([]))
            with self.assertRaises(ValueError):
                ScopeSDKReference(Path(root) / "bad", None)
            with self.assertRaises(ValueError):
                ScopeSDKReference(Path(root) / "unmarked", object())

    def test_manifest_counts_authorship_and_family_disjointness(self):
        rows = planned_manifest()
        validate_manifest(rows)
        for split, count in (("pilot", 20), ("development", 100), ("diagnostic", 50), ("heldout", 500)):
            self.assertEqual(sum(row["split"] == split for row in rows), count)
        self.assertEqual(len({s.cluster_id for s in pilot_sequences()}), 10)
        self.assertTrue(all(row["fixture_status"] == "authored" for row in rows if row["split"] in ("diagnostic", "heldout")))
        self.assertTrue(all(row["fixture_status"] == "authored" for row in rows if row["split"] == "development"))
        corrupt = [dict(rows[0]), {**rows[0], "sequence_id": "different", "split": "heldout"}]
        with self.assertRaisesRegex(ValueError, "crosses splits"):
            validate_manifest(corrupt)

    def test_public_observations_exclude_grading_keys(self):
        for sequence in pilot_sequences():
            for event in sequence.events:
                if isinstance(event, (Task, Feedback)):
                    public = json.dumps(event.public_request())
                    for grading_field in ("required_fields", "metric_tags", "mistake_key", "expected_response", "scoring_keys"):
                        self.assertNotIn(grading_field, public)
                    if isinstance(event, Task):
                        self.assertNotIn("result", event.public_request()["tools"][0])

    def test_fake_tools_are_isolated_and_reject_unknown_actions(self):
        task = next(e for e in pilot_sequences()[0].events if isinstance(e, Task))
        world = FakeWorld(task)
        tool = task.tools[0]
        result = world.call(tool.name, tool.arguments)
        result["status"] = "completed"
        self.assertEqual(world.call(tool.name, tool.arguments)["status"], "failed")
        with self.assertRaises(ValueError):
            world.call("real-calendar.delete", {})
        with self.assertRaises(ValueError):
            world.call(tool.name, {"item": "wrong"})

    def test_scoring_requires_exact_structured_types(self):
        key = pilot_sequences()[0].scoring_keys[next(e.task_id for e in pilot_sequences()[0].events if isinstance(e, Task))]
        self.assertFalse(score_response({"completed": 0}, key)["success"])
        self.assertTrue(score_response({"completed": False}, key)["success"])
        self.assertFalse(score_response({}, key)["success"])

    def test_offline_pilot_is_isolated_and_explicitly_not_efficacy(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / "pilot"
            summary = run_pilot(output)
            self.assertEqual(summary["sequence_runs"], 60)
            self.assertEqual(summary["future_tasks_per_condition"], 40)
            self.assertEqual(summary["primary_comparison"]["family_cluster_count"], 10)
            self.assertTrue(summary["surrogate"])
            self.assertFalse(summary["efficacy_evidence"])
            self.assertEqual(summary["usage"]["model_calls"], 0)
            self.assertIsNone(summary["usage"]["real_evaluation_cost"]["amount"])
            memory_paths = list(output.glob("*/pilot.*/memory/memory.json"))
            self.assertEqual(len(memory_paths), 60)
            self.assertTrue(all(json.loads(path.read_text())["adapter"] == "scripted-surrogate" for path in memory_paths))
            self.assertEqual(summary["conditions"]["improved"]["metrics"]["scope_leakage"]["count"], 0)
            self.assertGreater(summary["conditions"]["repaired-v0.2"]["metrics"]["scope_leakage"]["count"], 0)
            self.assertEqual(summary["conditions"]["improved"]["metrics"]["rollback_recurrence"]["count"], 0)
            with self.assertRaises(FileExistsError):
                run_pilot(output)

    def test_paired_reporting_rejects_unmatched_results(self):
        def row(condition, seq, cluster, rate):
            return {"condition": condition, "sequence_id": seq, "cluster_id": cluster,
                    "future_success_rate": rate, "records": [{"task_id": seq + ".task", "phase": "future"}]}
        pairs = [row("repaired-v0.2", "one", "cluster-1", .5), row("improved", "one", "cluster-1", 1),
                 row("repaired-v0.2", "two", "cluster-1", .5), row("improved", "two", "cluster-1", 1)]
        comparison = paired_cluster_comparison(pairs, bootstrap_samples=100)
        self.assertEqual(comparison["paired_sequences"], 2)
        self.assertEqual(comparison["family_cluster_count"], 1)
        self.assertEqual(comparison["future_success_rate_difference"], .5)
        with self.assertRaises(ValueError):
            paired_cluster_comparison(pairs[:-1])
        with self.assertRaises(ValueError):
            paired_cluster_comparison([*pairs, pairs[0]])

    def test_real_model_configuration_does_not_trigger_spending(self):
        from dataclasses import replace
        from evaluation.models import ModelConfig, BudgetedModel
        calls = []
        async def transport(*args):
            calls.append(args)
            raise AssertionError("Configuration must not issue a request")
        config = ModelConfig("openai-compatible", "selected-model", "https://example.invalid/v1", "EXPLICIT_TEST_KEY", 2.0, 1.0, 2.0)
        with self.assertRaisesRegex(ValueError, "opt_in"):
            BudgetedModel(config, transport=transport)
        enabled = replace(config, opt_in=True)
        BudgetedModel(enabled, transport=transport)
        self.assertAlmostEqual(enabled.reservation_cost(), .034816)
        self.assertEqual(calls, [])
        with self.assertRaises(ValueError):
            replace(enabled, max_cost_usd=float("nan")).validate()
        with self.assertRaisesRegex(ValueError, "environment-variable identifier"):
            replace(enabled, api_key_env="sk-example-pasted-value").public_dict()

    def test_actual_memory_store_isolation_outcome_and_rollback(self):
        with tempfile.TemporaryDirectory() as root:
            result = run_storage_smoke(Path(root) / "actual-store")
            self.assertTrue(result["actual_memory_store"])
            self.assertEqual(result["model_calls"], 0)
            self.assertFalse(result["efficacy_evidence"])
            self.assertEqual(len(result["checks"]), 9)

    def test_budget_reservation_bounds_concurrent_calls_and_unknown_usage(self):
        from evaluation.models import BudgetExceeded, BudgetedModel, ModelConfig
        calls = []
        async def transport(url, payload, headers, timeout):
            calls.append(payload)
            return {"choices": [{"message": {"content": "{}"}}]}
        config = ModelConfig("openai-compatible", "test-model", "https://example.invalid/v1", "EXPLICIT_TEST_KEY",
                             .009, 1, 1, max_input_tokens=8192, max_output_tokens=32, opt_in=True)
        model = BudgetedModel(config, transport=transport)
        async def run():
            return await asyncio.gather(*(model.generate([{"role": "user", "content": "Hello"}]) for _ in range(3)), return_exceptions=True)
        outcomes = asyncio.run(run())
        self.assertEqual(len(calls), 1)
        self.assertEqual(sum(isinstance(result, BudgetExceeded) for result in outcomes), 2)
        self.assertEqual(calls[0]["max_tokens"], 32)
        snapshot = model.ledger.snapshot()
        self.assertEqual(snapshot["unknown_usage_calls"], 1)
        self.assertAlmostEqual(snapshot["accounted_budget_usd"], config.reservation_cost())
        self.assertNotIn("injected-offline-transport-no-live-key", json.dumps(snapshot))

    def test_provider_adapters_actual_usage_and_explicit_credential_boundary(self):
        from evaluation.models import BudgetedModel, ModelConfig
        requests = []
        async def transport(url, payload, headers, timeout):
            requests.append((url, payload))
            return {"content": [{"type": "text", "text": "a reply"}],
                    "usage": {"input_tokens": 120, "output_tokens": 12}}
        config = ModelConfig("anthropic", "test-model", "https://example.invalid/v1", "EXPLICIT_TEST_KEY",
                             1, 1, 2, max_input_tokens=8192, max_output_tokens=64, opt_in=True)
        model = BudgetedModel(config, transport=transport).for_stage("synthesis")
        reply = asyncio.run(model.generate([{"role": "system", "content": "system"}, {"role": "user", "content": "hello"}]))
        self.assertEqual(reply.content, "a reply")
        self.assertEqual(requests[0][0], "https://example.invalid/v1/messages")
        self.assertEqual(requests[0][1]["max_tokens"], 64)
        self.assertEqual(model.ledger.snapshot()["actual_usage_calls"], 1)
        self.assertAlmostEqual(model.ledger.snapshot()["accounted_budget_usd"], .000144)
        with patch.dict("os.environ", {}, clear=True), patch("evaluation.models._http_transport", transport):
            live_model = BudgetedModel(config)
            with self.assertRaisesRegex(ValueError, "environment variable is missing"):
                asyncio.run(live_model.generate([{"role": "user", "content": "hello"}]))
        self.assertEqual(len(requests), 1)
        config.validate(require_opt_in=False)

    def test_token_only_mimo_counts_cached_and_reasoning_tokens_once(self):
        from evaluation.models import BudgetedModel, ModelConfig
        requests = []
        async def transport(url, payload, headers, timeout):
            requests.append(payload)
            return {"choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100,
                              "prompt_tokens_details": {"cached_tokens": 800},
                              "completion_tokens_details": {"reasoning_tokens": 30}, "cost": {"total": 0}}}
        config = ModelConfig("xiaomi-mimo", "mimo-v2.6-flash", "https://api.xiaomimimo.com/v1", "EXPLICIT_TEST_KEY",
                             max_input_tokens=8192, max_output_tokens=128, max_total_tokens=40_000,
                             max_quota_credits=2_000_000, quota_uncached_input_credits=100,
                             quota_cached_input_credits=2, quota_output_credits=200, opt_in=True)
        model = BudgetedModel(config, transport=transport)
        asyncio.run(model.generate([{"role": "user", "content": "hello"}]))
        self.assertEqual(requests[0]["max_completion_tokens"], 128)
        self.assertEqual(requests[0]["thinking"], {"type": "disabled"})
        self.assertNotIn("max_tokens", requests[0])
        usage = model.ledger.snapshot()
        self.assertEqual(usage["accounted_total_tokens"], 1100)
        self.assertEqual(usage["accounted_quota_credits"], 41_600)
        self.assertIsNone(usage["accounted_budget_usd"])
        self.assertEqual(usage["cost_status"], "unknown")
        self.assertEqual(usage["calls"][0]["reasoning_tokens"], 30)

    def test_token_and_credit_caps_keep_unknown_reservations_across_stages(self):
        from evaluation.models import BudgetExceeded, BudgetedModel, ModelConfig
        for caps in ({"max_total_tokens": 9000, "max_quota_credits": 2_000_000},
                     {"max_total_tokens": 40_000, "max_quota_credits": 900_000}):
            calls = []
            async def transport(*args):
                calls.append(args)
                return {"choices": [{"message": {"content": "{}"}}]}
            config = ModelConfig("xiaomi-mimo", "mimo-v2.6-flash", "https://api.xiaomimimo.com/v1", "EXPLICIT_TEST_KEY",
                max_input_tokens=8192, max_output_tokens=128, quota_uncached_input_credits=100,
                quota_cached_input_credits=2, quota_output_credits=200, opt_in=True, **caps)
            model = BudgetedModel(config, transport=transport)
            asyncio.run(model.for_stage("solver").generate([{"role": "user", "content": "first"}]))
            with self.assertRaises(BudgetExceeded):
                asyncio.run(model.for_stage("paper:reflection").generate([{"role": "user", "content": "second"}]))
            self.assertEqual(len(calls), 1)
            self.assertEqual(model.ledger.snapshot()["reserved_unknown_tokens"], 8320)
            self.assertEqual(model.ledger.snapshot()["accounted_quota_credits"], 844_800)
            self.assertIsNone(model.ledger.snapshot()["accounted_budget_usd"])

    def test_unknown_cache_is_uncached_and_invalid_usage_cannot_release_budget(self):
        from evaluation.models import BudgetExceeded, BudgetedModel, ModelConfig
        config = ModelConfig("xiaomi-mimo", "mimo-v2.6-flash", "https://api.xiaomimimo.com/v1", "EXPLICIT_TEST_KEY",
            max_input_tokens=8192, max_output_tokens=128, max_total_tokens=40_000,
            max_quota_credits=2_000_000, quota_uncached_input_credits=100,
            quota_cached_input_credits=2, quota_output_credits=200, opt_in=True)
        async def transport(*args):
            return {"choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 100}}
        model = BudgetedModel(config, transport=transport)
        asyncio.run(model.generate([{"role": "user", "content": "hello"}]))
        self.assertEqual(model.ledger.snapshot()["accounted_quota_credits"], 120_000)
        self.assertEqual(model.ledger.snapshot()["calls"][0]["cache_accounting"], "unknown-assumed-uncached")
        async def bad_transport(*args):
            return {"choices": [{"message": {"content": "{}"}}],
                    "usage": {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1}}
        model = BudgetedModel(config, transport=bad_transport)
        with self.assertRaises(BudgetExceeded):
            asyncio.run(model.generate([{"role": "user", "content": "hello"}]))
        self.assertEqual(model.ledger.snapshot()["reserved_unknown_tokens"], 8320)
        self.assertEqual(model.ledger.snapshot()["accounted_quota_credits"], 844_800)

    def test_swallowed_transport_or_response_failure_blocks_the_next_stage(self):
        from evaluation.models import BudgetExceeded, BudgetedModel, ModelConfig
        config = ModelConfig("openai-compatible", "test-model", "https://example.invalid/v1", "EXPLICIT_TEST_KEY",
            max_input_tokens=8192, max_output_tokens=128, max_total_tokens=40_000, opt_in=True)
        for failure in ("transport", "response"):
            with self.subTest(failure=failure):
                calls = []
                original = OSError("Injected offline transport failure")
                async def transport(*args):
                    calls.append(args)
                    if failure == "transport":
                        raise original
                    return {"choices": [{"message": {"content": None}}],
                            "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
                model = BudgetedModel(config, transport=transport)
                async def swallowed_then_continue():
                    try:
                        await model.for_stage("synthesis").generate([{"role": "user", "content": "first"}])
                    except (OSError, ValueError) as exc:
                        if failure == "transport":
                            self.assertIs(exc, original)
                        # SDK helpers can suppress an error and try another stage.
                    else:
                        self.fail("The original execution failure must propagate")
                    with self.assertRaises(BudgetExceeded):
                        await model.for_stage("classification").generate([{"role": "user", "content": "next"}])
                asyncio.run(swallowed_then_continue())
                usage = model.ledger.snapshot()
                self.assertEqual(len(calls), 1)
                self.assertEqual(usage["request_count"], 1)
                self.assertTrue(usage["blocked_reason"])
                self.assertEqual(usage["calls"][0]["status"], "failed")
                self.assertEqual(usage["accounted_total_tokens"], 8320 if failure == "transport" else 110)

    def test_native_failed_known_usage_exceeding_reservation_is_accounted(self):
        from evaluation.models import BudgetExceeded, BudgetedModel, ModelConfig
        from evaluation.openclaw_transport import NativeOpenClawError
        config = ModelConfig("xiaomi-mimo", "mimo-v2.6-flash", "https://token-plan-ams.xiaomimimo.com/v1", "OPENCLAW_MANAGED_AUTH",
            max_input_tokens=65536, max_output_tokens=2048, max_total_tokens=2_000_000,
            max_quota_credits=250_000_000, quota_uncached_input_credits=100,
            quota_cached_input_credits=2, quota_output_credits=200, opt_in=True,
            execution_backend="native-openclaw")
        for prompt, output, cached in ((74961, 691, 70080), (76918, 653, 72384)):
            with self.subTest(prompt=prompt):
                original = NativeOpenClawError("native-configured-token-limit-exceeded", metadata={
                    "native_openclaw": True, "usage": {
                        "prompt_tokens": prompt, "completion_tokens": output, "total_tokens": prompt + output,
                        "prompt_tokens_details": {"cached_tokens": cached},
                        "completion_tokens_details": {"reasoning_tokens": 17}}})
                class Native:
                    native_openclaw = True
                    def __init__(self):
                        self.calls = 0
                    async def __call__(self, *args):
                        self.calls += 1
                        raise original
                native = Native()
                model = BudgetedModel(config, transport=native, transport_kind="native-openclaw")
                with self.assertRaises(NativeOpenClawError) as raised:
                    asyncio.run(model.generate([{"role": "user", "content": "offline failed call"}]))
                self.assertIs(raised.exception, original)
                usage = model.ledger.snapshot()
                self.assertEqual(usage["known_total_tokens"], prompt + output)
                self.assertEqual(usage["accounted_total_tokens"], prompt + output)
                self.assertEqual(usage["reserved_unknown_tokens"], 0)
                self.assertTrue(usage["provider_limit_violation"])
                self.assertEqual(usage["accounted_quota_credits"], (prompt - cached) * 100 + cached * 2 + output * 200)
                call = usage["calls"][0]
                self.assertEqual(call["status"], "failed")
                self.assertEqual(call["usage_status"], "actual")
                self.assertEqual(call["cached_input_tokens"], cached)
                self.assertEqual(call["reasoning_tokens"], 17)
                self.assertTrue(call["provider_limit_violation"])
                self.assertIsNone(usage["accounted_budget_usd"])
                with self.assertRaises(BudgetExceeded):
                    asyncio.run(model.for_stage("reflection").generate([{"role": "user", "content": "next"}]))
                self.assertEqual(native.calls, 1)

    def test_failed_usage_metadata_requires_native_transport_and_error_type(self):
        from evaluation.models import BudgetedModel, ModelConfig
        from evaluation.openclaw_transport import NativeOpenClawError
        config = ModelConfig("openai-compatible", "test-model", "https://example.invalid/v1", "EXPLICIT_TEST_KEY",
            max_input_tokens=8192, max_output_tokens=128, max_total_tokens=40_000,
            execution_backend="native-openclaw", opt_in=True)
        metadata = {"usage": {"prompt_tokens": 10, "completion_tokens": 1, "total_tokens": 11}}
        for kind in ("offline-native-error", "native-untrusted-error", "native-inconsistent-usage"):
            with self.subTest(kind=kind):
                if kind == "native-untrusted-error":
                    original = RuntimeError("Untrusted metadata")
                    original.metadata = metadata
                else:
                    original = NativeOpenClawError("offline-failure", metadata=metadata if kind != "native-inconsistent-usage" else {
                        "usage": {"prompt_tokens": 100, "completion_tokens": 10, "total_tokens": 1}})
                class Transport:
                    native_openclaw = True
                    async def __call__(self, *args):
                        raise original
                model = BudgetedModel(config, transport=Transport(), transport_kind=(
                    "offline-mock" if kind == "offline-native-error" else "native-openclaw"))
                with self.assertRaises(type(original)) as raised:
                    asyncio.run(model.generate([{"role": "user", "content": "offline failed call"}]))
                self.assertIs(raised.exception, original)
                usage = model.ledger.snapshot()
                self.assertEqual(usage["known_total_tokens"], 0)
                self.assertEqual(usage["reserved_unknown_tokens"], 8320)
                self.assertEqual(usage["accounted_total_tokens"], 8320)
                self.assertTrue(usage["blocked_reason"])

    def test_cancelled_transport_blocks_followup_and_keeps_unknown_reservation(self):
        from evaluation.models import BudgetExceeded, BudgetedModel, ModelConfig
        original = asyncio.CancelledError()
        calls = []
        async def transport(*args):
            calls.append(args)
            raise original
        config = ModelConfig("openai-compatible", "test-model", "https://example.invalid/v1", "EXPLICIT_TEST_KEY",
            max_input_tokens=8192, max_output_tokens=128, max_total_tokens=40_000, opt_in=True)
        model = BudgetedModel(config, transport=transport)
        async def exercise():
            with self.assertRaises(asyncio.CancelledError) as raised:
                await model.generate([{"role": "user", "content": "offline cancelled call"}])
            self.assertIs(raised.exception, original)
            with self.assertRaises(BudgetExceeded):
                await model.generate([{"role": "user", "content": "next"}])
        asyncio.run(exercise())
        self.assertEqual(len(calls), 1)
        usage = model.ledger.snapshot()
        self.assertEqual(usage["reserved_unknown_tokens"], 8320)
        self.assertEqual(usage["calls"][0]["status"], "failed")
        self.assertEqual(usage["calls"][0]["error_type"], "CancelledError")

    def test_token_plan_requires_native_auth_and_never_reads_an_env_secret(self):
        from evaluation.models import BudgetedModel, ModelConfig
        from dataclasses import replace
        config = ModelConfig("xiaomi-mimo", "mimo-v2.6-flash", "https://token-plan-ams.xiaomimimo.com/v1", "OPENCLAW_MANAGED_AUTH",
            max_input_tokens=8192, max_output_tokens=128, max_total_tokens=40_000,
            max_quota_credits=2_000_000, quota_uncached_input_credits=100,
            quota_cached_input_credits=2, quota_output_credits=200, opt_in=True,
            execution_backend="native-openclaw")
        with self.assertRaisesRegex(ValueError, "direct HTTP"):
            replace(config, execution_backend="direct-http").validate()
        with self.assertRaisesRegex(ValueError, "cannot fall back"):
            BudgetedModel(config)
        class Native:
            native_openclaw = True
            budget_contract = {"native_input_overhead_tokens": None, "max_provider_attempts": None}
            async def __call__(self, url, payload, headers, timeout):
                self.headers = headers
                return {"choices": [{"message": {"content": "{}"}}],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 10}}
        native = Native()
        import os
        original_get = os.environ.get
        def no_native_secret(name, default=None):
            if name == "OPENCLAW_MANAGED_AUTH":
                raise AssertionError("No native secret lookup")
            return original_get(name, default)
        with patch("evaluation.models.os.environ.get", side_effect=no_native_secret):
            model = BudgetedModel(config, transport=native, transport_kind="native-openclaw")
            asyncio.run(model.generate([{"role": "user", "content": "hello"}]))
        self.assertEqual(native.headers, {"Content-Type": "application/json"})
        self.assertEqual(model.ledger.snapshot()["calls"][0]["transport_kind"], "native-openclaw")

    def test_real_agent_uses_only_fake_observations_and_next_step_guidance(self):
        from evaluation.models import ModelReply
        from evaluation.real_agent import FakeWorldModelAgent
        task = next(e for e in pilot_sequences()[0].events if isinstance(e, Task))
        class Model:
            def __init__(self):
                self.requests = []
            async def generate(self, messages):
                self.requests.append(messages)
                answer = {"tool_calls": [{"name": task.tools[0].name, "arguments": task.tools[0].arguments}], "answer": None} if len(self.requests) == 1 else {"tool_calls": [], "answer": {"completed": False}}
                return ModelReply(json.dumps(answer), {})
        class Guidance:
            def __init__(self):
                self.observed = []
            def prompt(self, role, base_prompt):
                return base_prompt + f"\nGuidance version {len(self.observed)}"
            async def observe_step(self, **step):
                self.observed.append(step)
                return {"mechanical": True}
        model, guidance = Model(), Guidance()
        agent = FakeWorldModelAgent(model)
        response = asyncio.run(agent.bind(task)(task.public_request(), "thoroughness", guidance))
        self.assertEqual(response, {"completed": False})
        self.assertEqual(len(agent.last_runs[0]["tool_calls"]), 1)
        self.assertIsInstance(guidance.observed[0]["error"], RuntimeError)
        self.assertIn("Guidance version 1", model.requests[1][0]["content"])
        self.assertNotIn("required_fields", json.dumps(model.requests))
        with self.assertRaises(ValueError):
            asyncio.run(agent.bind(task)({**task.public_request(), "expected_response": {}}, "single", guidance))

    def test_hierarchical_roles_delegate_and_keep_per_invocation_limits(self):
        from evaluation.models import ModelReply
        from evaluation.real_agent import FakeWorldModelAgent
        task = next(e for e in pilot_sequences()[0].events if isinstance(e, Task))
        tool_call = {"tool_calls": [{"name": task.tools[0].name, "arguments": task.tools[0].arguments}], "answer": None}
        final = {"tool_calls": [], "answer": {"completed": False}}
        delegation = lambda role: {"delegations": [{"role": role, "instruction": "Inspect the simulated result."}], "answer": None}
        class Model:
            def __init__(self, responses):
                self.responses = iter(responses)
            async def generate(self, messages):
                return ModelReply(json.dumps(next(self.responses)), {})
        # Planner rolls each subordinate answer into its next observation.
        responses = [delegation("Web Search"), tool_call, final, delegation("Analyzer"), final,
                     delegation("Browser"), tool_call, final, final]
        agent = FakeWorldModelAgent(Model(responses), hierarchical=True)
        self.assertEqual(asyncio.run(agent.run_task(task)), {"completed": False})
        invocations = agent.last_runs[0]["role_invocations"]
        self.assertEqual([entry["role"] for entry in invocations], ["Planner", "Web Search", "Analyzer", "Browser"])
        self.assertEqual([entry["max_steps"] for entry in invocations], [20, 3, 3, 5])
        # A fresh delegation receives its own three-step allowance, even when
        # the earlier invocation of the same role exhausted its allowance.
        responses = [delegation("Web Search"), tool_call, tool_call, tool_call,
                     delegation("Web Search"), tool_call, tool_call, tool_call, final]
        agent = FakeWorldModelAgent(Model(responses), hierarchical=True)
        self.assertEqual(asyncio.run(agent.run_task(task)), {"completed": False})
        children = [entry for entry in agent.last_runs[0]["role_invocations"] if entry["role"] == "Web Search"]
        self.assertEqual([entry["steps"] for entry in children], [3, 3])
        self.assertEqual(len(agent.last_runs[0]["tool_calls"]), 6)


if __name__ == "__main__":
    unittest.main()
