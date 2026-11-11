# Differences from gnr app dockerize

`dockerize` aims to be a drop-in replacement for `gnr app dockerize`: same
options, same `build.json`, same `Dockerfile` structure, same gunicorn and
supervisord configuration. These are the intentional differences.

## The instance repository comes from the local checkout

`gnr app dockerize` clones the instance repository again from `origin`.
`dockerize` exports the committed `HEAD` of the local checkout with
`git archive` instead.

- No extra credentials or network access are needed for it.
- The image always contains the commit being built, which is what a CI job
  expects.
- Uncommitted changes are **not** included; you get a warning.
- If `build.json` pins the instance repository to another branch or commit,
  you get a warning.

`--clone-main` restores the upstream behaviour.

## build.json is not generated

Generating it needs Genropy to load the application. `--build-gen` is accepted
but ignored with a warning. Without the file the image contains only the
instance repository. See
[Generating build.json](configuration.md#generating-buildjson).

## Errors stop the build

A failed clone or checkout is an error with exit status 1, not a log line
followed by a broken image.

## Other changes

- `apt-dependencies.txt`: `apt-get update` runs before the install, and the
  apt lists are removed afterwards.
- The compose file uses the image name given with `-n` (upstream used the
  instance name).
- The Traefik rules in the compose file no longer have an extra closing
  parenthesis.
- `--mako` is accepted but ignored: there is a single compose generator.
- URLs written into image labels never contain credentials.
- Two more labels: `org.opencontainers.image.revision` and
  `org.opencontainers.image.version`.
- New options: `--project-dir`, `--context-only`, `--base-image`,
  `--clone-main`.
