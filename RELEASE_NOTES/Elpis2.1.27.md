# Elpis2.1.27

## Version: v2.1.27

Elpis2.1.27 is a bounded maintenance successor to the published Elpis2.1.26 repository-identity release.

## Python AST policy repairs

The canonical `python.ast.v1` policy now:

- admits a typed `except` handler only when its type is one of the already admitted `_EXCEPTION_NAMES`;
- rejects bare and non-admitted handlers while preserving the existing external `BANNED_CALL` decision code;
- requires the requested entrypoint to be a module-top-level function rather than accepting a nested definition discovered by `ast.walk`.

These changes repair static-policy admission behavior. They do not convert the AST policy into an execution sandbox and do not grant generated-source execution authority.

## Regression integrity

The canonical-promotion planner immutability regression now asserts the exact `dataclasses.FrozenInstanceError` instead of swallowing its own `assert False`.

A new authority-scope regression records the intentional distinction between:

- whole Elpis learned/reference runtime admission; and
- component-level `runtime_admission` in `manifests/PUBLIC_COMPONENT_REGISTRY.json`.

The latter remains false for the public component registry and must not be inferred from the former.

## PyPI Trusted Publishing

The repository now carries `.github/workflows/pypi-publish.yaml`, matching the PyPI Trusted Publisher identity for:

- repository `abraxis717/Elpis`;
- workflow `pypi-publish.yaml`;
- environment `pypi`.

The publishing job receives only `id-token: write` and uses PyPA's Trusted Publishing action. No long-lived PyPI API token is embedded in repository configuration.

## Preserved authority

This release does not broaden:

- model or TRM authority;
- terminal execution authority;
- public-component runtime admission;
- ECS scope;
- Grid81 Publisher R1 mechanics;
- StreamingRegexIngress/RegexHACF V2 mechanics;
- closed Branch35–40 scientific evidence.

The DurableApplicationLedger historical entry hash remains schema v1. Any design that binds `artifact_digest` into the entry hash is deferred to an explicit schema-v2 successor rather than silently reinterpreting persisted heads.

`PUBLISHED_RELEASES.json` remains unchanged in the pre-tag candidate. Publication-registry materialization remains a separate post-tag step.
