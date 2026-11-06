# Operating SentinelAI

Keep the API and dashboard on loopback. Run one API worker and keep untrusted local users out of the working directory. Only register endpoints covered by explicit testing authorization. Use a disposable synthetic tenant and credentials scoped to that tenant. The tool server and retrieval index for the local demo are process-local data structures.

## Configuration

Pydantic Settings validates environment variables on startup. Copy `.env.example` to an untracked `.env` for native development, or export variables before starting the server. The database URL is handled as a secret. Credential values referenced by `auth_env` are read from the process environment. Inline credentials in profile URLs are rejected. Keep sensitive values out of headers, payload templates, display names and scenario files.

| Setting | Default or purpose |
|---|---|
| SENTINEL_DATABASE_URL | sqlite:///sentinel.db, or an operator-supplied postgresql+psycopg URL |
| SENTINEL_SCENARIO_DIR | Installed scenarios package directory, override with an operator-controlled catalogue |
| SENTINEL_PROFILES | Empty object. Named exact HTTPS endpoints, auth references, templates, mappings, capabilities and per-profile requests_per_second |
| SENTINEL_TIMEOUT | 15 seconds per interaction, including rate-limit wait |
| SENTINEL_CONCURRENCY / SENTINEL_MAX_ACTIVE | 4 simultaneous scenarios globally / 4 active assessments |
| SENTINEL_CREATES_PER_MINUTE | 10 accepted submissions per process per rolling minute |
| SENTINEL_MAX_BYTES | 65,536 inbound API body bytes and per remote request or response |
| SENTINEL_RETRIES | 1 extra attempt on eligible idempotent remote profiles |
| SENTINEL_PROVIDER / SENTINEL_JUDGE_PROFILE / SENTINEL_JUDGE_MODEL | Advisory judge selection and deployment identity |
| SENTINEL_MIN_CONFIDENCE | 0.85 for accepting secure evidence and marking advisory confidence |
| SENTINEL_PRICE_PER_MILLION_TOKENS | Optional USD blended rate for target usage |
| SENTINEL_LOG_LEVEL | INFO. Service error events carry event name and failure type |
| POSTGRES_PASSWORD | Required generated hex password for the Compose database |
| SENTINEL_DASHBOARD_API_PORT | Local API port used by the Streamlit client (8000) |

The Compose file starts the offline configuration. To enable an authorized integration in Compose, pass its specific profile, credential-reference variables and judge settings to the API service with a private local override. Keep that override outside version control. Avoid including credentials in command-line flags or enabling access logs containing sensitive query strings.

## Add a custom scenario

Copy a related entry from a bundled JSON catalogue into a top-level JSON array in the configured scenario directory. Give it a unique ID and set its requirements, setup, expected behavior, attack steps, rule, remediation and references. Set `enabled: false` to keep a definition visible while excluding it from execution. Trusted scenario definitions are persisted verbatim and must be synthetic. Restart the API to load edits. Use `GET /api/v1/scenarios/{id}` to inspect the loaded definition. Run both a positive and a negative control before interpreting results.

Rules support exact whole-response matching, a named synthetic-secret match, forbidden document IDs and forbidden tool receipts. Tool rules support a subset of arguments, an actor and an approval state. A permitted account read or a correctly approved action can be distinguished from the prohibited variant.

## Dependencies and lifecycle

Version ranges in pyproject declare supported libraries. constraints.txt records the versions from the tested environment. New installations use these constraints. Review release notes and regenerate constraints in a clean environment when updating. Run the tests, migration check and paired demo before adopting an update. To scan an installed environment, install `pip-audit` in a tooling environment, then run `pip-audit -r constraints.txt`. Triage advisories against the actual runtime and dashboard dependency sets. Review container image findings with `docker scout cves` on the built image where Docker Scout is available.

The SQLite demo is for a single process. Back up the database before applying migrations to a retained history. PostgreSQL schema upgrades use Alembic as well. Protect reports like other security findings and apply a retention policy appropriate to your lab.
