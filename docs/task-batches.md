# Task-specific diagnostic and held-out batches

These batches are authored for the user's role-specific comparison of EvolveClaw
and SCOPE. They use five task categories: coding, research, writing, planning
and data. The original pilot and 100-sequence development suite remain separate.
New authoring does not itself establish model performance or statistical power.

## Dataset and boundaries

| Split | Per category | Family clusters per category | Batches | Total sequences |
| --- | ---: | ---: | ---: | ---: |
| Diagnostic | 10 (two variants per family) | 5 | 5 | 50 |
| Held-out | 100 (five variants per family) | 20 | 50 | 500 |

A batch contains ten sequences from one category. Each sequence has two public
learning tasks, an ordinary feedback turn and two fresh future probes. Each
sequence is run against all five conditions, making 50 condition-sequence runs
per batch and 2,750 across the complete 550-sequence design. There are 1,100
distinct future probes before repetitions or condition comparisons. Variants
share their family cluster; reviewed family IDs do not prove independence.

Variants are spread across batches. Memory stays isolated by condition and
sequence, with learning history preserved inside the sequence. A batch boundary
does not grant permission to mix memories or reset a sequence midway. Category
results and family-aware uncertainty should be reported after combining the
appropriate sequence records, rather than treating batches as independent data.

## What each category checks

- Coding: constrained pure Python functions, public tests and independent private
  regression cases. Candidate code executes in a disposable restricted child
  process; supplied success flags cannot pass. Public `code.check` sees only
  public test cases. Final `code` is checked independently after execution.
  This is snippet-level coding coverage, not a full repository benchmark.
- Research: explicitly synthetic frozen source bundles and independent factual
  and citation/source decisions. No live-web search or freshness claim follows.
- Writing: structured factual content plus nonempty text, declared length limits,
  required content alternatives and exclusions. Different wording is possible;
  this deterministic rubric is not a complete semantic or subjective style judge.
- Planning: constrained schedules, choices, policies and current context.
- Data: independently computed calculations and transformations on supplied data.

Instructions state the required answer fields and constraints. Scoring keys are
not sent to solvers or learners. Public code tests may disclose their own expected
returns as ordinary development feedback; private regression cases remain in
the scorer-only export. Held-out model outputs must not be used to tune prompts,
task wording, grading rules or learned-rule selection. Authoring tests establish
reachability and mechanics; they are not model benchmark scores.

## Prepare and inspect without model calls

From the repository root, use the Python environment recorded in [HANDOFF.md](../HANDOFF.md):

```sh
PYTHONPATH=server:. /home/broedkrumme/evolveclaw-research/test-venv/bin/python \
  -m evaluation.batches --output artifacts/evaluation/task-batches-001
```

The destination must not already exist. Preparation produces `manifest.json`,
`public/sequences.json` and separate `scorer-only/scoring_keys.json`. No provider
client or credential is constructed. The public fixtures contain tool observations
that become visible to an actor only through its advertised FakeWorld tools;
do not paste the grader export into a prompt. The manifest records source-fixture
hashes, IDs, categories, counts and diagnostic limitations.

Batch IDs are `diagnostic.coding.01`, `diagnostic.research.01`,
`diagnostic.writing.01`, `diagnostic.planning.01`, `diagnostic.data.01`, and
`heldout.<category>.01` through `.10`. List them with `python -m evaluation.batches`.

Write a zero-call MiMo plan for one batch:

```sh
PYTHONPATH=server:. /home/broedkrumme/evolveclaw-research/test-venv/bin/python \
  -m evaluation.run_models \
  --provider xiaomi-mimo --model mimo-v2.6-flash \
  --base-url https://token-plan-ams.xiaomimimo.com/v1 \
  --execution-backend native-openclaw --native-json-mode \
  --max-total-tokens 10000000 --max-quota-credits 500000000 \
  --quota-cached-input-credits 2 --quota-uncached-input-credits 100 \
  --quota-output-credits 200 --max-calls 10000 \
  --max-input-tokens 65536 --max-output-tokens 2048 \
  --split diagnostic --batch-id diagnostic.coding.01 \
  --output artifacts/evaluation/diagnostic-coding-plan-001
```

Those caps are illustrative local planning guards, not a measured per-batch
forecast, subscription balance or authorization to consume that amount. Set
concrete study/batch allowances before executing. `--sequence-limit 1` can check
one authored sequence operationally; its plan explicitly marks the batch selection
incomplete and it must not be reported as a completed ten-sequence batch.

## Actual-model execution

Use the pinned isolated native profile and real-tool denial described in
[native-openclaw-evaluation.md](native-openclaw-evaluation.md). The normal runner
needs `--execute`, CLI/config/workspace paths and an explicit selected allowance.
Reusing credentials through OpenClaw is supported; exporting keys or issuing
direct Token Plan HTTP is not. No live model execution is part of task authoring.

Start with diagnostics. Preserve raw runs, rejected lessons, public test failures
and unknown usage. Typed solver step caps count as incorrect; provider, budget
and persistence errors abort. A failed batch is not replaced silently by a later
successful attempt. Choose the full-study provider, model, execution protocol,
grading contracts, meaningful improvement and stopping rules before examining
held-out model outputs. Freeze or record any later changes as a new cohort.

The existing runner saves completed sequence cells and incomplete usage on abort;
it does not resume arbitrary partially learned sequences. Use fresh output
directories and record continuations. The previous pilot's leftover local guard
is not the user's remaining Xiaomi balance. Codex authoring/analysis usage is
also separate from native MiMo execution usage; no conversion to “Codex batches”
has been measured.

## Verification checkpoint

Consult HANDOFF.md for the latest proof and authoring completion status. Before
claiming readiness, validate all 550 sequences, exported public/grader separation,
all 55 batch selections, actual constrained code execution, independent writing
constraints and representative all-five-adapter flows with an offline provider.
Offline oracle success demonstrates reachable task answers, not improved AI quality.
