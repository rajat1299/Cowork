# Cowork Production Readiness

## SLO Targets

- Desktop task start success rate: `>= 99.9%`
- Orchestrator chat availability: `>= 99.9%`
- Orchestrator chat p95 latency: `<= 6000ms`
- Core API availability: `>= 99.9%`
- Core API p95 latency: `<= 500ms`
- Monthly error budget: `0.1%`

## Release Gates

1. **Safety Gate**
   - Tool approval contract version is present on `ask_user`, `decision`, and `compose_message` events.
   - Audit log events are emitted for request + response paths.
2. **Reliability Gate**
   - Retry policy active for cross-service HTTP calls.
   - Step/artifact ingestion is idempotent for repeated event keys.
3. **Quality Gate**
   - Backend unit tests pass for approval flow and idempotency.
   - Frontend typecheck/lint pass for SSE contract handling.
4. **Operations Gate**
   - `/health/ready` returns `ok` in deployed environment.
   - Request IDs propagate through frontend -> orchestrator -> core_api.

## Deployment Checklist

- Configure `APP_ENV` for each service.
- Set non-default `JWT_SECRET` in all non-dev environments.
- Set `CORE_API_INTERNAL_KEY` and `INTERNAL_API_KEY` outside development/test/desktop.
- Validate `/health` and `/health/ready` for orchestrator and core API.
- Run smoke flow: start task -> approval prompt -> decision -> artifact persistence.
