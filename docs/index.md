# genro-toolchain

Standalone build tools for [Genropy](https://github.com/genropy/genropy)
applications. **No Genropy installation needed**: only Python ≥ 3.11
(standard library only), `git` and `docker`.

The first tool is **dockerize**, a drop-in replacement for
`gnr app dockerize`. It lets a CI pipeline build the Docker image of a
Genropy application without installing Genropy first.

```bash
pip install git+https://github.com/genropy/genro-toolchain
cd myproject                 # the folder containing instances/
gnr-dockerize myapp -t 1.4.0 --push -u myorg
```

```{toctree}
:maxdepth: 2
:caption: User guide

installation
quickstart
dockerize
configuration
image
ci
upstream-differences
```

```{toctree}
:maxdepth: 1
:caption: Project

development
```
