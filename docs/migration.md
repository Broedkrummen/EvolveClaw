# OpenClaw 2 migration and verification

The original EvolveClaw snapshot is `a9c62516051c4fa6369b1c7b20c07c3371e1901d`.
The investigated and tested host is OpenClaw 2026.10.2, Node 26.11.1, Python 3.12.
[OpenClaw 2026.8.1](https://docs.openclaw.ai/releases/2026.8.1) is identified by the
official release history as OpenClaw 2.0. The exact historical update that broke
the user's previous installation cannot be established: no EvolveClaw installation
or historical error log was present in the inspected live roots.

## Reproduced causes

- Without `plugins.entries.evolveclaw.hooks.allowConversationAccess: true`, the
  original plugin loaded but only its two tool hooks registered. The learning
  and injection hooks were explicitly blocked by the host. The old installer
  never granted this access.
- Original hook fields did not match the installed host: assistant output was
  missed, tool names/inputs became `unknown`/`{}`, results were dropped, and a
  user request was sent as `current_system_prompt`.
- The installed default model is a string. The old integration only understood
  `agents.defaults.model.primary`, so it skipped automatic model configuration.
- One global trace buffer mixed overlapping runs. Holding completion A, starting
  B, and releasing A reproducibly erased B's trace.
- SCOPE 0.1.3 exposes no tactical reset method. The old endpoint returned success
  without changing its counters; twenty accepted rules could become a process
  lifetime learning limit.
- The old sidecar could label advice strategic without persisting it, discard
  custom OpenAI endpoints, and truncate away the current response after prepending
  conversation history.

These are concrete compatibility and lifecycle failures. They support the repair
without claiming that the 2.0 update alone caused every symptom.

## Preserved functionality and repair coverage

| Existing capability | Repaired behavior/proof |
| --- | --- |
| Native plugin registration | Compiled ESM entry, focused SDK imports, manifest activation; actual host inspection sees seven typed hooks and the sidecar service. |
| System/context injection | Both `append_system` and `prepend_context` retain additive fields; cached prompt injection never waits for remote I/O. |
| Error and successful-run learning | Current assistant/tool fields, real system prompt, error-only failures, bounded trace and recent conversation history. |
| Assistant-specific prompts and domains | Original `server/prompts.py` remains unchanged. |
| Tactical learning | Kept by session and run; overlapping sessions cannot mix buffers or advice. |
| Session reset/new session | Ended session cannot accept delayed advice; the pinned SDK's task counters and duplicate history actually reset. |
| Persistent strategic memory | Same disk format and main-agent namespace, confirmed promotion, restart loading, refresh after consolidation/pruning. |
| Guideline cap | Count individual strategic entries, prioritize them, then keep the newest tactical entries; zero tactical budget really keeps zero. |
| Background filtering | Heartbeat/memory/cron and subagent sessions remain excluded. |
| Model/provider configuration | Host model/auth helpers, object/string settings, compatible API credentials, explicit overrides, `.env` priority, endpoint forwarding and retry. |
| Automatic Python server | Asynchronous dependency setup in an isolated environment, managed-environment reuse, configured local port, owned-process cleanup. |
| Existing memory/config | Preserve explicit `.env` data paths, reuse legacy local memory, or use stable state storage; no slot replacement. |
| Separately managed server | Retained; plugin stops only a process it started. Incompatible old sidecars require a visible restart rather than silently retaining old defects. |
| Sidecar HTTP API and statistics | All six endpoints remain, with protocol marker, individual rule list and actual strategic counts added. |
| Failure isolation | Sidecar outage does not block prompt building or crash normal agent operation. |

The SDK compatibility adapter is intentionally pinned to `scope-optimizer==0.1.3`
because it accesses that release's task-counter internals. Updating SCOPE requires
reviewing or removing the adapter and rerunning its regression tests.

## Verification and limits

Type checking uses the public declarations from the exact host release. Node tests
drive current-shaped hooks against an actual HTTP test server, including concurrent
completions, old-response ordering, permission-independent filtering, injection
modes, configuration retry, OAuth handling and outages. The Python subprocess test
starts the actual sidecar on a temporary port and proves cleanup. Python tests use
the actual pinned SCOPE library with a mocked synthesis model to verify task limits,
reset, low-confidence fallback, consolidation, persistence/restart, HTTP routes and
OpenAI base URLs. All 55 upstream SCOPE tests also pass in the research environment.

`npm run verify:package` creates the release tarball, rejects credentials/venvs/memory
in its payload, installs it through `npm-pack:` into isolated OpenClaw state, and
inspects the runtime. With required grants it registers seven hooks plus
`evolveclaw-sidecar`; without conversation access it retains three metadata/tool
hooks and reports the host's four blocked conversation hooks. Inspection does not
start the Python service, send a paid model request, or validate a live Gateway.

The host's `plugins validate` command is scoped to static tool/feature authoring
metadata. It rejects a hook/service-only entry as lacking that metadata; even
provider scaffolds do not use that command. Adding an unrelated tool would expand
the plugin solely to satisfy a differently scoped validator. See
[official authoring documentation](https://docs.openclaw.ai/cli/plugins/authoring).

No live plugin activation, normal Gateway restart, real provider call or measured
quality benchmark was performed. The project includes a repeatable CI workflow;
local passing checks do not imply that hosted CI has already run successfully.

Future research mechanisms and efficacy evaluation are described separately in
[the paper/repository assessment](research-assessment.md).
