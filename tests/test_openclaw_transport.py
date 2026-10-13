"""Native CLI boundary tests use an offline executable, never an LLM service."""
import asyncio
from copy import deepcopy
import json
import shutil
import subprocess
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation.openclaw_transport import (
    NativeBudgetUnsupported, NativeOpenClawError, NativeOpenClawTransport, NativeOpenClawPool,
    build_native_config, convert_native_usage, prepare_native_workspace,
)


def envelope(**changes):
    value = {"ok": True, "status": "ok", "final": '{"answer":{"completed":false}}',
             "provider": "xiaomi-token-plan", "model": "mimo-v2.6-flash", "assistantTurns": 1,
             "usage": {"input": 90, "output": 20, "cacheRead": 30, "cacheWrite": 0,
                       "reasoningTokens": 5, "total": 140, "cost": {"total": 0}}}
    value.update(changes)
    return value


class NativeTransportTests(unittest.TestCase):
    def setup_cli(self, directory, reply=None, *, stderr="", exit_code=0, raw_stdout=None):
        paths = prepare_native_workspace(directory / "native", max_input_tokens=131072,
                                         max_output_tokens=256)
        cli = directory / "offline-openclaw"
        log = directory / "requests.json"
        # JSON literals become Python string literals via repr, preventing
        # shell expansion or quoting surprises. Nothing contains a real key.
        source = ("#!/usr/bin/env python3\nimport json,sys\nfrom pathlib import Path\n"
            + f"Path({str(log)!r}).write_text(json.dumps({{'argv':sys.argv[1:],'stdin':sys.stdin.read()}}))\n"
            + f"sys.stderr.write({stderr!r})\n"
            + f"sys.stdout.write({(raw_stdout if raw_stdout is not None else json.dumps(reply or envelope()))!r})\n"
            + f"sys.exit({exit_code})\n")
        cli.write_text(source)
        cli.chmod(0o700)
        transport = NativeOpenClawTransport(cli, paths["config_path"], paths["workspace_path"],
            model="mimo-v2.6-flash", max_input_tokens=131072, max_output_tokens=256)
        return transport, log, paths

    def request(self, transport, **changes):
        payload = {"model": "mimo-v2.6-flash", "max_completion_tokens": 256, "temperature": .3,
            "messages": [{"role": "system", "content": "Coding-evaluation role guidance"},
                         {"role": "user", "content": "Observed fake-tool context"},
                         {"role": "assistant", "content": "Prior simulated reply"}]}
        payload.update(changes)
        return asyncio.run(transport(transport.base_url + "/chat/completions", payload,
                                    {"Authorization": "unused-test-placeholder"}, 10))

    def test_native_stdin_roles_and_usage_with_absent_zero_tool_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport, log, paths = self.setup_cli(Path(tmp))
            result = self.request(transport)
            observed = json.loads(log.read_text())
            self.assertEqual(observed["argv"][:2], ["agent", "exec"])
            self.assertIn("--json", observed["argv"])
            self.assertNotIn("--state-dir", observed["argv"])
            self.assertNotIn("--auth-env-only", observed["argv"])
            self.assertNotIn("--fallback", observed["argv"])
            self.assertNotIn("unused-test-placeholder", json.dumps(observed))
            serialized = json.loads(observed["stdin"].split("Serialized model request:\n", 1)[1])
            self.assertEqual([message["role"] for message in serialized["messages"]], ["system", "user", "assistant"])
            self.assertNotIn("Coding-evaluation role guidance", observed["argv"])
            self.assertEqual(result["usage"], {"prompt_tokens": 120, "completion_tokens": 20,
                "total_tokens": 140, "prompt_tokens_details": {"cached_tokens": 30},
                "completion_tokens_details": {"reasoning_tokens": 5}})
            self.assertNotIn("costUsd", result)
            self.assertIsNone(result["native_openclaw"]["reported_tool_calls"])
            self.assertEqual(result["native_openclaw"]["tool_denial_source"], "validated-config")
            self.assertFalse(transport.budget_contract["supports_strict_reservation"])
            self.assertIsNone(transport.budget_contract["native_input_overhead_tokens"])
            self.assertEqual(list(paths["workspace_path"].iterdir()), [paths["workspace_path"] / ".openclaw"])

    def test_usage_unknown_and_inconsistent_buckets_are_not_fabricated(self):
        self.assertEqual(convert_native_usage(None), {})
        self.assertEqual(convert_native_usage({"input": 90, "output": 20}), {"completion_tokens": 20})
        conservative = convert_native_usage({"input": 90, "output": 20, "total": 140})
        self.assertEqual(conservative["prompt_tokens"], 120)
        self.assertNotIn("prompt_tokens_details", conservative)
        for usage in ({"input": 90, "output": 20, "cacheRead": 30, "total": 110},
                      {"input": 90, "output": 20, "cacheRead": 0, "reasoningTokens": 25},
                      {"input": True, "output": 20}, {"input": 90, "output": 20, "cacheRead": -1}):
            with self.assertRaises(NativeOpenClawError):
                convert_native_usage(usage)
        self.assertTrue(convert_native_usage({"input": 90, "output": 20, "cacheWrite": 1})["native_unsupported_cache_write"])

    def test_identity_turns_and_positive_tools_fail_closed(self):
        for changes, kind in (({"provider": "other-provider"}, "identity"),
                              ({"model": "other-model"}, "identity"),
                              ({"assistantTurns": 2}, "turn-count"),
                              ({"assistantTurns": True}, "turn-count"),
                              ({"toolSummary": {"calls": 1}}, "tool-denial")):
            with self.subTest(changes=changes), tempfile.TemporaryDirectory() as tmp:
                transport, _, _ = self.setup_cli(Path(tmp), envelope(**changes))
                with self.assertRaisesRegex(NativeOpenClawError, kind):
                    self.request(transport)

    def test_failures_never_expose_native_stderr_or_error_messages(self):
        sentinel = "FAKE_PRIVATE_DIAGNOSTIC_DO_NOT_EXPOSE"
        for raw in (None, sentinel):
            with tempfile.TemporaryDirectory() as tmp:
                transport, _, _ = self.setup_cli(Path(tmp), envelope(ok=False, status="error", error={"message": sentinel}),
                    stderr=sentinel, exit_code=1, raw_stdout=raw)
                with self.assertRaises(NativeOpenClawError) as caught:
                    self.request(transport)
                self.assertNotIn(sentinel, str(caught.exception))
                self.assertNotIn(sentinel, json.dumps(caught.exception.metadata))
                self.assertNotIn(sentinel, json.dumps(transport.events))

    def test_config_and_payload_admission_reject_before_cli_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport, log, paths = self.setup_cli(Path(tmp))
            for changes in ({"model": "wrong"}, {"max_completion_tokens": 257}, {"max_tokens": 257}, {"temperature": .8}):
                with self.assertRaises(ValueError):
                    self.request(transport, **changes)
                self.assertFalse(log.exists())
            changed = json.loads(paths["config_path"].read_text())
            changed["tools"]["deny"] = []
            paths["config_path"].write_text(json.dumps(changed))
            with self.assertRaises(ValueError):
                self.request(transport)
            self.assertFalse(log.exists())
            with self.assertRaises(ValueError):
                NativeOpenClawTransport(transport.cli_path, paths["config_path"], paths["workspace_path"],
                    model="mimo-v2.6-flash", max_output_tokens=256)

    def test_strict_native_budget_guarantee_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport, log, paths = self.setup_cli(Path(tmp))
            with self.assertRaises(NativeBudgetUnsupported):
                NativeOpenClawTransport(transport.cli_path, paths["config_path"], paths["workspace_path"],
                    model="mimo-v2.6-flash", max_output_tokens=256, require_strict_budget=True)
            self.assertFalse(log.exists())

    def test_secret_free_config_matches_v2_schema_locations(self):
        config = build_native_config()
        defaults = config["agents"]["defaults"]
        self.assertNotIn("agentRuntime", defaults)
        self.assertNotIn("contextTokens", defaults)
        self.assertNotIn("memorySearch", defaults)
        model_entry = defaults["models"]["xiaomi-token-plan/mimo-v2.6-flash"]
        self.assertEqual(model_entry["agentRuntime"], {"id": "openclaw"})
        self.assertEqual(config["tools"]["deny"], ["*"])
        self.assertEqual(config["plugins"]["allow"], ["xiaomi"])
        self.assertEqual(defaults["model"]["fallbacks"], [])
        self.assertEqual(model_entry["params"]["extraBody"]["max_completion_tokens"], 1024)
        self.assertNotIn("apiKey", json.dumps(config))

    def test_warm_worker_serializes_requests_reuses_process_and_closes(self):
        async def exercise(transport, log):
            payload = {"model": "mimo-v2.6-flash", "max_completion_tokens": 256, "temperature": .3,
                       "messages": [{"role": "user", "content": "Coding smoke test"}]}
            async with transport:
                replies = await asyncio.gather(*(transport(transport.base_url + "/chat/completions", payload, {}, 10) for _ in range(2)))
                self.assertEqual(len(replies), 2)
                self.assertTrue(all(reply["native_openclaw"]["worker"]["persistent_worker"] for reply in replies))
                rows = [json.loads(line) for line in log.read_text().splitlines()]
                self.assertEqual([row["id"] for row in rows], [1, 2])
                self.assertEqual(len({row["pid"] for row in rows}), 1)
                self.assertTrue(all("Serialized model request" in row["prompt"] for row in rows))
            self.assertIsNone(transport._worker)
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            transport, _, paths = self.setup_cli(directory)
            log = directory / "warm-requests.jsonl"
            node = directory / "offline-node"
            source = ("#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\n"
                + "metadata={'openclaw_version':'2026.10.2','entry_source_sha256':'a638bf91efbd775ab4b2d66fd0d6e124074b6edcbad8f85a487e07dab25b8504','persistent_worker':True,'internal_entry':True,'model_requests_serialized':True}\n"
                + "print(json.dumps({'ready':True,'metadata':metadata}),flush=True)\n"
                + "for line in sys.stdin:\n request=json.loads(line)\n"
                + " if request['op']=='close':\n  print(json.dumps({'id':request['id'],'closed':True}),flush=True)\n  break\n"
                + f" with Path({str(log)!r}).open('a') as output: output.write(json.dumps({{'id':request['id'],'pid':os.getpid(),'prompt':request['prompt']}})+'\\n')\n"
                + f" print(json.dumps({{'id':request['id'],'exitCode':0,'metadata':metadata,'envelope':{envelope()!r}}}),flush=True)\n")
            node.write_text(source)
            node.chmod(0o700)
            warm = NativeOpenClawTransport(transport.cli_path, paths["config_path"], paths["workspace_path"],
                model="mimo-v2.6-flash", max_output_tokens=256, warm_worker=True, node_path=node)
            asyncio.run(exercise(warm, log))

    def test_real_worker_rejects_wrong_host_version_before_import_or_request(self):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node is unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / "package.json").write_text(json.dumps({"name": "openclaw", "version": "wrong"}))
            cli = directory / "openclaw.mjs"
            cli.write_text("throw new Error('MUST_NOT_EXECUTE');")
            worker = Path(__file__).resolve().parents[1] / "scripts/openclaw-evaluation-worker.mjs"
            result = subprocess.run([node, str(worker), str(cli)], input=b"", capture_output=True, timeout=10)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["error_kind"], "native-worker-version-or-source-admission")
            self.assertNotIn("MUST_NOT_EXECUTE", result.stdout.decode())

    def test_pool_overlaps_independent_workers_preserves_identity_and_shared_limits(self):
        active, maximum, created = 0, 0, []
        class OfflineWorker:
            def __init__(self, *args, **kwargs):
                self.index, self.calls, self.closed, self.busy = len(created), [], False, False
                self.budget_contract = {"supports_strict_reservation": False}
                created.append(self)
            async def __call__(self, url, payload, headers, timeout):
                nonlocal active, maximum
                if self.busy:
                    raise AssertionError("Pool overlapped one native worker")
                self.busy = True
                active += 1
                maximum = max(maximum, active)
                self.calls.append(deepcopy(payload))
                try:
                    await asyncio.sleep(.02)
                    return {"choices": [{"message": {"content": "{}"}}],
                            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
                            "native_openclaw": {"model": payload["model"], "usage": {"prompt_tokens": 10, "completion_tokens": 5}, "status": "completed"}}
                finally:
                    active -= 1
                    self.busy = False
            async def close(self):
                self.closed = True
        async def exercise():
            with patch("evaluation.openclaw_transport.NativeOpenClawTransport", OfflineWorker):
                pool = NativeOpenClawPool("cli", "config", "workspace", model="mimo-v2.6-flash", workers=3)
            async with pool:
                results = await asyncio.gather(*(pool("endpoint", {"model": "mimo-v2.6-flash", "task": i}, {}, 10) for i in range(6)))
                self.assertEqual(len(results), 6)
                self.assertEqual(maximum, 3)
                self.assertEqual([len(worker.calls) for worker in created], [2, 2, 2])
                self.assertEqual({reply["native_openclaw"]["pool_worker_index"] for reply in results}, {0, 1, 2})
                self.assertTrue(all(reply["native_openclaw"]["model"] == "mimo-v2.6-flash" for reply in results))
                self.assertEqual(sum(reply["usage"]["prompt_tokens"] for reply in results), 60)
                self.assertEqual(pool.budget_contract["maximum_concurrent_native_requests"], 3)
                self.assertFalse(pool.budget_contract["supports_strict_reservation"])
            self.assertTrue(all(worker.closed for worker in created))
            with self.assertRaisesRegex(NativeOpenClawError, "pool-closed"):
                await pool("endpoint", {}, {}, 10)
        asyncio.run(exercise())

    def test_pool_close_cancels_and_joins_issued_and_queued_requests(self):
        created = []
        class OfflineWorker:
            def __init__(self, *args, **kwargs):
                self.budget_contract, self.closed, self.started = {}, False, asyncio.Event()
                created.append(self)
            async def __call__(self, *args):
                self.started.set()
                await asyncio.Event().wait()
            async def close(self):
                self.closed = True
        async def exercise():
            with patch("evaluation.openclaw_transport.NativeOpenClawTransport", OfflineWorker):
                pool = NativeOpenClawPool("cli", "config", "workspace", model="mimo-v2.6-flash", workers=1)
            issued = asyncio.create_task(pool("endpoint", {}, {}, 10))
            queued = asyncio.create_task(pool("endpoint", {}, {}, 10))
            await created[0].started.wait()
            await pool.close()
            self.assertTrue(issued.cancelled())
            self.assertTrue(queued.cancelled())
            self.assertTrue(created[0].closed)
            await pool.close()
        asyncio.run(exercise())
        for count in (0, 5, True, 1.5):
            with self.assertRaises(ValueError):
                NativeOpenClawPool("cli", "config", "workspace", model="mimo-v2.6-flash", workers=count)


if __name__ == "__main__":
    unittest.main()
