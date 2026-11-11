# Quick start

This page builds an image for an instance called `myapp` that lives in a
project repository like this:

```text
myproject/                  <- git repository
├── packages/
│   └── ...
└── instances/
    └── myapp/
        ├── instanceconfig.xml
        ├── config/
        │   ├── build.json             (optional, recommended)
        │   └── apt-dependencies.txt   (optional)
        └── site/
```

## 1. Describe the dependencies

`config/build.json` lists the other git repositories the application needs
(for example shared Genropy packages). It uses the same format as
`gnr app dockerize`:

```json
{
  "dependencies": {
    "git_repositories": {
      "erpy": {
        "url": "git@github.com:myorg/erpy.git",
        "branch_or_commit": "develop",
        "subfolder": null,
        "description": "erpy"
      }
    }
  }
}
```

If you already have Genropy installed somewhere, you can generate it once with
`gnr app dockerize --build-gen` and commit it. See
[Configuration files](configuration.md) for all the fields.

## 2. Commit

The instance repository is taken from the **committed** `HEAD` of your local
checkout. Uncommitted changes are not included (you get a warning).

## 3. Build

From the project folder:

```bash
cd myproject
gnr-dockerize myapp -t 1.4.0
```

This builds the local image `myapp:1.4.0`.

## 4. Push

```bash
docker login ghcr.io
gnr-dockerize myapp -t 1.4.0 --push -u myorg
```

The image is tagged and pushed as `ghcr.io/myorg/myapp:1.4.0`.

## 5. Try it locally

Add `-c` to get a compose file with a PostgreSQL service next to the
application:

```bash
gnr-dockerize myapp -t 1.4.0 -c
docker compose -f myapp-compose.yml up
```

The application answers on <http://localhost:8888>.

## Next steps

- [The dockerize command](dockerize.md): every option.
- [Using it in CI](ci.md): GitHub Actions examples.
