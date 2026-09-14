# Implementation and AI integration

Use this reference when implementation begins or when an existing project must be made genuinely runnable.

## Vertical-slice order

Prefer a thin end-to-end foundation before breadth:

1. reproducible environment, configuration, migrations, health checks, and demo accounts;
2. one real business entity and complete CRUD journey;
3. one AI request with saved input snapshot, task state, validated output, and visible result;
4. background execution and recovery for long-running work;
5. approval or human review with a real upstream submission and audit trail;
6. representative import/sample data and remaining journeys;
7. target deployment and operational controls.

Do not create disconnected pages in parallel if their backing state transitions do not yet exist.

## Provider integration contract

Put model access behind a provider gateway. Store provider, model, mode, prompt/schema version, request correlation ID, timing, usage/cost when available, external job ID, and structured error category. Do not store or log raw secrets.

For each modality:

- verify the provider's exact endpoint and model availability with a minimal authorized request;
- validate inputs before billing work is submitted;
- distinguish `mock`, `live`, and fallback results in storage and UI;
- validate structured text against a schema and limit repair attempts;
- download media, verify status/MIME/size, persist it under application ownership, and serve it from a stable authorized URL;
- model asynchronous work with observable states such as pending, running, succeeded, failed, timeout, and cancelled;
- handle an unknown submit result without blindly resubmitting a potentially billable job;
- prevent stale or duplicate attempts from overwriting the active result.

## UI and data integrity

Each asynchronous task needs status, timestamps, actionable errors, retry rules, and an obvious path to its result. Refresh or polling must stop at a terminal state.

Seed data must cover multiple brands/categories/states and make visual comparison possible. Use unique stable identifiers and keep initialization idempotent. Avoid claiming diversity by changing only display names while reusing identical media and metrics.

Enforce permissions and state transitions in the backend. UI capability checks improve usability but are not authorization.

## Change discipline

Inspect existing tests, configuration, dirty Git state, and neighboring behavior before editing. Preserve user changes, update docs and examples with code, keep lockfiles reproducible, and run the narrowest fast checks continuously. Commit secrets and generated runtime data to neither source nor release bundles.
