# Using it in CI

`dockerize` is designed for CI runners: it installs with `pip` in seconds and
needs only `git` and `docker`, which most runners already have.

## Access to private dependencies

The repositories in `build.json` are cloned with plain `git`, using whatever
credentials git has. They usually have SSH URLs
(`git@github.com:org/repo.git`). In CI, the simplest approach is to rewrite
them to HTTPS with a token that can read those repositories:

```bash
git config --global url."https://x-access-token:${TOKEN}@github.com/".insteadOf "git@github.com:"
```

The token is used for cloning only: image labels are built from the URLs as
written in `build.json` and in the checkout's configuration, with any
credentials removed.

The instance repository itself needs no credentials: it is exported from the
checkout the CI job already has.

## GitHub Actions

Build and push to the GitHub Container Registry on every tag:

```yaml
name: image

on:
  push:
    tags: ["v*"]

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
      - run: >
          gnr-dockerize myapp
          -t ${{ github.ref_name }}
          --push -u ${{ github.repository_owner }}
          --progress plain
```

`DEPS_TOKEN` is a repository secret holding a token (for example a
fine-grained personal access token) with read access to the dependency
repositories. `GITHUB_TOKEN` cannot read other private repositories.

### With docker/build-push-action

To use Buildx features (layer cache, multi-platform images), let `dockerize`
prepare the context and hand it to the official action:

```yaml
      - run: gnr-dockerize myapp --context-only ctx
      - uses: docker/setup-qemu-action@v3
      - uses: docker/setup-buildx-action@v3
      - uses: docker/build-push-action@v6
        with:
          context: ctx
          platforms: linux/amd64,linux/arm64
          push: true
          tags: ghcr.io/${{ github.repository_owner }}/myapp:${{ github.ref_name }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

Note that `org.opencontainers.image.version` is taken from `-t`, so pass the
same tag to `--context-only` if you rely on that label:

```bash
gnr-dockerize myapp -t "$TAG" --context-only ctx
```

## Other CI systems

The steps are the same everywhere:

1. Check out the project repository.
2. `pip install git+https://github.com/genropy/genro-toolchain`
3. Give git read access to the dependency repositories.
4. `docker login` to the target registry.
5. `gnr-dockerize INSTANCE -t TAG --push -r REGISTRY -u NAMESPACE --progress plain`

## Tips

- Commit before building: only the committed `HEAD` goes into the image. A
  CI checkout is always clean, so this matters mostly on developer machines.
- Shallow clones (the `actions/checkout` default) are fine.
- Use `--progress plain` to get readable build logs.
- Use `--context-only` plus `cat ctx/Dockerfile` to debug what goes into the
  image without building it.
