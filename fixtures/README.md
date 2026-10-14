# Deterministic fixtures

Tests generate small canonical event fixtures from fixed seeds at runtime.
No patient records, manually copied EHR rows, or binary fixture files belong here.
`tests/conftest.py` defines the shared seed. The generator itself is versioned.
