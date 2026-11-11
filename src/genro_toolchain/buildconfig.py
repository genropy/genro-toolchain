"""Read an instance's ``config/build.json`` and ``config/apt-dependencies.txt``.

``build.json`` has the format written by ``gnr app dockerize --build-gen``::

    {
      "dependencies": {
        "git_repositories": {
          "erpy": {"url": "git@github.com:org/erpy.git",
                   "branch_or_commit": "develop",
                   "subfolder": null,
                   "description": "erpy"}
        },
        "docker_images": [...]
      }
    }
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from genro_toolchain import ToolchainError
from genro_toolchain.git import normalize_url, repo_name_from_url
from genro_toolchain.instance import Instance

logger = logging.getLogger(__name__)

BUILD_FILE_NAME = "build.json"
APT_FILE_NAME = "apt-dependencies.txt"


@dataclass
class Repository:
    url: str
    ref: str = "master"
    subfolder: str | None = None
    description: str = "No description"
    # Set for the repository holding the instance itself.
    is_main: bool = False

    @property
    def name(self) -> str:
        return repo_name_from_url(self.url)

    @property
    def key(self) -> str:
        return normalize_url(self.url)


def load_build_config(instance: Instance) -> dict | None:
    """The parsed build.json, or None when the instance has none."""
    path = instance.config_dir / BUILD_FILE_NAME
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as fp:
            config = json.load(fp)
    except json.JSONDecodeError as exc:
        raise ToolchainError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(config, dict):
        raise ToolchainError(f"{path} must contain a JSON object")
    logger.info("Found build configuration %s", path)
    return config


def dependency_repositories(config: dict | None) -> list[Repository]:
    """Git repositories declared in build.json, in file order, deduplicated by URL."""
    repos: dict[str, Repository] = {}
    git_config = ((config or {}).get("dependencies") or {}).get("git_repositories") or {}
    for label, conf in git_config.items():
        url = conf.get("url")
        if not url:
            raise ToolchainError(f"build.json: repository '{label}' has no url")
        repo = Repository(
            url=url,
            ref=conf.get("branch_or_commit") or "master",
            subfolder=conf.get("subfolder") or None,
            description=conf.get("description") or "No description",
        )
        repos[repo.key] = repo
    return list(repos.values())


def docker_images(config: dict | None) -> list[dict]:
    """``dependencies.docker_images`` entries (kept for parity; not used in the build)."""
    images = ((config or {}).get("dependencies") or {}).get("docker_images") or []
    return [
        {
            "name": image.get("name"),
            "tag": image.get("tag"),
            "description": image.get("description", "No description"),
        }
        for image in images
    ]


def apt_dependencies(instance: Instance) -> list[str]:
    """Debian packages listed one per line in config/apt-dependencies.txt."""
    path = instance.config_dir / APT_FILE_NAME
    if not path.is_file():
        return []
    packages = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if line:
            packages.extend(line.split())
    return packages
