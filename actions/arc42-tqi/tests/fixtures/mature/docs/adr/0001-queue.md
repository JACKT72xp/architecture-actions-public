---
id: ADR-0001
title: Use a durable order queue
status: accepted
arc42_sections: [5, 9, 11]
supersedes: []
superseded_by: null
related: []
---
# ADR-0001: Use a durable order queue

## Context

Warehouse outages must not prevent order acceptance or lose accepted work.

## Decision

Use a durable queue between the Orders API and Worker.

## Alternatives

Synchronous warehouse submission was rejected because outages would propagate to customers.
A shared database polling design was rejected because it couples the component schemas.

## Positive Consequences

Independent deployments become possible.

## Negative Consequences

Eventual fulfillment requires idempotent consumers, retry budgets, queue monitoring, and operator recovery procedures.

## Quality Attributes

Availability, recoverability, maintainability, and eventual consistency.
