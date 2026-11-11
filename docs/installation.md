# Installation

## Requirements

- Python 3.11 or newer. The tool uses the standard library only, so it
  installs in a bare CI runner in a few seconds.
- `git` on the `PATH`. It is used to export the instance repository and to
  clone the dependencies.
- `docker` on the `PATH`, only when you build or push the image. Preparing the
  build context with `--context-only` does not need Docker.

Genropy itself is **not** required.

## Install with pip

```bash
pip install git+https://github.com/genropy/genro-toolchain
```

To pin a version, add a tag, branch or commit after `@`:

```bash
pip install "git+https://github.com/genropy/genro-toolchain@<tag-or-commit>"
```

`pipx` works too, and keeps the tool out of your project environment:

```bash
pipx install git+https://github.com/genropy/genro-toolchain
```

## Commands

The package installs two equivalent entry points:

| Command | Notes |
| --- | --- |
| `genro-toolchain dockerize ...` | Main command; future tools will be added as sub-commands |
| `gnr-dockerize ...` | Shortcut for `genro-toolchain dockerize` |

`python -m genro_toolchain dockerize ...` also works.

Check the installation:

```bash
genro-toolchain --version
gnr-dockerize --help
```
