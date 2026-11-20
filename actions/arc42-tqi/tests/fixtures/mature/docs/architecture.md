# Order platform architecture

## 1. Introduction and Goals

The order platform accepts customer orders, validates their contents, and schedules fulfillment. Its stakeholders are customers, warehouse operators, and the support team. Reliable submission and a transparent recovery process take precedence over immediate fulfillment. The design applies to the production order domain.

## 2. Architecture Constraints

Customer information remains in the designated European region. The platform must use the organization identity provider and preserve an auditable record of every order transition. Application teams own their interfaces, while the platform team owns deployment infrastructure and security policy enforcement.

## 3. Context and Scope

The storefront calls the order API. The API stores validated order envelopes in a durable queue for a fulfillment worker. The warehouse is an external business actor, not a library dependency. Identity verification is supplied by the organizational access boundary.

include::parts/04-solution.adoc[]

## 5. Building Block View

The Orders API owns input validation and the public submission interface. The Worker owns warehouse translation and fulfillment retries. The API must not import worker implementation packages. The durable queue provides the only production communication boundary between these components. Ownership of shared schemas belongs to the order domain team, which publishes backward compatible contracts and migration guidance before changing message fields.

See the [runtime diagram](diagrams/runtime.mmd) and [queue decision](adr/0001-queue.md).

## 6. Runtime View

A customer submits an order through the authenticated interface. The API validates the request before publishing an envelope to the orders queue. The worker consumes the envelope, checks its idempotency key, and invokes the warehouse adapter. Successful handling acknowledges the message. Failed handling preserves the message for bounded retries, after which a dead letter queue exposes the failure for operator investigation.

## 7. Deployment View

Both components run in the designated European production environment. The API and worker use distinct service identities with least privilege access to their queue operations. The platform team provisions the queue through reviewed infrastructure definitions. Encryption at rest is mandatory. Deployment promotion validates schema compatibility before shifting traffic. Rollback restores the previous image while preserving pending messages and their idempotency metadata.

## 8. Crosscutting Concepts

The external warehouse integration is a volatility zone. Its adapter contains protocol translation so changes do not propagate into order validation. Business rule changes are isolated inside the API validation policy. Each zone has an owner, an impact statement, and a documented mitigation, with regression evidence tied to the corresponding decision.

```arc42-claims
components:
- id: orders-api
  name: Orders API
  responsibility: Validate orders and publish accepted envelopes.
  boundaries:
  - Public submission interface; no worker implementation imports.
  verification:
    target: src/orders
    property: imports
    operator: not_contains
    expected: src/worker
    method: dependency_graph
  evidence_targets:
  - code
  declared_volatility:
  - business_rules
- id: worker
  name: Worker
  responsibility: Translate order envelopes into warehouse commands.
  boundaries:
  - Queue consumer exposing no synchronous submission API.
  verification:
    target: src/worker/adapter
    property: warehouse_translation
    operator: exists
    expected: null
    method: ast
  evidence_targets:
  - code
  declared_volatility:
  - external_integrations
dependencies:
- id: forbid-worker-import
  source: orders-api
  target: worker
  protocol: Python import
  synchrony: sync
  rationale: Keep independent deployment boundaries.
  allowed: false
  verification:
    target: src/orders
    property: imports
    operator: not_contains
    expected: src/worker
    method: dependency_graph
  evidence_targets:
  - code
flows:
- id: submit-order
  source: orders-api
  target: worker
  protocol: SQS orders queue
  synchrony: async
  rationale: Preserve orders during warehouse outages.
  verification:
    target: src/orders/publisher
    property: queue
    operator: equals
    expected: orders
    method: ast
  evidence_targets:
  - code
  interface: orders queue message schema
cloud_resources:
- id: orders-queue
  provider: aws
  service: sqs
  role: Durable order transport
  component_id: orders-api
  configuration:
    region: eu-west-1
    queue_name: orders
  security:
    encryption_at_rest: true
    public_access: false
  verification:
    target: aws/eu-west-1/sqs/orders
    property: encryption_at_rest
    operator: equals
    expected: true
    method: cloud_inventory
  evidence_targets:
  - cloud
  environment: production
  region: eu-west-1
volatility_zones:
- id: warehouse-protocol
  component_id: worker
  axis: external_integrations
  propagation_risk: Protocol changes could alter every fulfillment path.
  encapsulation: WarehouseAdapter is the only implementation of the outbound warehouse
    port.
  impact: Adapter changes require contract validation but no public submission changes.
  mitigation: Run consumer-driven adapter contract tests before deployment.
  verification:
    target: src/worker/adapter
    property: warehouse_sdk_imports
    operator: exists
    expected: null
    method: ast
  evidence_targets:
  - code
  owner: Order domain team
- id: order-rules
  component_id: orders-api
  axis: business_rules
  propagation_risk: Validation policy changes could reject previously accepted orders.
  encapsulation: Versioned ValidationPolicy hides rules behind the submission interface.
  impact: Policy changes affect validation outcomes without changing worker behavior.
  mitigation: Replay an approved order corpus against each new policy version.
  verification:
    target: src/orders/policy
    property: ValidationPolicy
    operator: exists
    expected: null
    method: ast
  evidence_targets:
  - code
  owner: Order domain team
constraints_and_adrs:
- id: durable-order-decision
  constraint: Accepted orders cross the API boundary through a durable queue.
  adr_id: ADR-0001
  verification:
    target: infrastructure/orders-queue.tf
    property: resource_type
    operator: equals
    expected: aws_sqs_queue
    method: iac
  evidence_targets:
  - code
  status: accepted
  alternatives:
  - name: Synchronous submission
    rejection_reason: Outages propagate to customers.
  consequences:
    positive:
    - Independent deployments.
    negative:
    - Retry complexity.
  quality_attributes:
  - availability
```

## 9. Architecture Decisions

The [accepted queue ADR](adr/0001-queue.md) defines the boundary between acceptance and fulfillment. It records the rejected synchronous alternative and its operational consequences. Owners revisit the decision when delivery latency or recovery targets change. The architecture review process requires an explicit successor before removing this decision from the active baseline, preserving links from impacted building blocks and risks.

## 10. Quality Requirements

During a warehouse outage, previously accepted orders remain recoverable without customer resubmission. The acceptance interface returns within two seconds at the agreed peak load. Duplicate delivery does not produce duplicate warehouse commands. Operators can identify messages that exceed retry limits. Each scenario has a defined stimulus, observable response, and measurement procedure, and the team evaluates these scenarios before promoting a release.

## 11. Risks and Technical Debt

Queue retention exhaustion can lose unprocessed work during a prolonged outage. The operations team monitors message age against the retention threshold and rehearses export recovery monthly. Schema divergence could prevent old workers from consuming new envelopes, so compatibility tests block incompatible deployments. The [queue ADR](adr/0001-queue.md) owns these trade-offs; its owner reviews the mitigation evidence whenever delivery guarantees change.

## 12. Glossary

An envelope is an immutable order message containing an idempotency key and schema version. Acceptance means the platform has durably recorded the intent, while fulfillment means the warehouse has confirmed execution. A port is an interface owned by the domain; an adapter implements its external protocol translation.
