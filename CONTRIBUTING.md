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


## Release verification ordering

`tools/verify_public_release.py` verifies the physical release tree and therefore
must run on a pristine checkout **before** any in-place package build or install.
`pip install .`, wheel builds, and editable installs may create `build/`, `dist/`,
`*.egg-info`, or cache material; those artifacts are intentionally rejected by the
release verifier even when ignored by Git. Package/install qualification must use
a throwaway source copy or temporary build directory rather than weakening the
release census.
