# Development

## Setup

```bash
git clone https://github.com/genropy/genro-toolchain
cd genro-toolchain
python -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
```

## Checks

```bash
.venv/bin/pytest
.venv/bin/ruff check src tests
.venv/bin/ruff format --check src tests
```

Tests build real git repositories in a temporary folder; Docker is mocked, so
it is not needed to run them.

## Rules

- **Standard library only** at runtime. The tool must install in a bare CI
  runner. Test and documentation tools go in the optional dependencies.
- Keep the generated `Dockerfile`, the gunicorn and supervisord templates and
  the command line options compatible with `gnr app dockerize` (upstream:
  `gnrpy/gnr/app/cli/gnrdockerize.py` in genropy). Document every intentional
  difference in [Differences from gnr app dockerize](upstream-differences.md)
  and in the README.
- Never put credentials into image labels.

## Source layout

| Module | Role |
| --- | --- |
| `cli.py` | Command line entry points |
| `instance.py` | Instance lookup (path, project folder, `~/.gnr/environment.xml`) |
| `buildconfig.py` | Reading `config/build.json` and `config/apt-dependencies.txt` |
| `git.py` | Wrappers around the git command line |
| `dockerize/builder.py` | Build context, `Dockerfile`, docker build and push |
| `dockerize/templates.py` | gunicorn and supervisord configuration, labels |
| `dockerize/compose.py` | Compose file |

## Documentation

The documentation is written in Markdown (MyST) and built with Sphinx.
To build it locally:

```bash
.venv/bin/pip install -e '.[docs]'
.venv/bin/sphinx-build -W -b html docs docs/_build/html
```

Then open `docs/_build/html/index.html`.
