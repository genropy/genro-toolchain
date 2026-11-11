# The dockerize command

```text
gnr-dockerize [options] INSTANCE
genro-toolchain dockerize [options] INSTANCE
```

Builds a Docker image for a Genropy instance. It accepts the same options as
`gnr app dockerize`, plus a few CI-oriented ones.

## What it does

1. **Finds the instance** folder (see [Instance lookup](#instance-lookup)).
2. **Reads** `config/build.json` and `config/apt-dependencies.txt` from it
   (see [Configuration files](configuration.md)).
3. **Prepares a build context** in a temporary folder inside the current
   directory:
   - the instance repository, exported from the committed `HEAD` of the local
     checkout with `git archive`;
   - every repository listed in `build.json`, cloned at its
     `branch_or_commit` (the `.git` folder is removed);
   - `gunicorn.py`, `supervisord.conf` and the `Dockerfile`.
4. **Runs** `docker build`, producing the local image `NAME:TAG`.
5. With `--push`, **tags and pushes** it as `REGISTRY/USERNAME/NAME:TAG`.
6. With `--compose`, **writes** `INSTANCE-compose.yml` in the current folder.

The temporary build folder is removed at the end, unless `--keep-temp` is
given. Any failure (missing repository, failed clone, failed build) stops the
command with exit status 1.

## The INSTANCE argument

`INSTANCE` is either:

- a **path** to the instance folder, such as `instances/myapp` or
  `/src/myproject/instances/myapp`; or
- an instance **name**, such as `myapp`, looked up as described below.

(instance-lookup)=
### Instance lookup

A name is searched in this order; the first existing folder wins:

1. `PROJECT_DIR/instances/NAME`
2. `PROJECT_DIR/*/instances/NAME`
3. `$GNR_LOCAL_PROJECTS/*/instances/NAME`, when the variable is set
4. `NAME` inside every `instances` path declared in
   `$GENRO_GNRFOLDER/environment.xml` (default `~/.gnr/environment.xml`)
5. `*/instances/NAME` inside every `projects` path declared in the same file

`PROJECT_DIR` is `--project-dir`, or the current directory. Steps 4 and 5 use
the same file Genropy reads, so on a developer machine a name resolves the way
`gnr` resolves it. In CI, steps 1–2 are usually all you need.

The instance folder must be inside a git working tree.

## Options

### Options shared with `gnr app dockerize`

`-t TAG`, `--tag TAG`
: Image version tag. Default: `latest`.

`-n NAME`, `--name NAME`
: Image name. Default: the instance name.

`-p`, `--push`
: After the build, tag the image as `REGISTRY/USERNAME/NAME:TAG` and push
  it. You must be logged in to the registry (`docker login`).

`-r REGISTRY`, `--registry REGISTRY`
: Registry to push to. Default: `ghcr.io`.

`-u USERNAME`, `--username USERNAME`
: Registry namespace (user or organization) to push to.
  Default: `softwellsrl`.

`-a PLATFORM`, `--arch PLATFORM`, `--platform PLATFORM`
: Target platform passed to `docker build --platform`.
  Default: `linux/amd64`.

`--progress {auto,plain,tty,quiet,rawjson}`
: Docker build progress output. Default: `auto`. Use `plain` in CI logs.

`--bleeding`
: Build on `ghcr.io/genropy/genropy:develop` instead of `:latest`.

`--no-pull`
: Do not pull the base image (passes `--pull=false` to `docker build`).

`--keep-temp`
: Keep the temporary build folder, for debugging. Its path is printed.

`-c`, `--compose`
: Also write `INSTANCE-compose.yml` with PostgreSQL and the application.
  See [The compose file](image.md#the-compose-file).

`-f FQDN`, `--fqdn FQDN`
: Host name the application is served on. Repeat for several names. Adds
  Traefik routing labels to the compose file.

`--router {traefik}`
: Router the compose labels are written for. Only `traefik` is supported.

`--build-gen`
: **Ignored**, with a warning. Generating `build.json` needs Genropy; see
  [Configuration files](configuration.md#generating-buildjson).

`--mako`
: **Ignored**, with a warning. There is a single compose generator.

### genro-toolchain options

`--project-dir DIR`
: Where to look up the instance by name. Default: the current directory.

`--context-only DIR`
: Write the build context (sources, configuration files and `Dockerfile`)
  to `DIR` and stop: no build, no push. `DIR` must be missing or empty. The
  `docker build` command to run is printed. Docker is not needed. Cannot be
  combined with `--push`.

`--base-image IMAGE`
: Use `IMAGE` as the base image instead of
  `ghcr.io/genropy/genropy:latest` (or `:develop` with `--bleeding`).

`--clone-main`
: Clone the instance repository from its `origin` remote, at the
  `branch_or_commit` given in `build.json`, instead of exporting the local
  checkout. This is how `gnr app dockerize` works.

`--loglevel {debug,info,warning,error}`
: Log level. Default: `info`.

`--version`
: Print the version and exit.

## Examples

Build from the project folder:

```bash
gnr-dockerize myapp -t 1.4.0
```

Build an instance given by path, with a custom image name, and push it to
Docker Hub:

```bash
gnr-dockerize ~/src/myproject/instances/myapp -n myapp-web -t 1.4.0 \
    --push -r docker.io -u myorg
```

Build for ARM:

```bash
gnr-dockerize myapp -t 1.4.0 --platform linux/arm64
```

Generate a compose file served on two host names:

```bash
gnr-dockerize myapp -t 1.4.0 -c -f myapp.example.com -f www.myapp.example.com
```

Only prepare the build context, then build it yourself:

```bash
gnr-dockerize myapp --context-only build/ctx
docker buildx build --platform linux/amd64,linux/arm64 -t myorg/myapp:1.4.0 build/ctx
```

Inspect what would go into the image:

```bash
gnr-dockerize myapp --context-only /tmp/ctx --loglevel debug
cat /tmp/ctx/Dockerfile
```

## Exit status

| Status | Meaning |
| --- | --- |
| `0` | Success |
| `1` | Error (instance not found, invalid `build.json`, failed clone, failed `docker build` or `docker push`, ...). The message is printed without a traceback. |
| `2` | Invalid command line options |
| `130` | Interrupted with Ctrl-C |
