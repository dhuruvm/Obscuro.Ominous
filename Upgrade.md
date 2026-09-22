(#) DS-Agent Upgrade Plan

## 1. Purpose

Convert the current Obscuro Ominous command-line data tool into a proper agentic AI data scientist system. The target is not a chatbot with a large prompt. It is a controlled, stateful system that can:

- understand a high-level data or model objective;
- create and revise an execution plan;
- call ingestion, research, cleaning, deduplication, labeling, storage, evaluation, and model tools;
- observe every step and its result;
- recover from transient failures;
- stop, ask for approval, or roll back when risk or uncertainty is high;
- produce reproducible datasets, model artifacts, reports, and provenance.

`Agent.md` describes the long-term industrial target. The current repository is a local Windows/Ollama proof of concept, so this plan deliberately separates the first useful agent from later distributed infrastructure.

## 2. Current-State Assessment

### What already exists

- `cli.py` provides command routing and an interactive terminal menu.
- `pipeline/model_manager.py` provides Ollama discovery, model pulls, streaming generation, and model creation through the local API.
- `pipeline/chat_interface.py` provides interactive chat, CPU/GPU selection, streaming output, and timing metrics.
- `pipeline/autonomous_agent.py` has a fixed research, cleaning, and dataset-commit workflow.
- `pipeline/research_browser.py` can query Wikipedia and DuckDuckGo and scrape pages.
- `pipeline/cleaner.py` performs basic HTML removal and normalization.
- `pipeline/dataset_store.py` stores JSONL plus tokenized `.bin`/`.idx` artifacts and a registry.
- `workers/job_manager.py` provides local multiprocessing for cleaning and tokenization.
- `pipeline/model_store.py` provides a local catalog of Ollama and GGUF models.

### What is not yet agentic

- The autonomous workflow is hard-coded rather than selected by a planner.
- There is no durable run state, task graph, checkpoint, resume, cancellation, or retry policy.
- Tool inputs and outputs are informal Python values rather than versioned schemas.
- Dataset verification falls back to acceptance when the model returns invalid JSON; this hides quality failures.
- There is no exact or fuzzy deduplication, language identification, perplexity scoring, poisoning defense, drift report, or ML-BOM.
- Dataset metadata is incomplete: transformations, source hashes, code version, model version, and configuration are not recorded together.
- Training currently builds an Ollama model with dataset context. It is not neural fine-tuning and does not produce newly trained GGUF weights.
- There is no evaluation set, regression suite, quality scorecard, or agent success metric.
- Registry writes are not transactional and concurrent runs can collide on IDs and files.
- The CLI is synchronous and local; Ray, Slurm, vLLM, Datatrove, Rust extraction, and object storage are future scale layers, not current capabilities.

## 3. Target Operating Model

The system should be organized around a durable `Run` rather than a single function call.

```text
User goal
	-> Run creation and policy check
	-> Planner creates a typed task graph
	-> Executor claims one task at a time
	-> Tools perform bounded work
	-> Observer records events, metrics, artifacts, and evidence
	-> Evaluator scores the result
	-> Planner revises, retries, asks approval, or completes
	-> Report and artifacts are committed to their stores
```

The agent must always be able to answer:

1. What goal is being pursued?
2. What task is running now?
3. Why was this task selected?
4. What evidence did the task produce?
5. What changed in the dataset or model store?
6. What failed, what was retried, and what was skipped?
7. Can the run be resumed or audited later?

## 4. Core Architecture

### 4.1 Agent kernel

Add `pipeline/agent/` with these components:

- `types.py`: typed `RunSpec`, `TaskSpec`, `TaskResult`, `ArtifactRef`, `Evidence`, `QualityReport`, and `ApprovalRequest`.
- `planner.py`: converts a goal into a task graph using a strict JSON schema and validates dependencies before execution.
- `executor.py`: executes tasks through a registered tool catalog, enforces timeouts, concurrency limits, retries, and cancellation.
- `state.py`: persists run state and task state in SQLite first; support Postgres later.
- `memory.py`: stores durable facts, run summaries, failed strategies, and user preferences. Do not use an unbounded chat transcript as memory.
- `policy.py`: controls network access, allowed tools, maximum cost, model selection, file boundaries, and approval gates.
- `observer.py`: emits structured events for progress UI, logs, metrics, and audit records.
- `evaluator.py`: scores data quality, source coverage, deduplication, label agreement, and model behavior.

The planner must never execute arbitrary generated Python or shell commands. It may select registered tools with validated arguments only.

### 4.2 Tool registry

Create a single registry with explicit contracts. Initial tools should wrap existing modules:

| Tool | Existing implementation | New contract |
|---|---|---|
| `research.search` | `research_browser.py` | Query, source policy, result limit, timeout -> URLs and evidence |
| `research.fetch` | `research_browser.py` | URL -> status, content hash, text, metadata |
| `dataset.clean` | `cleaner.py` | Input artifact -> cleaned artifact and rejection reasons |
| `dataset.deduplicate` | new | Exact/fuzzy duplicate groups and retained records |
| `dataset.score` | new | Language, quality, safety, perplexity, and anomaly scores |
| `dataset.verify` | `dataset_store.py` | Typed verdict with reason and confidence |
| `dataset.commit` | `dataset_store.py` | Atomic artifact and registry commit |
| `dataset.tokenize` | `job_manager.py` / tokenizer | Versioned `.bin`/`.idx` artifact with tokenizer metadata |
| `model.list` | `model_manager.py` / `model_store.py` | Model metadata and capabilities |
| `model.generate` | `model_manager.py` | Streaming response plus timing and usage metadata |
| `model.build` | `model_manager.py` | Ollama model build record; explicitly not fine-tuning |
| `model.evaluate` | new | Test prompts, scores, regressions, and report |
| `report.write` | new | Markdown/JSON run report and ML-BOM |

Every tool must define: input schema, output schema, side effects, required permissions, timeout, retryability, idempotency key, and artifact outputs.

### 4.3 Durable state and event log

Use SQLite for the first production-quality local implementation. Suggested tables:

- `runs`: goal, status, created time, completed time, policy, planner model, code version.
- `tasks`: run ID, task ID, type, dependencies, status, attempts, input JSON, output JSON, error JSON.
- `events`: run ID, task ID, timestamp, severity, event type, structured payload.
- `artifacts`: content hash, path/URI, type, size, producer task, schema version.
- `evaluations`: artifact/model ID, metric, score, threshold, evaluator version.
- `approvals`: requested action, risk, user decision, timestamp.

All file writes should use temporary files followed by atomic rename. Registry updates must use a lock or database transaction.

### 4.4 Planner and execution loop

The planner should return a validated task graph, for example:

```json
{
	"goal": "Create a verified medical virology corpus",
	"tasks": [
		{"id": "discover", "tool": "research.search", "depends_on": []},
		{"id": "fetch", "tool": "research.fetch", "depends_on": ["discover"]},
		{"id": "clean", "tool": "dataset.clean", "depends_on": ["fetch"]},
		{"id": "dedupe", "tool": "dataset.deduplicate", "depends_on": ["clean"]},
		{"id": "score", "tool": "dataset.score", "depends_on": ["dedupe"]},
		{"id": "verify", "tool": "dataset.verify", "depends_on": ["score"]},
		{"id": "commit", "tool": "dataset.commit", "depends_on": ["verify"]},
		{"id": "report", "tool": "report.write", "depends_on": ["commit"]}
	]
}
```

The executor runs only tasks whose dependencies succeeded. After each task it provides the planner with a compact observation: result summary, evidence references, quality metrics, and failure classification. The planner may revise the remaining graph, but completed artifacts remain immutable.

## 5. Data Quality and Safety Pipeline

Implement the quality cascade in this order:

1. **Ingestion validation**: encoding, MIME type, size, URL, HTTP status, and content hash.
2. **Normalization**: HTML removal, Unicode normalization, whitespace, boilerplate, and document boundaries.
3. **Language and format**: language identification and minimum readable-text checks.
4. **Exact deduplication**: SHA-256 of normalized documents and paragraph hashes.
5. **Fuzzy deduplication**: MinHash/LSH on shingled text. Start locally; move to Rust/Ray at scale.
6. **Quality scoring**: length, repetition, boilerplate, perplexity proxy, educational value, and source reliability.
7. **Safety and poisoning checks**: prompt injection markers, suspicious instruction payloads, secrets, malware links, repeated adversarial patterns, and anomalous distributions.
8. **LLM audit**: structured JSON verdict with schema validation and confidence. Invalid output is a failure requiring retry or deterministic review, not an automatic pass.
9. **Human approval gate**: required when quality is below threshold, sources conflict, or the run requests external side effects.
10. **Commit**: write immutable JSONL, binary index, quality report, and ML-BOM atomically.

## 6. ML-BOM and Reproducibility

Every dataset and model artifact must carry:

- source URL or input file and content hash;
- retrieval timestamp and HTTP metadata;
- cleaning, deduplication, scoring, and tokenization versions;
- source model names and exact tags;
- prompt/template identifiers and hashes;
- code commit or package version;
- hardware/device mode;
- parent artifact IDs;
- quality metrics and approval decisions;
- license and usage notes where known.

Store this as `metadata.json` beside each artifact and also index it in the state database. A dataset without provenance is not eligible for model building.

## 7. Model Lifecycle

Separate these operations clearly:

### Local inference

Ollama is the first backend. Support model capabilities, context length, GPU layers, timeout, streaming, and usage timing. Chat should select only runnable models.

### Context-built Ollama model

The current `model.build` operation creates an Ollama model with a system/context configuration. Label it accurately as `context_built`, not `fine_tuned`.

### Actual fine-tuning

Add only after the dataset pipeline and evaluation are reliable. The fine-tuning tool must specify:

- base checkpoint;
- training framework;
- hardware and VRAM requirement;
- dataset and tokenizer versions;
- LoRA/QLoRA/full-fine-tune method;
- checkpoints and resume state;
- validation split and metrics;
- merge and quantization command;
- GGUF conversion metadata;
- license compatibility.

GGUF export is an artifact conversion step, not proof that training occurred.

## 8. Evaluation and Self-Correction

Create fixed evaluation sets before enabling autonomous model changes:

- factuality and citation checks;
- domain question answering;
- refusal and prompt-injection tests;
- formatting/schema compliance;
- regression prompts from prior releases;
- latency and memory measurements;
- dataset quality thresholds.

Self-correction must be bounded. A failed run may retry a task with a different strategy, but it must have a maximum attempt count, budget, and escalation path. The agent must not silently lower quality thresholds to force success.

## 9. User Experience

Replace the current menu-only autonomous flow with three entry points:

1. `obscuro run "Create a verified dataset about ..."`
2. `obscuro status <run-id>`
3. `obscuro resume <run-id>`

The terminal UI should show:

- run ID and goal;
- current phase and task;
- elapsed time and ETA based on observed tasks;
- active model and device;
- completed/failed/retried task counts;
- quality gates and approval requests;
- artifact paths and final report.

Keep `chat`, `datasets`, `models`, and `train` as direct expert commands. The agent command orchestrates them through contracts rather than duplicating their internals.

## 10. Phased Implementation Plan

### Phase 0: Baseline and contracts

Deliverables:

- clean generated files and deterministic environment setup;
- typed schemas and versioned artifact metadata;
- SQLite state database;
- structured logging and run IDs;
- tests for registries, model calls, and atomic writes.

Exit criteria: an interrupted local run can be inspected and resumed without corrupting a registry.

### Phase 1: Local agent MVP

Deliverables:

- `pipeline/agent/` kernel;
- planner with strict JSON output;
- tool registry wrapping current research, cleaning, tokenization, and commit functions;
- executor with dependencies, retries, timeout, cancellation, and approval gates;
- `obscuro run`, `status`, and `resume` commands;
- run report and initial ML-BOM.

Exit criteria: the agent can create a small verified dataset from a natural-language goal, recover from a failed fetch, and explain every artifact.

### Phase 2: Quality and audit maturity

Deliverables:

- exact/fuzzy deduplication;
- language and repetition scoring;
- structured LLM verifier with strict schema validation;
- poisoning and prompt-injection checks;
- quality dashboard and evaluation datasets;
- immutable artifact manifests.

Exit criteria: quality thresholds are measurable, tested, and cannot be bypassed by malformed model output.

### Phase 3: Real model lifecycle

Deliverables:

- explicit distinction between inference, context-built models, fine-tuning, and quantization;
- training backend adapter;
- checkpoint/resume support;
- validation and regression gates;
- GGUF conversion and Model Store metadata.

Exit criteria: a model release has reproducible data, code, configuration, evaluation, and conversion provenance.

### Phase 4: Scale-out execution

Deliverables:

- object storage adapter for JSONL/Parquet/WARC;
- Ray task backend for distributed CPU work;
- Rust-backed extraction and deduplication workers;
- vLLM inference backend where hardware supports it;
- Slurm adapter for scheduled training;
- Prometheus/OpenTelemetry metrics.

Exit criteria: the same task contracts run locally and distributed without changing planner behavior.

### Phase 5: Industrial hardening

Deliverables:

- authentication and multi-user tenancy;
- secrets management;
- policy-as-code;
- signed artifacts and supply-chain checks;
- disaster recovery and retention policies;
- load, failure-injection, and security testing.

Exit criteria: the system can operate unattended within declared boundaries and produce an audit package for every run.

## 11. Recommended Repository Shape

```text
Ominous/
	cli.py
	pipeline/
		agent/
			types.py
			planner.py
			executor.py
			state.py
			memory.py
			policy.py
			observer.py
			evaluator.py
			tools.py
		data/
			ingest.py
			normalize.py
			deduplicate.py
			quality.py
			provenance.py
		backends/
			ollama.py
			vllm.py
			training.py
			ray.py
			slurm.py
		stores/
			state_store.py
			dataset_store.py
			model_store.py
			artifact_store.py
		reports/
			run_report.py
			mlbom.py
	schemas/
		run.schema.json
		task.schema.json
		artifact.schema.json
		evaluation.schema.json
	tests/
		unit/
		integration/
		regression/
	datasets/
	models/
```

## 12. Immediate Next Sprint

1. Add `RunSpec`, `TaskSpec`, and `ArtifactRef` schemas.
2. Add SQLite `runs`, `tasks`, `events`, and `artifacts` tables.
3. Extract current autonomous workflow steps into registered tools.
4. Implement a deterministic executor before adding planner autonomy.
5. Add strict JSON parsing and retry limits to AI verification.
6. Add atomic registry writes and file locks.
7. Add `obscuro run`, `status`, and `resume`.
8. Add one end-to-end test using a fixture dataset and a mocked Ollama backend.
9. Add quality and provenance reports to every committed dataset.
10. Only then introduce a planner model and self-correction loop.

## 13. Success Definition

The upgrade is complete when a user can state a data objective once and the agent can plan, execute, observe, evaluate, recover, and report the complete run without hidden state. Every decision is bounded by policy, every artifact is reproducible, every failure is visible, and scaling from one Windows workstation to distributed workers changes the execution backend rather than the data contract.

Lead Architect: Person
Implementation Target Date: To be scheduled after Phase 0 sizing
Internal Reference: `Agent.md`
