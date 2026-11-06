# SentinelAI implementation plan

## Architecture

FastAPI accepts bounded target registrations and assessment selections. A single-process scheduler owns cancellable asyncio jobs. Each job reads a frozen scenario and target configuration, compiles declarative steps into interactions, invokes an adapter and evaluates observed output. Evidence passes through a disclosure boundary before SQLAlchemy persists it. Reports read only those persisted records. The demo runs entirely in memory with synthetic documents, accounts, tools and identities.

## Planned repository

```text
app/
  main.py                     API factory and lifecycle
  api/                        request models, resources and errors
  core/                       validated settings, logging, security
  database/                   mapped entities and session factory
  attacks/                    scenario schema, registry and module interface
  targets/                    target contract, mock, HTTP and demo adapters
  demo/                       synthetic retrieval and tool policy
  evaluation/                 deterministic evidence, optional judge, metrics
  orchestration/              scheduler, assessment and execution lifecycle
  reporting/                  persisted result projections and renderers
scenarios/                    six JSON catalogues
alembic/versions/             explicit versioned schema
scripts/                      end-to-end demo client
dashboard/                    optional Streamlit API client
tests/{unit,integration,security}/
docs/                         architecture, plan, threat model, methodology,
                              API, security, demo, coverage and example report
.github/workflows/            lint, typing, tests and PostgreSQL checks
Dockerfile, docker-compose.yml, pyproject.toml, alembic.ini, .env.example,
.gitignore, .dockerignore, LICENSE, README.md
```

## Data model

UUID primary keys and timestamps throughout. Targets hold a display name and configuration with credential references. Assessments reference targets and freeze configuration. Scenario definitions track a versioned content digest. Assessment scenarios bind an assessment to immutable definitions and track progress. Attack executions store timing and sanitized observations. Evaluation results and findings reference executions. Tool invocations reference executions. Report metadata records format, assessment and content hash. PostgreSQL uses JSONB for variable shapes. SQLite supports the zero-service demo and fast deterministic tests. Schema changes go through Alembic.

## Dependencies and boundaries

Python 3.12+, FastAPI, Pydantic v2 / pydantic-settings, SQLAlchemy 2, psycopg, Alembic, HTTPX and Uvicorn. Development uses pytest, Ruff and mypy. Streamlit is optional. Docker Compose supplies PostgreSQL and the API.

Trusted operators control deployment settings, credential bindings and local scenario files. API clients operate in a single-user loopback deployment. Remote access requires both operator allowlisting and registration confirmation. Remote responses, retrieved documents, tool content and judge opinions are untrusted. Keep raw remote text out of persistent evidence, bound all remote IO, and never dispatch arbitrary tools. Demo policy controls run outside the simulated reasoning layer.

## Phases and verification gates

1. Foundation. Configure packaging, settings, migrations, domain contracts, demo/mock adapters and health endpoints. Migrate a scratch database, run foundation tests and lint.
2. Attack engine. Validate structured definitions, execute steps and compare actual responses on prompt injection, leakage and jailbreak fixtures. Exercise sequential and concurrent scheduling.
3. Advanced AI security. Add tenant-aware retrieval, tool simulation, agent boundaries, structured traces and an optional hosted judge. Test the secure/vulnerable pairs and ambiguous outcomes.
4. Reporting. Persist findings and evidence with run snapshots, compute explicit-denominator metrics and render three report formats. Check reproducibility and escaping.
5. Hardening. Enforce egress policy, size, rate and concurrency limits, cancellation and lifecycle integrity. Run security and API/database integration suites, package services and exercise available runtimes.
6. Dashboard and documentation. Deliver the reviewer workflow, coverage matrix, threat model, diagrams and measured sample report. Run final lint, typing, tests and a live local demonstration.

## Environment baseline

The workspace was empty. Windows has Python 3.13 and 3.14, Git and the Docker CLI. Use an isolated Python 3.13 environment locally and Python 3.12 in the container. Check daemon availability independently of the CLI.

### Phase 1 gate
Created packaging, app/core, app/database, app/targets, synthetic fixtures, app/main.py, Alembic revision 0001 and foundation tests. Fixed an unqualified type in the generated migration. Verified SQLite upgrade and schema check, three adapter tests, Ruff format/lint and API readiness/docs. PostgreSQL service verification follows in phase 5. Next: scenario execution.

### Phase 2 gate
Added app/attacks, app/orchestration/execution.py, app/evaluation/rules.py, three scenario catalogues and registry/security tests. All 42 tests passed, including both modes for 18 probes, invalid imports, ambiguous output and retry identity. Ruff passed. This gate covers individual conversations. Scheduling and durable run state are integrated with persisted findings in phase 4. Next: RAG, tool and privilege fixtures.

### Phase 3 gate
Added app/demo retrieval, principal/tool policy and lab interpreter, the remaining three catalogues plus indirect injection, typed trace evaluation, app/evaluation/judge.py, and HTTP adapter groundwork. All 91 tests passed, including the secure/vulnerable pair for every one of 41 scenarios. Ruff passed. MCP currently uses local simulated dispatch. Hosted inference is optional and has no live credentials in this environment. Next: database-backed execution, reports and API.

### Phase 4 gate
Created app/api, app/reporting, metrics, evidence projection, scheduler, API integration and report tests. Runs freeze definitions, persist each evaluation and tool receipt transactionally, and export reproducible JSON, HTML and Markdown. The API supplies target and assessment history, cancellation and human review. All 96 tests passed, including both full runs through FastAPI, all report formats and repeat exports. Ruff and mypy passed. Single-worker scheduling and projected evidence are intentional constraints. Next: hostile network and lifecycle tests, Compose and CI.

### Phase 5 gate
Added network and service regression tests, concurrency/cancellation tests, Dockerfile, Compose, environment template and CI workflow. The SQLite-backed suite passed 123 tests with one explicitly gated live judge test skipped. A real temporary PostgreSQL 17.11 server applied migration 0001, reported no schema drift, and passed all three API integration cases present at that check. Ruff and mypy passed. Compose config validation passed. Docker Desktop startup timed out and its backend log identified an inaccessible inference socket. Container startup remains unverified locally. Next: reviewer workflow and documentation.

### Phase 6 gate

Delivered the Streamlit dashboard, paired demo CLI, README, MIT license, dependency constraints, architecture and sequence diagrams, threat model, API reference, security guide, evaluation methodology, demo guide, scenario matrix and an exported Markdown report. End-to-end review added public response schemas, precise tool argument/actor/approval predicates and missing-trace checks.

The running SQLite API executed both 41-scenario configurations. The vulnerable target produced 41 failures and the secured target produced 41 passes. Both runs had zero errors and zero inconclusive outcomes. A separate one-scenario pair reproduced missing approval. Streamlit AppTest opened all four dashboard pages against the live API, selected the vulnerable run and rendered its 41 findings. API readiness, OpenAPI documentation and dashboard health returned HTTP 200.

Final verification on Python 3.13 passed 127 tests and skipped one explicitly gated hosted judge test. Ruff lint and formatting passed, mypy passed on 37 application files, and pip check found no broken requirements. PostgreSQL 17.11 passed upgrade/downgrade/upgrade, schema drift detection and seven integration tests, with the hosted judge skipped. Compose configuration validated. The actual Compose startup could not access the Docker Desktop Linux engine pipe.

Outstanding deployment verification is a Compose smoke run on a working Linux container engine and an explicitly authorized hosted-provider run. The checked-in CI workflow has not been run on GitHub. Potential extensions include a durable task queue, authenticated ownership, independent server audit capture, vector retrieval and protocol-level MCP.
