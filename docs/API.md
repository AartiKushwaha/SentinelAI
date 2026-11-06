# API guide

Use the loopback base URL `http://127.0.0.1:8000/api/v1`. Interactive documentation is at `/docs`, machine-readable OpenAPI at `/openapi.json`. Health and database readiness are at `/health` and `/ready`.

| Method and path | Result |
|---|---|
| POST /targets | 201. Register a local demo or a confirmed deployment profile. |
| GET /targets, GET /targets/{id} | List targets or read a registration. |
| DELETE /targets/{id} | 204. Referenced targets return 409 to preserve history. |
| GET /scenarios, GET /scenarios/{id} | Filter the catalogue by category, severity and enabled state, or inspect a full definition. |
| POST /assessments | 202 with UUID and queued status. Accepts target_id, optional scenario_ids, category, severity and concurrency. |
| GET /assessments | Newest first. Filters include status and target_id. |
| GET /assessments/{id} | Read lifecycle status, configuration snapshot, per-scenario progress and metrics. |
| POST /assessments/{id}/cancel | Cancel active work and retain completed executions. Repeating cancellation is supported. |
| GET /assessments/{id}/findings | Paginated findings with optional category and severity filters. |
| GET /assessments/{id}/report | Terminal assessment export. Set format to json, html or markdown. ETag is a SHA-256 content digest. |
| PATCH /assessments/{id}/executions/{execution_id}/review | Supply status reviewed, confirmed or dismissed. Execution UUIDs are in the JSON report. |
| GET /metrics/summary | Counts and decided-test ASR across all assessments. |

List operations accept offset (default 0) and limit (1–100, default 50). The input and error envelope are documented in OpenAPI. Sample error body: `{"error":{"code":"invalid_scenario_selection"}}`. A 422 indicates invalid inputs, 409 indicates conflicting state, 429 signals rate or worker capacity, and 503 indicates a database failure.

## Manual local assessment (PowerShell)

```powershell
$api = 'http://127.0.0.1:8000/api/v1'
$t = Invoke-RestMethod "$api/targets" -Method Post -ContentType application/json -Body '{"name":"Support lab","adapter":"demo","mode":"vulnerable"}'
$body = @{target_id=$t.id; scenario_ids=@('rag-tenant','tool_misuse-approval'); concurrency=1} | ConvertTo-Json
$r = Invoke-RestMethod "$api/assessments" -Method Post -ContentType application/json -Body $body
Invoke-RestMethod "$api/assessments/$($r.id)"
Invoke-RestMethod "$api/assessments/$($r.id)/report"
```

## Remote adapter

The operator configures named profiles in the JSON-valued environment variable `SENTINEL_PROFILES`. Registering raw URLs through the API is unsupported. The following profile illustrates a custom application contract. Replace the reserved example hostname only with an endpoint you are explicitly authorized to test.

```json
{
  "support-staging": {
    "url": "https://support.example/assess",
    "method": "POST",
    "headers": {"Accept": "application/json"},
    "auth_env": "SENTINEL_CRED_SUPPORT",
    "auth_header": "Authorization",
    "auth_prefix": "Bearer ",
    "payload": {"conversation": "$messages", "current_question": "$prompt"},
    "text_path": "result.answer",
    "decision_path": "result.policy_decision",
    "trace_path": "result.trace",
    "usage_path": "usage.total_tokens",
    "capabilities": ["chat","rag","tools","agent"],
    "requests_per_second": 2,
    "idempotent": false
  }
}
```

Template variables replace entire JSON values, including inside lists. `$messages` carries the ordered history. `$prompt` carries the current prompt. Paths can traverse arrays, for example `choices.0.message.content`. Decisions are `denied` or `answered`. Omit optional paths for unavailable telemetry. Every configured path must exist in its response. A trace is an object with optional `documents` (ID array) and `tools` (receipt array). Example receipt:

```json
{"tool":"account","actor":"support","user":"reader","tenant":"north","arguments":{"value":"south"},"status":"executed","approved":false}
```

Export the credential through the named process environment variable. The secret reference is bound to its exact profile by the operator. Register the deployment through `POST /targets`:

```json
{"name":"Staging support","adapter":"http","kind":"tool_agent","profile":"support-staging","authorized":true}
```

Create custom scenarios with markers, fixture setup and expected secure outputs appropriate to the registered application. The lab's fixture directives have meaning to the local interpreter. A remote service needs equivalent seeded data or its own probes. The `kind` label describes the deployment, while `capabilities` controls eligibility. An explicit list containing disabled or incompatible probes is rejected.

## Hosted judge

Set `SENTINEL_PROVIDER=hosted`, `SENTINEL_JUDGE_PROFILE=judge` and `SENTINEL_JUDGE_MODEL` to your deployment's model identifier. Add a separate named `judge` profile to the same profile map. For a chat-completions-compatible service, configure its authorized HTTPS endpoint, `payload={"model":"$model","messages":"$messages"}`, `text_path=choices.0.message.content`, and an auth_env reference. The judge must return a JSON object conforming to the schema supplied in its prompt. The judge-only profile cannot be registered as a target. External billing and output variability depend on the selected provider.
