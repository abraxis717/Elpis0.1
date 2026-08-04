# Contributing

## Development workflow

1. Fork the repository
2. Create a feature branch
3. Make changes with tests
4. Run `python tools/verify_public_release.py`
5. Submit a pull request

## Code standards

- Python: type hints where applicable, docstrings on public APIs
- C/C++: C11/C++17, no external dependencies beyond standard library
- Tests: every public function must have a test
- Determinism: all structural operations must be reproducible across processes

## Testing

Run the full test suite before submitting:

```bash
python tools/verify_public_release.py
```

## Qualification

New components must pass the same qualification gates as existing ones:
- Direct test suite passes
- Negative cases covered
- Fresh-process determinism verified
- Consumer compatibility validated (where applicable)
