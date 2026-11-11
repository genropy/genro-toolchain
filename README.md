# genro-toolchain

Standalone build tools for [Genropy](https://github.com/genropy/genropy)
applications. **No Genropy installation needed**: only Python ≥ 3.10 (standard
library only), `git` and `docker`.

The first tool is `dockerize`, a drop-in replacement for `gnr app dockerize`,
so a CI pipeline can build an application image without installing Genropy.

Full documentation: [genro-toolchain.readthedocs.io](https://genro-toolchain.readthedocs.io)
(sources in [docs/](docs/)).

## Install

```bash
pip install git+https://github.com/genropy/genro-toolchain
```

This gives two equivalent commands: `genro-toolchain dockerize ...` and the
shortcut `gnr-dockerize ...`.

## Usage

```bash
# from the project folder (the one containing instances/)
gnr-dockerize myapp -t 1.4.0

# or point straight to the instance folder
gnr-dockerize path/to/project/instances/myapp -t 1.4.0 --push -u myorg

# only prepare the build context (Dockerfile + sources), build it yourself
gnr-dockerize myapp --context-only build/ctx
```

All `gnr app dockerize` options are accepted with the same meaning:
`-c/--compose`, `-f/--fqdn`, `-n/--name`, `-p/--push`, `-r/--registry`,
`-a/--arch`, `--progress`, `-t/--tag`, `-u/--username`, `--bleeding`,
`--keep-temp`, `--no-pull`, `--router`. `--build-gen` and `--mako` are accepted
but ignored (see below).

Extra options:

| Option | Meaning |
| --- | --- |
| `--project-dir DIR` | Where to look up the instance by name (default: current folder) |
| `--context-only DIR` | Write the build context to `DIR` and stop (no build, no push) |
| `--base-image IMAGE` | Replace `ghcr.io/genropy/genropy:latest` |
| `--clone-main` | Clone the instance repository from `origin` instead of using the local checkout |
| `--loglevel LEVEL` | `debug`, `info` (default), `warning`, `error` |

### What it reads

From the instance folder:

- `config/build.json`: the git repositories to include, same format as
  `gnr app dockerize`.
- `config/apt-dependencies.txt`: Debian packages to install, one or more per
  line (`#` comments allowed).

The instance is found by path, or by name under `--project-dir`
(`instances/<name>` or `*/instances/<name>`), `$GNR_LOCAL_PROJECTS`, and the
`instances`/`projects` paths in `~/.gnr/environment.xml` when present.

## Differences from `gnr app dockerize`

- **The instance repository comes from the local checkout** (its committed
  `HEAD`, exported with `git archive`) instead of being cloned again from
  `origin`. No extra credentials or network access are needed for it, and the
  image always contains the commit being built. Uncommitted changes are not
  included. If `build.json` pins the instance repository to another commit you
  get a warning; `--clone-main` restores the old behaviour.
- **`build.json` is not generated.** Generating it needs Genropy to load the
  application. Without the file the image contains only the instance
  repository (with a warning). Generate it once with
  `gnr app dockerize --build-gen` and commit it, or write it by hand.
- **Errors stop the build.** A failed clone or checkout is an error, not a log
  line followed by a broken image.
- `apt-dependencies.txt` runs `apt-get update` before installing.
- The compose file uses the image name given with `-n` (it used the instance
  name), and the Traefik rules no longer have an extra closing parenthesis.
- URLs written into image labels never contain credentials.
- Two more labels: `org.opencontainers.image.revision` and
  `org.opencontainers.image.version`.

## In CI (GitHub Actions)

Dependencies listed in `build.json` usually use SSH URLs
(`git@github.com:org/repo.git`). In CI, rewrite them to HTTPS with a token
that can read those repositories:

```yaml
jobs:
  image:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git+https://github.com/genropy/genro-toolchain
      - name: Let git use HTTPS + token for dependencies
        run: |
          git config --global url."https://x-access-token:${{ secrets.DEPS_TOKEN }}@github.com/".insteadOf "git@github.com:"
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}
      - run: gnr-dockerize myapp -t ${{ github.ref_name }} --push -u ${{ github.repository_owner }}
```

To build with `docker/build-push-action` (caching, multi-arch) instead,
run `gnr-dockerize myapp --context-only ctx` and pass `context: ctx` to the
action.

## Development

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test,dev]'
.venv/bin/pytest
.venv/bin/ruff check src tests
```

## License

Apache-2.0. See [NOTICE](NOTICE) for the Genropy code this tool is based on.
