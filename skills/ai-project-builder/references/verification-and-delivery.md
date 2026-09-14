# Verification and delivery

Use this reference before stating that a feature or project is complete.

## Evidence ladder

Run the strongest applicable checks, keeping the layers distinct:

1. static checks: formatting, types, compile, dependency locks, migrations, secret scan;
2. unit tests: business rules, calculations, schemas, permissions, state machines;
3. integration tests: API, database, queue, storage, retries, idempotency, provider adapter;
4. live-provider smoke tests: one successful, billable call per required modality plus a controlled failure case where safe;
5. end-to-end browser tests: navigate from the real upstream action to the persisted visible result;
6. target-like runtime: process/container health, ports, persistence, logs, restart behavior, and public access if in scope.

A lower layer cannot substitute for a higher requested layer. Do not equate a compiled frontend with a working screen, a 200 API response with a correct user journey, or a Mock provider with live AI.

## Acceptance matrix

For each requirement record:

| Requirement | Scenario | Preconditions | Action | Expected state/result | Test layer | Evidence | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |

Include happy paths, role violations, invalid inputs, empty states, provider errors, timeout/retry, duplicate submission, refresh/reload, and cross-entity isolation where applicable.

For generated media, record task ID, provider mode, terminal state, stable application URL, HTTP status, media type, size, and browser preview/playback result. For approval, prove `draft -> submitted -> approved/rejected` through actual UI or API actions by the correct roles.

## Repair loop

When a check fails:

1. preserve the failure evidence;
2. diagnose the failing layer and root cause;
3. implement the smallest coherent repair;
4. rerun the failing test and related regression set;
5. update requirement status and documentation.

Do not suppress errors, weaken assertions, or mark a feature complete because the demo can avoid the broken path.

## Handoff package

Provide:

- requirements, architecture, and meaningful decisions;
- source and migration changes;
- sample/import data with initialization commands;
- environment variables documented with placeholders only;
- exact install, start, stop, restart, update, backup, and rollback commands;
- test summary with counts and named unverified items;
- public/local access paths and demo account lookup location;
- screenshots or recordings for critical journeys;
- cost and safety warnings for live model actions;
- current commit/version and known limitations.

Before delivery, verify that the repository is in the intended state and that documentation matches the deployed behavior.
