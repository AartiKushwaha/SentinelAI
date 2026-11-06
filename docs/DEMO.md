# Reviewer walkthrough

1. Follow the native or Compose commands in the README. Request `GET /ready`. A ready response verifies access to the migrated report table.
2. Run `python scripts/demo.py` from the environment with HTTPX installed. The script creates a vulnerable and a secured target, polls both assessments to completion and exports all three formats for each run. The two runs use the same definitions and isolated fixture state. `--port` and `--output` select a local API port and export directory.
3. Open the vulnerable HTML report. In the cross-tenant RAG case, inspect the retrieved document IDs. In the approval case, inspect the executed ticket receipt, argument value, support actor, north tenant and missing approval. In the leakage case, inspect the matched fixture field and response length. The raw seeded secret is withheld.
4. Open the secured JSON report and locate the same scenario IDs under executions. Compare their receipt statuses, decisions and retrieved context. Use the definition digests to check that both runs used the same test definitions.
5. Launch Streamlit and select **Assessments**. Switch between the two entries in assessment history. Inspect severity and category views, expand a finding and download its report. **Targets** can register a new lab instance. The scenario catalogue shows each probe and remediation.
6. To review a single issue by hand, submit a one-scenario assessment. The following command produces a compact matched pair:

```console
python scripts/demo.py --scenario tool_misuse-approval
```

The local support agent interprets a small bracketed fixture language embedded in natural-language prompts. In vulnerable mode it may publish a protected marker, reveal a seeded value, incorporate an untrusted document or dispatch beyond the caller's scope. In secured mode the retriever and tool dispatcher enforce their respective policies. Returning an ordinary phrase, claiming to have used a tool or merely mentioning a field name is insufficient to establish a violation.

A secured target can also set `forbidden_actions: []` at registration to change the local publication policy. Revisit the expected predicate when changing policy. Every successful probe should be interpreted against the target's intended behavior.

## Reproduce a result

Preserve the trusted scenario catalogue, application revision, target profile and synthetic fixtures for the run. Compare report configuration, definition digests, steps and evidence. The demo starts each scenario from a clean lab. Remote services may drift even when the request is identical. Existing reports are regenerated from committed records without contacting the target or judge.

Use Ctrl+C to stop a foreground native API or dashboard. Run `docker compose down` to stop Compose services. Exported evidence is under the chosen output directory and remains available after shutdown.
