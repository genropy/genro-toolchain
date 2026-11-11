"""Locate a Genropy instance folder without loading GenroPy.

Lookup order for ``spec``:

1. ``spec`` is an existing directory: it is the instance folder.
2. ``<project_dir>/instances/<spec>`` and ``<project_dir>/*/instances/<spec>``
   (``project_dir`` defaults to the current directory).
3. ``$GNR_LOCAL_PROJECTS/*/instances/<spec>``.
4. The ``instances`` and ``projects`` paths declared in
   ``$GENRO_GNRFOLDER/environment.xml`` (default ``~/.gnr``), the same file
   GenroPy reads, so a developer machine resolves names like ``gnr`` does.
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from genro_toolchain import ToolchainError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Instance:
    name: str
    path: Path

    @property
    def config_dir(self) -> Path:
        return self.path / "config"


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


def gnr_folder() -> Path:
    return _expand(os.environ.get("GENRO_GNRFOLDER") or "~/.gnr")


def environment_paths(section: str, gnrfolder: Path | None = None) -> list[Path]:
    """Directories listed under ``<section>`` in GenroPy's environment.xml."""
    env_file = (gnrfolder or gnr_folder()) / "environment.xml"
    if not env_file.is_file():
        return []
    try:
        root = ET.parse(env_file).getroot()
    except ET.ParseError as exc:
        logger.warning("Ignoring unreadable %s: %s", env_file, exc)
        return []
    paths = []
    for node in root.iter(section):
        for child in node:
            if child.get("path"):
                path = _expand(child.get("path"))
                if path.is_dir():
                    paths.append(path)
    return paths


def _candidates(name: str, project_dir: Path) -> list[Path]:
    candidates = [project_dir / "instances" / name]
    candidates += sorted(project_dir.glob(f"*/instances/{name}"))
    local_projects = os.environ.get("GNR_LOCAL_PROJECTS")
    if local_projects:
        candidates += sorted(_expand(local_projects).glob(f"*/instances/{name}"))
    candidates += [p / name for p in environment_paths("instances")]
    for projects in environment_paths("projects"):
        candidates += sorted(projects.glob(f"*/instances/{name}"))
    return candidates


def resolve_instance(spec: str, project_dir: str | Path | None = None) -> Instance:
    """Turn an instance name or path into an :class:`Instance`."""
    as_path = Path(spec).expanduser()
    if as_path.is_dir():
        path = as_path.resolve()
        return Instance(name=path.name, path=path)
    if os.sep in spec or "/" in spec:
        raise ToolchainError(f"Instance folder '{spec}' does not exist")

    base = Path(project_dir).expanduser() if project_dir else Path.cwd()
    for candidate in _candidates(spec, base):
        if candidate.is_dir():
            logger.debug("Instance %s found at %s", spec, candidate)
            return Instance(name=spec, path=candidate.resolve())
    raise ToolchainError(
        f"Instance '{spec}' not found. Pass the instance folder path, "
        f"or run from the project folder (or use --project-dir)."
    )
