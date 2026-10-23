# Memory architectures: bounded literature sprint

13 October 2026, approximately15:03–15:11UTC. This research is for the phase **after** the current EvolveClaw improvement design. No EvolveClaw code, live runtime/configuration, external accounts or provider-model calls changed. Firecrawl retrieved complete versioned papers, current author-repository pages and two pinned implementation files. This is not an exhaustive literature review or an efficacy reproduction.

## Main implication

Prioritize **versioned, scope-bound observations plus derived current-state memory** over selecting a vendor/framework by a headline retrieval score. Zep's distinction between observation time and fact-validity time, Letta's versioned context, and Mem0's explicit namespaces are useful patterns. A-Mem's associative linking is worth testing later, with links confined to authorized scope. These methods largely evaluate conversation QA; none of the inspected evidence proves that adding their retrieval layer reduces mistakes on EvolveClaw's everyday tool tasks.

Keep facts/episodes distinct from behavioral guidelines. “The booking was cancelled on Tuesday” needs a dated factual record; “Verify confirmation before claiming completion” is a reusable procedure. A shared vector similarity score cannot establish the authority, current validity or global scope of either.

## Paper evidence, with baselines and limits

### MemGPT: bounded working memory with explicit external recall

[MemGPTv2](https://arxiv.org/html/2310.08560v2), revised12February2024, describes static instructions, editable working context, a FIFO recent-message queue, archival storage and indefinitely retained recall history. LLM tool calls move information between tiers; warning/flush thresholds prompt saving and eviction. Eviction forgets *in-context access*, not the original record.

Reported DMR accuracy with GPT-4Turbo is93.4% versus35.3% for the same model's lossy recursive-summary baseline. Those are not equal-access full-context competitors. Questions are generated from five-session Multi-Session-Chat conversations and judged against narrow gold answers. The paper text inspected does not clearly restate the scored sample count; Zep's later reproduction explicitly uses500conversations. This is conversational recall/document-analysis evidence, not downstream reliability. Extra memory tool/model turns add cost; no transferable end-to-end dollar saving was established.

Publication status: arXivpreprint; no peer-reviewed venue proved in this sprint. Coverage: completev2HTML and metadata.

### A-Mem: linked notes that evolve with later evidence

[A-Memv11](https://arxiv.org/html/2502.12110v11),8October2025, stores original content/timestamp plus model-produced keywords/tags/context, embedding and links. New observations can update related notes' context/attributes; the evolved note replaces its predecessor. This is useful associative organization, but a replacement mechanism alone is not version history or safe conflict resolution.

The paper describes7,512LoCoMoQA pairs across five categories, including adversarial questions. Table1: GPT-4o-mini temporalF1 improves25.52→45.85 versusMemGPT; multi-hopF1 is26.65→27.02, so prose suggesting universal doubled multi-hop performance overstates that row. GPT-4o single-hopF1 falls60.16→48.43. DialSimF1 rises2.55→3.45 versusLoCoMo, but absolute scores remain low. Retrieval-token reductions do not establish full ingestion/link/evolution costs.

Publication status: **peer-reviewed NeurIPS2025poster**, verified by [official OpenReview](https://openreview.net/forum?id=FiM0M8gcct); this memo analyzes arXivv11, not a byte comparison to the final proceedingsPDF. Coverage: fullv11HTML, officialvenuepage, author implementationREADME.

### Mem0: extract/update memories, with materially changed current software

[Mem0v1](https://arxiv.org/html/2504.19413v1),28April2025, extracts salient facts from a message pair plus summary/recent context, then selects ADD/UPDATE/DELETE/NOOP against similar records. Its graph variant models relationships. The evaluated LoCoMo subset has10conversations, roughly200questions/conversation, excluding adversarial questions; the exact scored denominator is not restated numerically. Do not compare directly to A-Mem's stated7,512/five-category setting.

Table2: judge scoreMem066.88, graph68.44, ChatGPT-memory52.90, full-context72.90. The26%relative claim is versusChatGPT memory, not full-context. Mem0 p95answer latency1.440s versus17.117s full-context and retrieved1,764 versus26,031tokens explain the efficiency claim; ingestion/extraction/embedding costs are excluded from those answer-context totals.

Publication status: arXivpreprint absent proved venue. Coverage: completev1HTML, current authorREADME and one pinned sourcefile; no run/reproduction.

### Zep/Graphiti: episodes, semantic relationships and bitemporal validity

[Zepv1](https://arxiv.org/html/2501.13956v1),20January2025, retains raw episodes and derived entities/relations, with community summaries. Edges track valid/invalid fact times separately from system-created/expired times. New contradictory facts invalidate prior overlapping edges rather than simply erasing history. Provenance and “what was true then?” queries are directly relevant to EvolveClaw's scoped history; time priority still needs source-authority rules.

DMR uses500conversations: GPT-4TurboZep94.8%, full-context94.4%, publishedMemGPT93.4%. The improvement over equal-model full-context is only0.4percentagepoints. LongMemEval-S GPT-4o: full-context60.2→Zep71.2%, latency28.9→2.58s, context115k→1.6ktokens; “18.5%” is a relative improvement, not18.5points. The paper does not restate the LongMemEval-S scored denominator, so verify against benchmark artifacts before replication. Some question categories regress.

Publication status: arXivpreprint absent proved venue. Coverage: fullv1HTML, authorGraphitiREADME and one pinned sourcefile.

## Current author-code/product distinctions

These are fresh primary repository claims and limited source inspections, not paper replications:

| Source snapshot | What is actually supported by inspected material | EvolveClaw implication |
| --- | --- | --- |
| [Letta legacy repo](https://github.com/letta-ai/letta/tree/5bcdd177d70fa2b31a754cfcd801e77b2e1ab16a) and [current LettaCode](https://github.com/letta-ai/letta-code/tree/2943efe47e8c49e8ef2b78df100ba8e262c2415a) | Legacy server is archived. Active harness advertises git-trackedMemFS context, memory blocks, project/global/agent skills and inspect/dream controls. | Borrow context versioning and separately scoped durable blocks; do not recommend archived server as current. Git history aids inspection/reversal but is not proof of semantic undo across all derived indexes/actions. README-only coverage. |
| [A-mem-sys](https://github.com/WujiangXu/A-mem-sys/tree/f303dfc71e07bdc787f4bc135d4cea328ae30e99) | Documents ChromaDB, metadata-enriched embeddings, dynamic links, CRUD and retrieval counters. Explicitly points to a different [benchmark repository](https://github.com/WujiangXu/AgenticMemory) to reproduce paper results. | Scoped linking, timestamps and raw-content preservation are candidates. No user/project isolation or reversible revision API was established by this README; do not infer them from CRUD. |
| [Mem0current](https://github.com/mem0ai/mem0/tree/d26ba5e4518cef7fff3c66d4f715b21adf9feabe), [memory/main.py](https://github.com/mem0ai/mem0/blob/d26ba5e4518cef7fff3c66d4f715b21adf9feabe/mem0/memory/main.py) | April2026README announces ADD-only extraction, first-class agent facts, entity/BM25/semantic retrieval and temporalranking. Source requires nonempty user/agent/run identifier and applies filters; supplies history/delete/manualupdate surfaces. | Immutable observations with derived latest-state views improve reversibility. IDs/filters are technical partitioning, not authentication. Broadly storing assistant-confirmed actions with equal weight risks retaining mistaken completion claims unless verified. |
| [Graphiticurrent](https://github.com/getzep/graphiti/tree/2f0fb35b749f1ff17377892e099882176e453393), [graphiti.py](https://github.com/getzep/graphiti/blob/2f0fb35b749f1ff17377892e099882176e453393/graphiti_core/graphiti.py) | Group-scoped ingestion/search and request-local driver bundles; episode removal exists. README distinguishes self-hostedGraphiti from managedZep's proprietary graphengine and built-in user/sessionmanagement. | Useful scope/provenance/temporal patterns, with additional graph infrastructure and application-owned authorization. Episode deletion is not automatically a complete rollback of later derived facts. Sourcefile coverage is partial. |

Mem0's currentREADME reports92.5LoCoMo/94.4LongMemEval for the **managed platform**, explicitly acknowledging proprietary optimizations absent fromOSS. Those are vendor-reported2026results without a protocol/denominator audit here and must not replace the2025paper's numbers or be promised for an EvolveClaw integration. Graphiti similarly does not guarantee Zep's production performance.

## Scoping, updating, forgetting and reversal: research priorities

1. **Authority before retrieval/linking.** Select host-authorized audience plus project before semantic search, neighbor updates, merging or graph traversal. MemoryAudience in OpenClaw is owner-private-agent or conversation-agent/session, not arbitrary universal human identity. Bind any finer sender mapping to authenticated producer context. Never ask an LLM to choose the user's access scope.
2. **Append evidence; derive state.** Store original observation, source/run/tool identity, timestamp, confidence basis and scope separately from a model's summarized rule/fact. Use explicit supersedes/validity relationships and revisions. Old observations can remain available to authorized history while current retrieval excludes invalid/superseded state.
3. **Separate forgetting from deletion.** Low retrieval priority, expiration, disabling a rule and erasing evidence are distinct operations. None of the four papers establishes a comprehensive privacy-aware forgetting/undo policy for EvolveClaw. Recompute dependent views/indexes after reversal; guard concurrent revision writes.
4. **Measure the full pipeline.** Count extraction, embeddings, neighbor classification, graph resolution, compaction, retrieval and downstream answer calls. Report answer latency separately from ingestion/maintenance latency and cache cost. Small correlated conversational datasets do not justify universal efficiency or reliability guarantees.
5. **Evaluate state changes, then tool outcomes.** Test contradictory/implicit updates, changing project conventions, stale preferences, unsupported inference, cross-user/project isolation and rollback consistency. Keep first-answer task success and verified completion separate from recallF1/judge scores. Retrieve-only improvements may still cause more actions or amplify false memories.

Priority order for the later phase: bitemporal/evidence/versioning patterns first; bounded multi-signal retrieval second; associative links/agent-managed memory and graph infrastructure only after a scoped, versioned baseline shows measurable benefit. This is a research prioritization, not a decision to replace SCOPE or add a vendor dependency now.

## Coverage and reproducibility record

Successful source artifacts are under `/home/broedkrumme/evolveclaw-research/literature-sources/`:

- Fullpapers: `memgpt-full-v2.json`, `amem-full-v11.json`, `mem0-full-v1.json`, `zep-full-v1.json` contain entire Firecrawlmarkdown/metadata, canonical versionedURL and retrievaldate.
- Metadata: `memgpt-meta.json`, `amem-meta.json`, `mem0-meta.json`, `zep-meta.json` distinguish abstract/versionhistory from fulltext.
- Venueproof: `amem-review-official.json`.
- RepositoryREADME snapshots: `letta-repo.json`, `letta-code-repo.json`, `amem-sys-repo.json`, `mem0-repo.json`, `graphiti-repo.json`.
- Pinned partialimplementation: `mem0-source-d26ba5e.json`, `graphiti-source-2f0fb35.json`.
- Discovery: `search-0.json` through`search-4.json`, explicitly marked excerpts. Fresh2026STALE/ Human-InspiredMemory papers were discovered but not reviewed here; root's parallel benchmark/revision research owns that follow-up. No stronger2026architecture claim is made from an abstract alone.

Early unversioned `*-full.json` attempts hit the shared Firecrawl ratecap and are **failure artifacts**, not fulltext coverage; subsequent `*-full-v*.json` files succeeded. Two requests per minute were observed after coordinating the shared cap. Complete HTML tables can have flattened headings; selected values above were checked against their row/category context. Exact unavailable denominators are labeled instead of reconstructed from percentages. No repository code was executed or comprehensively audited; no benchmark was reproduced.
