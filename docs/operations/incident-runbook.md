# Cowork Incident Runbook

## 1) SSE Stream Instability

### Symptoms
- Users report frozen streaming output.
- Tasks appear stuck in running state.

### Immediate Actions
- Check orchestrator `/health/ready`.
- Verify recent `X-Request-Id` traces across frontend/orchestrator/core_api logs.
- Inspect errors tagged with `send_step_failed` or `send_artifact_failed`.

### Mitigation
- Restart orchestrator worker.
- Throttle retries if upstream provider is unstable.
- Ask users to retry task from latest persisted project state.

## 2) Approval/Decision Flow Breakage

### Symptoms
- Tool approval cards do not resolve.
- Decision widgets appear but submission fails.

### Immediate Actions
- Confirm `contract_version` is present in `ask_user` payloads.
- Validate `/chat/{project_id}/permission` is returning `200` and not `409`.
- Check audit events for `permission_request_emitted` and `permission_response_recorded`.

### Mitigation
- Roll back to last known compatible frontend build if contract mismatch is widespread.
- Temporarily disable optional decision flows and use plain confirmation prompts.

## 3) Duplicate Step/Artifact Records

### Symptoms
- Timeline shows repeated artifacts or duplicate step entries.

### Immediate Actions
- Confirm sender includes `idempotency_key`.
- Verify core API dedupe path in `/chat/steps` and `/chat/artifacts`.

### Mitigation
- Reprocess affected tasks using latest records only.
- Add one-time cleanup query for duplicate display entries in UI if needed.

## 4) Auth/Internal Key Failures

### Symptoms
- Orchestrator cannot call core API.
- Sudden rise in `401`/`503` between services.

### Immediate Actions
- Validate `CORE_API_INTERNAL_KEY` and `INTERNAL_API_KEY` configuration.
- Confirm environment classification (`APP_ENV`) is correct.

### Mitigation
- Rotate internal keys and redeploy both services.
- Verify cookie auth + bearer propagation paths with request IDs.
