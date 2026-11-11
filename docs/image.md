# The generated image

## Base image

`ghcr.io/genropy/genropy:latest`, or `:develop` with `--bleeding`, or any
image given with `--base-image`. The base image provides Genropy, gunicorn and
supervisord, and a `genro` user.

## Layout

All sources go under `/home/genro/genropy_projects/`, one folder per
repository:

```text
/home/genro/
├── genropy_projects/
│   ├── myproject/              <- instance repository
│   │   └── instances/myapp/site/
│   └── erpy/                   <- dependencies from build.json
├── site -> genropy_projects/myproject/instances/myapp/site
└── gunicorn.py
/etc/supervisor/conf.d/myapp-supervisor.conf
```

Files are owned by `genro`, and the container runs as `genro`.

## Build steps

The `Dockerfile` does, in order:

1. Installs the packages from `apt-dependencies.txt`, if any.
2. Copies each repository.
3. Links `/home/genro/site` to the instance's `site` folder.
4. Copies the gunicorn and supervisord configuration.
5. Runs `gnr app checkdep -n -i INSTANCE`, so the build fails if a Python
   dependency of the application is missing.
6. Sets the image labels.

To see the exact `Dockerfile`, use `--context-only DIR` or `--keep-temp`.

## Runtime

The container starts with:

```text
gnr db migrate -u INSTANCE && /usr/bin/supervisord
```

supervisord then runs:

| Program | Command |
| --- | --- |
| `dbsetup` | `gnr db migrate -u INSTANCE` |
| `httpserver` | `gnr web serveprod INSTANCE` with gunicorn on port **8888** |
| `gnrasync` | `gnr app async` on port **9999** (websockets) |
| `gnrtaskscheduler` | `gnr web taskscheduler INSTANCE` |
| `gnrtaskworker` | `gnr web taskworker INSTANCE` |

Gunicorn uses one worker per available CPU (it reads the container's cgroup
CPU limit) with 8 threads each, and a 30-minute request timeout. All output
goes to the container's stdout/stderr.

The database connection is configured with environment variables such as
`GNR_DB_IMPLEMENTATION`, `GNR_DB_HOST`, `GNR_DB_PORT`, `GNR_DB_USER`,
`GNR_DB_PASSWORD` and `GNR_ROOTPWD`; see the compose file below for an
example.

These files are the same as those of `gnr app dockerize`, so images built by
either tool behave the same.

## Labels

Every image carries these labels:

| Label | Value |
| --- | --- |
| `org.opencontainers.image.title`, `org.label-schema.name` | Instance name |
| `org.opencontainers.image.description` | `Genropy application - instance NAME` |
| `org.opencontainers.image.created`, `org.label-schema.build-date`, `gnr_app_dockerize_on` | Build time (UTC) |
| `org.opencontainers.image.source`, `org.label-schema.vcs-url` | URL of the instance repository (empty without an `origin` remote) |
| `org.opencontainers.image.revision` | Commit of the instance repository |
| `org.opencontainers.image.version` | The `--tag` value |
| `git:REPO` | For each repository: `@COMMIT`, or `REF@COMMIT` when built from a branch or tag |
| `git:REPO:url` | For each repository: web link to the commit |

URLs in labels never contain credentials, even when git is configured to
inject a token (see [Using it in CI](ci.md)).

Read them with:

```bash
docker inspect --format '{{json .Config.Labels}}' myapp:1.4.0
```

## The compose file

With `-c`, `dockerize` writes `INSTANCE-compose.yml` in the current folder.
It defines:

- `INSTANCE_db`: `postgres:latest`, with a health check;
- `INSTANCE`: the image just built, on port 8888, started once the database is
  healthy, with the `site` folder in the `INSTANCE_site` volume.

Database settings can be overridden with environment variables
(`GNR_DB_HOST`, `GNR_DB_USER`, `GNR_DB_PORT`, `GNR_DB_PASSWORD`,
`GNR_ROOTPWD`). The defaults are meant for a local test only: change the
passwords before using the file anywhere else.

With one or more `-f FQDN`, the application service also gets Traefik labels
routing `Host(FQDN)` to port 8888 and `Host(FQDN) && Path(/websocket)` to
port 9999. Traefik itself is not part of the file.
