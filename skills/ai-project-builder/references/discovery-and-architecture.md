# Discovery and architecture

Use this reference after workspace inspection and during the Grill Me phase.

## Build the requirement baseline

Capture each requirement with a stable identifier, user/role, trigger, inputs, business rules, expected output, failure behavior, persistence needs, permissions, acceptance steps, and evidence source. Separate:

- confirmed requirements from assumptions and recommendations;
- first-release scope from later extensions;
- real integrations from simulations and placeholders;
- business acceptance from implementation choices.

For ambiguous or conflicting sources, quote the conflict briefly, explain its architectural effect, and obtain a decision. Prefer measurable definitions such as P95 latency, maximum cost per run, minimum output count, supported formats, and exact success/failure states.

## Architecture trace

For every primary journey, trace this chain:

`user action -> UI state -> API contract -> authorization -> domain transition -> persistent record -> queue/job -> provider -> artifact/result -> visible UI -> audit/observability`

Any missing link is a design gap. Record ownership of calculations and transitions; models may propose or explain, while deterministic code must validate and commit facts.

Choose technology based on current scale, team capability, deployment environment, model latency, data consistency, and recovery needs. Avoid microservices, vector databases, agents, or orchestration frameworks unless the verified use case benefits from them.

## Required design outputs

- context and component architecture;
- modules and ownership boundaries;
- core data model and state machines;
- API/event contracts and error model;
- AI gateway, prompts, structured schemas, model selection, evaluation, and fallback rules;
- asynchronous execution, idempotency, retries, timeouts, cancellation, and reconciliation;
- authentication, role authorization, secrets, untrusted-input handling, and network exposure;
- deployment topology, configuration, persistence, observability, backup, migration, and rollback;
- requirement-to-component and requirement-to-test traceability.

Keep a small architecture decision record for decisions that are costly to reverse.
