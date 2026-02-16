# ADR-0011: Make `app/` the Project-of-Record CLI

**Status:** Accepted
**Date:** 2026-02-15

## Context

This repository contains multiple Python libraries under `src/` (for example,
`catalog`, `ontology`, `agentlayer`, and `advanced_alchemy`) plus an
application package under `app/`.

We need one user-facing product entrypoint for the Substrate project. Today,
library and application concerns are mixed in packaging expectations, which
creates ambiguity about:

- what end users should install and run,
- where the canonical CLI lives,
- how internal libraries are consumed by the product.

Because this is pre-alpha, we can make a clean breaking change and standardize
on one packaging model without compatibility shims.

## Decision

- Treat `app/` as the product-of-record Python application for this repository.
- Keep library code in `src/<library_name>` as internal modular dependencies of
  the product.
- Keep the canonical CLI entrypoint in `app`, exposed via:
  - `substrate = "app.cli.main:main"`
- In `pyproject.toml`:
  - Set project metadata to represent the application product.
  - Declare internal libraries as normal dependencies by package name.
  - Resolve those internal dependencies through local editable source mappings
    in `[tool.uv.sources]`.
  - Build/publish package contents that include `app` plus required local
    libraries needed by this repository.
- Continue enforcing modular boundaries: libraries remain independently testable
  and reusable, while `app` is the integration and user interface layer.

## Consequences

- Users get one clear install/run surface (`substrate` CLI).
- Product behavior is centralized in `app`, reducing ambiguity across modules.
- Internal libraries keep clean boundaries and can still be developed and tested
  independently.
- Packaging configuration becomes explicit: app is primary; `src/*` libraries
  are dependencies.
- This is a deliberate breaking change in repository conventions, acceptable for
  pre-alpha, and avoids migration/fallback complexity.
