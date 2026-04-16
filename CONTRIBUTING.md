# Contributing

Thanks for contributing to Vision OS.

## Workflow

1. Create an issue or confirm the work is already tracked.
2. Branch from `main` using `feat/...`, `fix/...`, `docs/...`, or `chore/...`.
3. Keep changes small and focused.
4. Run `pytest` before opening a pull request.
5. Open a PR with a clear summary and verification notes.

## Local Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

## Standards

- Prefer clear module boundaries over clever abstractions.
- Add tests when logic changes.
- Keep UI rendering separate from perception and reasoning.
- Document assumptions in the PR description.

