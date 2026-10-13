# Simulation evaluation scaffold

This runs fake everyday tasks locally, with independent scoring and isolated
memory for each condition and sequence. It makes no network or model calls and
touches no real calendar, inbox, document, account, or OpenClaw installation.

**Offline results establish mechanics only.** The assistant and learning
strategies are deterministic surrogates. The condition names `learning-off`,
`repaired-v0.2`, and `improved` describe the planned comparison; the pilot does
not execute those actual AI versions. Its scripted differences cannot establish
that the improved plugin makes fewer mistakes.

## Run

From the repository root, using Python 3.10 or later:

```sh
python3 -m evaluation pilot --output artifacts/evaluation/pilot-001
python3 -m evaluation storage-smoke --output artifacts/evaluation/storage-001
python3 -m evaluation scope-reference-smoke --output artifacts/evaluation/sdk-reference-001
python3 -m unittest discover -s tests -p test_evaluation.py -v
```

Use a new output directory each time. Existing directories are never overwritten.
The pilot uses only the standard library. The storage smoke imports the actual
production `server/memory_store.py`, creates isolated SQLite data, and calls no
synthesis or classification model. It checks evidence links, user/project
isolation, scoped management, outcome provenance, revision rejection, and
persistent history undo. This is actual storage integration, still mechanical
evidence rather than AI efficacy evidence.

The SDK smoke additionally requires `scope-optimizer==0.1.3` from the existing
server requirements. It instantiates **the actual upstream `SCOPEOptimizer`
class**, supplying only the required model and isolated experiment directory.
All optional settings, default reflection/classification/optimization prompts,
allowed domains, thresholds, and SDK algorithms remain unchanged. The model's
responses are injected offline; upstream synthesis, classification, acceptance,
and persistent strategic storage execute normally. The report records exact
SDK version, source/prompt hashes, configuration, and known limitations.

The extra condition `scope_sdk_reference` is used only by this actual SDK adapter;
it is never a fourth scripted strategy in the offline surrogate pilot. This is a
released SDK reference, **not full-paper replication** or a task-quality result.
In particular, the defaults disable Best-of-N and expose no public task-counter
or tactical reset API. The reference reports reset as unsupported and preserves
these limitations rather than repairing the baseline.

## Authored cases and reserved authoring slots

The pilot contains 20 sequences: two variations of each of ten families. Families
cover failed calendar, email, document, data import, and booking operations;
changed prices and research sources; user preferences and project formatting;
and undo of a deliberately wrong learned preference. Each sequence contains an
initial learning opportunity followed by two fresh probes. A simulated user gives
ordinary corrections; source updates and scope changes are controlled.

The generated manifest also reserves 100 development and 500 held-out sequences,
with distinct family/cluster identifiers across splits. These rows are marked
`fixture_status: planned`, have no executable fixtures, and contribute no results.
They must be independently authored and reviewed before use. Unique IDs do not
make examples statistically independent. Cases with shared histories, solution
structures, paraphrases, or templates must share appropriate cluster IDs, and
cluster assignments may need to be coarser than the pilot's family labels.

To export the authoring manifest separately:

```sh
python3 -m evaluation manifest --output artifacts/evaluation/authoring-manifest.json
```

Author new `Sequence` fixtures with matching `Task` objects and separately held
`ScoringKey` objects. Keep held-out task families and their history templates out
of development. The current command intentionally executes only authored pilot
fixtures; reserved rows cannot masquerade as 500 evaluated cases.

## Boundaries and scoring

`Task.public_request()` contains the instruction, trusted simulated scope, topic,
and advertised fake tool calls. Tool results are returned by `FakeWorld.call()`;
unknown tools or unexpected arguments are rejected. An assistant can observe
normal tool results and user feedback, but receives no evaluator answer keys,
metric tags, success labels, or private expected responses.

Each sequence and condition gets a separate `memory/memory.json`. No lessons are
shared between conditions or sequence runs. Sequential learning within each
sequence is supported; cross-sequence transfer is not yet implemented. A later
frozen-memory transfer experiment must explicitly define shared training cohorts
and separate them from held-out evaluation.

Each future task starts with a fresh assistant request rather than the learning
conversation in its prompt. In the eventual real integration, preserve the
authorized memory audience/project while resetting ordinary task context, and
report that boundary. Otherwise an assistant could simply read the earlier user
correction from its chat history, confounding persistent-memory benefit. A
conversation-scoped audience may legitimately change across fresh sessions; the
harness must model this explicitly instead of bypassing OpenClaw's grant rules.

The independent scorer checks structured response fields exactly, including type
(a numeric zero cannot substitute for a boolean false). Metrics include future
task success, repeated mistakes after a correction in the same scope, stale
advice, scope leakage, and recurrence after rollback. Categories are reported
separately. Rollback undoes memory only; fake-world actions are never replayed.

The primary descriptive comparison pairs improved and repaired surrogates on
identical sequence/task IDs. It averages differences within family clusters, gives
each family equal weight, and resamples whole clusters for an illustrative 95%
interval. It rejects missing pairs, duplicate results, and mismatched tasks.
**Neither the interval nor the scripted mean is evidence about AI efficacy.**
The ten pilot family labels also do not establish statistical independence.

`summary.json` and `sequence_results.json` are scored reports. Each sequence's
`public_requests.json` contains learner-visible requests, while `scored_trace.json`
contains both observations and private scoring. `scorer-only/scoring_keys.json`
is private to the evaluator. For an eventual real-model adapter, keep the scorer
directory, scored traces, scenario source code, and this report out of the agent's
filesystem/tool sandbox. A Python object boundary alone provides no access control.

## Real-model execution: explicit opt-in, fake tools only

The runnable comparison entry point is `python3 -m evaluation.run_models`.
Omitting `--execute` writes a plan without reading a credential or making a call.
Use `--help` for its required provider, model, endpoint, key-variable name, prices,
and cap. The [evaluation readiness guide](../docs/evaluation-readiness.md) explains
the actual application/SDK/paper conditions and current limitations. This compares
learning implementations in the fake-tool agent; it does not execute OpenClaw's
native Gateway hook integration or reproduce the original paper's task set.

`models.py` supplies runnable OpenAI-compatible text and Anthropic text adapters;
`real_agent.py` supplies a bounded model loop over `FakeWorld`. Credentials are
read only from the explicitly named environment variable when a non-mocked call
is about to be issued. Models, endpoints, input/output prices, token limits,
maximum call count, and a positive US-dollar cap must be explicitly configured.
Temperature is recorded and configurable in [0,1], defaulting to 0.3 as an
evaluation setting. This is not a claim about the original paper's complete
decoding setup; the released SDK adapters default their temperature to unspecified.
With temperature zero, N=2 candidates generated
by the same model and prompt may be identical; preserve that setting in the report.
Planning can validate `ModelConfig` with `require_opt_in=False`; actual model
construction requires `opt_in=True`. No live calls were made while implementing
or testing these adapters. Actual execution uses `models.ModelConfig` and
`models.BudgetedModel`.

Use one shared `BudgetLedger` for all solver, reflection, classification,
candidate, selector, and consolidation calls across conditions and perspectives.
Each request reserves the configured maximum input/output cost before issuance.
Known provider token usage reconciles that reservation; failed or unknown usage
retains the full amount. API requests set an explicit `max_tokens`, enforce a
conservative UTF-8 text bound for input, reject redirects, and never retry
automatically. Models must support this output parameter, the configured temperature,
text input, and standard prompt/completion billing. This is not a universal client
for arbitrary reasoning, audio, multimodal, hosted-tool, or nonstandard billing
APIs. The configured prices must cover every billable token; additional cache
pricing is unsupported. Dollars are estimates at those configured prices, while
provider token counts are labeled actual when supplied. Unknown pricing cannot
start a capped run, and unknown usage is never reported as free.

The input reservation assumes a text tokenizer uses at most one token per UTF-8
byte plus the recorded request/role overhead, with no undisclosed billable input.
Provider token/limit violations are recorded and prevent further requests; a
client cannot undo a charge from a provider that violates its declared contract.
This operational spending guard is not a guarantee about a provider's final
billing statement. No hidden credentials, pricing, or budget defaults are chosen.

`FakeWorldModelAgent.bind(task)` provides the paper controller's executor callback.
Ordinary mode bounds a single assistant's steps. Hierarchical mode enables a real
Planner → Web Search/Analyzer/Browser delegation loop with paper step limits
20/3/3/5 **per invocation**. The Planner delegates tool work; subordinate outcomes
return as observations before its next step. Every role gets its own guidance and
step reflection, and accepted advice is consumed by that role's next model call.
Each perspective receives a fresh fake world. This uses the simulation's authored
tool/task environment, rather than the original paper's benchmark task set.

Before running paid evaluation, review and configure all of the following:

1. Feed only public requests and ordinary fake tool observations to a real
   assistant. Parse its structured final answer independently of its claimed
   success. Give each version the same model, normal-task limits, starting history,
   and fake tools. Pin the actual repaired and improved package revisions.
2. Use separate sidecar/Gateway data directories and process instances for each
   actual condition and sequence. Supply trusted fake `MemoryAudience` and prepared
   project context through the real OpenClaw harness; text supplied by a model
   must not establish scope. An independent server request is not an end-to-end
   substitute for the plugin's hook and memory-audience behavior.
3. Track input/output usage for **both** assistant and SCOPE synthesis,
   classification, and consolidation calls. Reserve a worst-case permitted call
   amount before issuing requests, stop before issuing an unreserved request, and
   reconcile usage afterward. A post-call estimate alone cannot enforce a limit.
   Unknown usage/pricing must stay unknown and prevent starting a capped run.
4. Supply normal corrections and observed failures to learning, never scorer
   keys or held-out expected answers. Store evaluation outcomes in a scorer
   database; send validated fixture results to production `/outcome` only in a
   separately specified outcome-learning experiment. Doing so by default would
   change what evidence each version can learn from.
5. Record failures, aborted/capped tasks, latency, and all consumption. Freeze the
   comparison protocol, minimum worthwhile effect, primary endpoint, cluster
   assignments, and stopping policy before opening held-out results.

The current improved sidecar integration contract is protocol 3:

```json
{
  "agent_name": "simulated-agent",
  "scope": {"audience_key": "sim:user-a", "project_key": "sim:project-a"},
  "operation": "list",
  "args": {}
}
```

`POST /memory/query` supports `list`, `history`, `detail`, `usage`, and `status`;
the snapshot includes a revision. `POST /memory/mutate` adds `expected_revision`
and supports `disable`, `restore`, `assign_scope`, `pause`, and `resume`. Undo uses
`args.history_id`; rule changes use `args.rule_id`. Stale revisions return 409,
out-of-scope IDs return 404. Optional sidecar authentication must be forwarded.
`GET /rules/{agent_name}` and `POST /step` require the same scope; `/step` can call
models and must not be invoked by the offline runner.

See [the evaluation proposal](../docs/simulation-evaluation-plan.md) for the
larger-study design and [the literature review](../docs/memory-systems-literature-review.md)
for why recall scores alone cannot establish more reliable task completion.
