# genro-toolchain

Standalone build tools for Genropy applications that must run **without
Genropy installed** (CI runners). Runtime: Python >= 3.11 standard library
only - never add runtime dependencies (PyYAML is a test-only dependency).

- `src/genro_toolchain/dockerize/` - replacement for `gnr app dockerize`
  (upstream: genropy `gnrpy/gnr/app/cli/gnrdockerize.py`). Keep the generated
  Dockerfile, gunicorn/supervisord templates and CLI flags compatible with
  upstream; document every intentional difference in README.md.
- `instance.py` - instance lookup (path, project dir, ~/.gnr/environment.xml).
- `buildconfig.py` - `config/build.json` and `config/apt-dependencies.txt`.
- `git.py` - git CLI wrappers. Never put credentials into image labels.

Checks: `.venv/bin/pytest`, `.venv/bin/ruff check src tests`,
`.venv/bin/ruff format --check src tests`. Tests build real git repos in
tmp_path (see tests/conftest.py); docker is mocked.
