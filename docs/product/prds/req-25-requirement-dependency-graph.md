# REQ-25 — Requirement dependency graph

## User journey

As a delivery planner, I want requirement prerequisites represented as data so work can be ordered and dependency cycles cannot hide in prose.

## Product requirement

Define known dependencies for REQ-23 through REQ-52 and reject duplicate nodes, unknown requirements, self-dependencies, and cycles.

## Acceptance criteria

- Every new requirement appears exactly once.
- Dependencies reference REQ-01 through REQ-52 only.
- The graph is acyclic and validated offline.

## Architecture impact

Adds a directed acyclic dependency layer to architecture traceability.

## Associated tasks

- PROD-25: publish the graph and implement deterministic cycle detection.

## Verification

Run positive graph validation and negative cycle tests in `test_product_operational_contracts.py`.
