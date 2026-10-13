# EvolveClaw

An OpenClaw plugin that learns guidelines from completed agent runs using
[SCOPE](https://github.com/JarvisPei/SCOPE). Tactical guidance stays with its
session; reusable strategic guidance persists on disk. The next turn receives
the learned guidance through an additive prompt hook.

Version 0.3.0 repairs compatibility with **OpenClaw 2026.10.2** and preserves
the existing learning pipeline, assistant-specific prompts/domains, both
injection modes, model configuration, automatic sidecar setup, and statistics.
It does not implement the paper's parallel perspectives or Best-of-N synthesis.
Those are separate future features.

The plugin already existed before this change. Its older integration could
appear loaded while conversation hooks were blocked, collect obsolete event
fields, mix concurrent sessions, or eventually stop accepting guidelines.
See [the investigation and research assessment](docs/research-assessment.md)
and [migration details](docs/migration.md).

## Scoped learning and controls (0.3)

Learning stays automatic. Each rule records its evidence, scope, stable ID, and
change history. SQLite transactions prevent a delayed consolidation from
overwriting a newer accepted change. Opposite instructions remain distinct.

The host supplies the memory audience and project identities. Everyday tasks
without a repository use a separate no-project bucket inside their audience.
Missing audience context produces no learning or injected advice. Older JSON
rules are preserved as inactive legacy history until an owner assigns a scope.
Project-spanning promotion requires independently validated evidence in at least
two projects within the same audience; an agent claiming success is not validation.

Chat controls:

- `/evolveclaw list`, `history`, `detail RULE_ID`, `usage`, `status`, `scopes`, or `legacy`.
- `/evolveclaw-change pause`, `resume`, `disable RULE_ID`, `restore RULE_ID`,
  `undo CHANGE_ID`, `assign RULE_ID`, or `promote RULE_ID`.

Commands use the last recorded scope for the conversation and require the host's
owner/operator authorization. Pause stops new learning and leaves active rules
available. Disable changes a rule's eligibility. Undo targets a specific recorded
change; it does not reverse external actions.

The native **EvolveClaw** dashboard shows recorded scope/status filters, rules,
supporting observations, history/undo, and measured/estimated/unknown usage. It
uses the same backend operations as chat. Enable OpenClaw's **Settings → Labs →
Custom plugin UI** when installing the reviewed plugin, and open the authenticated
Control UI on the same Gateway origin over HTTPS or trusted loopback. Backend
and chat controls remain available with that lab off. Recorded labels are for
management; they do not confer current learning authority.

The sidecar defaults to loopback and rejects direct browser-origin requests. For
a separately managed remote server, require `EVOLVECLAW_SIDECAR_TOKEN` and the
matching sensitive plugin setting `sidecarToken`; use a protected HTTPS endpoint.
The plugin starts and stops only its own locally managed Python process.

`maxPromptChars` bounds added guidance (default 12,000 characters). Synthesis,
classification, and consolidation usage are recorded separately. Dollar costs
remain unknown until explicit prices are configured. See [migration details](docs/migration.md).

## Experimental evaluation runners

The repository includes an isolated simulated environment, an unmodified
SCOPE 0.1.3 reference, and an experimental implementation of the paper's
parallel-perspective/candidate-selection architecture. See
[evaluation documentation](evaluation/README.md),
[paper fidelity and limits](docs/scope-paper-implementation.md), and
[evaluation readiness](docs/evaluation-readiness.md).

Offline tests verify mechanics. Actual quality comparisons require an explicit
model and a dollar or token budget; subscription experiments also account for
weighted plan credits. The authored pilot has 20 sequences, and the development
split has 100 sequences in 20 families with five clustered variants per family.
The 500 held-out slots still need separate authoring and review. The
[MiMo pilot protocol](docs/mimo-pilot-protocol.md) records live attempts, protocol changes and usage. The [pilot results](docs/mimo-first-pilot-results.md) preserve completed scores and limitations. Operational pilots and scripted results do not establish improved task reliability.

## Requirements

- OpenClaw 2026.10.2. This is the host version used for build and runtime tests;
  newer experimental SDK versions need their own compatibility verification.
- Node 24.16+ on the Node 24 line, or Node 26.1+.
- Python 3.10+ with `venv` and `pip`; Python 3.12 was tested. On Debian/Ubuntu,
  a Python installation without `ensurepip` needs its matching `python3-venv`
  package before automatic setup can work. An existing configured Python
  environment can instead be selected through `pythonPath`.
- An API credential supported by the SCOPE synthesis adapter. OpenClaw OAuth
  sign-in alone is not a transferable API key for this Python sidecar.

## Install the reviewed source

Use this checkout or a release containing 0.3.0. An existing npm/ClawHub listing
may still contain the old implementation until a maintainer publishes the update.

```bash
npm ci --ignore-scripts
npm run build
openclaw plugins install --link "$PWD" --force --accept-capabilities
openclaw config set plugins.entries.evolveclaw.hooks.allowConversationAccess true
openclaw config set plugins.entries.evolveclaw.hooks.allowPromptInjection true
openclaw plugins enable evolveclaw
openclaw plugins inspect evolveclaw --runtime --json
```

`./scripts/install-plugin.sh` performs these steps. It explicitly grants
conversation access because learning needs the prompt, assistant response, and
execution trace. The grant is host policy under `hooks`, not a plugin `config`
setting. If `plugins.allow` is configured, EvolveClaw must be included; the
native installer updates that allowlist.

OpenClaw applies plugin lifecycle changes to a running local Gateway. Use
`openclaw plugins reload evolveclaw` after editing source. A CLI inspection proves
registration in that inspecting process; verify a real conversation and its
sidecar effect to establish that the running Gateway loaded the change.

## Install a built package

```bash
npm pack --pack-destination /tmp
openclaw plugins install npm-pack:/tmp/evolveclaw-0.3.0.tgz --force --accept-capabilities
```

Then apply the same conversation/prompt grants and enablement above. The package
contains compiled JavaScript, the manifest, Python sidecar, custom prompts,
setup scripts, and documentation. Credentials, local virtual environments,
and learned memory are excluded. `--force` acknowledges an arbitrary reviewed
install source; it does not grant conversation access or privileged plugin trust.
`--accept-capabilities` records consent for the reviewed plugin's declared runtime
capabilities. Conversation and prompt grants remain explicit separate settings.

## Upgrade an existing installation

Back up the existing strategic memory and server `.env` before replacing an old
install directory. Keep the existing `agentName` to retain its strategic namespace.
If a package replacement changes the server directory, set `dataPath` to the
existing absolute SCOPE data directory or move the backed-up data into stable
OpenClaw state storage before starting the new sidecar.

The repaired sidecar reports **version 0.5.0, protocol_version 3** at `/health`.
The original detached server reports 0.3.0 without this protocol marker. Stop
that old process with its existing process manager and start the updated server.
The plugin identifies an incompatible server and logs a specific restart message;
it does not terminate a server it did not start.

Existing `server/.env` data-directory settings remain effective. Without an
explicit data directory, an existing `server/scope_data` is reused; otherwise
new memory goes under OpenClaw's stable service state directory. Version 0.3 imports existing strategic JSON once into scoped SQLite history.
Unscoped legacy rules remain inactive until an owner assigns their scope. The
original JSON remains available for backup; scoped exports preserve its format.
Tactical state remains task-specific.

## Configuration

```json5
{
  plugins: {
    allow: ["evolveclaw"], // Include your other existing allowed plugins too.
    entries: {
      evolveclaw: {
        enabled: true,
        hooks: { allowConversationAccess: true, allowPromptInjection: true },
        config: {
          serverUrl: "http://127.0.0.1:5757",
          agentName: "openclaw-agent",
          enabled: true,
          injectMode: "append_system",
          maxGuidelines: 30,
          autoStartServer: true,
        },
      },
    },
  },
}
```

| Setting | Default | Behavior |
| --- | --- | --- |
| `serverUrl` | `http://127.0.0.1:5757` | Sidecar endpoint; automatic process startup supports local HTTP URLs. |
| `agentName` | `openclaw-agent` | Persistent namespace for the main OpenClaw agent. Other agent IDs receive distinct namespaces. |
| `enabled` | `true` | Enable learning and injection within the installed plugin. |
| `injectMode` | `append_system` | Append cacheable system context, or use `prepend_context` for per-turn user context. |
| `maxGuidelines` | `30` | Limit injected individual guidelines, range 5–200; strategic guidance takes precedence, then the newest tactical advice. |
| `scopeModel` | OpenClaw default | Optional synthesis-model override. |
| `scopeProvider` | Detected | Optional `anthropic`, `openai`, or `litellm` adapter. |
| `scopeApiKey` | Resolved by OpenClaw | Optional synthesis API key; marked sensitive in config UI. |
| `scopeBaseUrl` | OpenClaw provider URL | Optional API endpoint override, including OpenAI-compatible endpoints. |
| `autoStartServer` | `true` | Start a local sidecar as a plugin-owned service if none is running. |
| `pythonPath` | Detected | Python executable/environment override. Dependencies are checked against pinned SCOPE 0.1.3. |
| `dataPath` | Existing or stable state path | Optional absolute path to SCOPE data. |

Server `.env` credentials take precedence over forwarded configuration, as before.
The plugin supports both object and string OpenClaw default-model settings,
uses the host's model/auth helpers, and retries configuration after an outage or
sidecar restart. Existing configured sidecars receive updated overrides when the
plugin service starts. OAuth and ambient AWS auth need separate compatible SCOPE
credentials; they are not forwarded as ordinary API keys.

See [server/.env.template](server/.env.template) for synthesis frequency,
confidence thresholds, memory limits, and provider environment settings. The
defaults remain efficiency mode, quality analysis every third successful step,
medium acceptance, 0.85 strategic promotion, twenty guidelines per task, and ten
strategic rules per domain. The SCOPE dependency is pinned to 0.1.3 because the
task-lifecycle adapter deliberately contains that version's private-counter defect.

## Operation

1. `before_prompt_build` injects cached strategic and session-local tactical
   guidance immediately, and refreshes memory in the background.
2. `llm_input` captures the actual assembled system prompt. `llm_output` captures
   `assistantTexts`; tool hooks capture `toolName`, `params`, structured results,
   and errors using current OpenClaw payloads.
3. `agent_end` sends a bounded trace and recent conversation history to SCOPE.
   Errors and successful runs retain the existing reflection/quality paths.
4. Accepted temporary advice is retained in its originating session. Successful
   strategic promotion reloads authoritative persisted memory after any merging
   or pruning. Older HTTP responses cannot replace a newer memory snapshot.
5. `session_end` clears that session's tactical state and resets the corresponding
   SDK counters. Strategic memory remains available across sessions and restarts.

Heartbeats, memory/cron triggers, and subagent sessions remain excluded. Sessions
and runs have separate state, so simultaneous conversations cannot mix traces or
clear each other's buffers. A new session begins without another session's tactical
guidance. Remote outages fail open; prompt building does not await remote requests.
Learned advice remains subordinate to current system and user instructions.

The plugin claims neither the memory slot nor the context-engine slot and can
coexist with other prompt/memory plugins. The service stops only its own Python
child on shutdown/reload. External servers remain externally managed.

## Run a separate sidecar

```bash
./scripts/start-server.sh
```

This creates a local Python environment, installs the pinned dependency, and starts
the same HTTP API. A `.env` is optional: the server can wait for model configuration
from OpenClaw. Set `autoStartServer: false` when a process manager owns the server.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Availability, configuration status, server/protocol version. |
| `POST /configure` | Synthesis provider/model/key/URL; explicit server credentials retain priority. |
| `POST /step` | Completed-run analysis; accepted guideline and memory type. |
| `GET /rules/{agent_name}` | Formatted strategic memory, individual guidelines, and actual rule count. |
| `POST /reset` | Reset one task's tactical counters/history, or all tactical tasks for an agent. |
| `GET /stats/{agent_name}` | Step/guideline counts, strategic count, synthesis rate, uptime. |

## Development and verification

```bash
npm ci --ignore-scripts
npm run typecheck
npm test
python3 -m venv server/venv
server/venv/bin/python -m pip install -r server/requirements-dev.txt
server/venv/bin/python -m pytest -q
EVOLVECLAW_TEST_PYTHON="$PWD/server/venv/bin/python" npm test
npm run verify:package
```

The Python tests use the real pinned SCOPE library with mocked synthesis, not paid
provider calls. The subprocess test starts/stops the actual sidecar on a temporary
port. Package verification installs the tarball into isolated OpenClaw state,
inspects seven hooks plus the service, and checks denied conversation access.
It neither edits the normal OpenClaw configuration nor contacts its Gateway.
GitHub Actions runs the same compatibility checks.

`openclaw plugins validate` currently validates tool/feature authoring metadata;
it does not validate this hook/service plugin. Runtime inspection and the managed
package test are the applicable host proofs. See [OpenClaw authoring docs](https://docs.openclaw.ai/cli/plugins/authoring).

Mechanical verification is not a measurement of improved answer quality. The
[research assessment](docs/research-assessment.md) explains the paper's Pass@2
results, missing research mechanisms, cost overhead, reproducibility limitations,
and a proposed future evaluation on representative OpenClaw tasks.

## Citation and license

SCOPE: Prompt Evolution for Enhancing Agent Effectiveness, Zehua Pei et al.
[arXiv:2512.15374v2](https://arxiv.org/abs/2512.15374v2), revised 28 May 2026.
EvolveClaw and SCOPE are MIT-licensed; see [LICENSE](LICENSE) and the upstream
[SCOPE repository](https://github.com/JarvisPei/SCOPE).
