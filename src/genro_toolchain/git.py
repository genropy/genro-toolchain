"""Thin wrappers around the git command line."""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

from genro_toolchain import ToolchainError

logger = logging.getLogger(__name__)


def require_git() -> None:
    if shutil.which("git") is None:
        raise ToolchainError("Missing executable: git - please install it")


def run_git(args: list[str], cwd: str | Path | None = None) -> str:
    """Run a git command and return its stripped stdout; raise on failure."""
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        where = f" (in {cwd})" if cwd else ""
        raise ToolchainError(f"git {' '.join(args)} failed{where}: {result.stderr.strip()}")
    return result.stdout.strip()


def toplevel(path: str | Path) -> Path:
    """Root of the working tree containing ``path``."""
    return Path(run_git(["rev-parse", "--show-toplevel"], cwd=path))


def head_commit(path: str | Path) -> str:
    return run_git(["rev-parse", "HEAD"], cwd=path)


def remote_url(path: str | Path, remote: str = "origin") -> str | None:
    """Configured URL of ``remote``, or None when the repository has no such remote.

    Reads the raw config value on purpose: ``git remote get-url`` applies
    ``url.*.insteadOf`` rewrites, which in CI often inject access tokens."""
    try:
        return run_git(["config", "--get", f"remote.{remote}.url"], cwd=path) or None
    except ToolchainError:
        return None


def strip_credentials(url: str) -> str:
    """Drop ``user:password@`` from scheme URLs (scp-style ``git@host:`` is kept)."""
    return re.sub(r"^([a-z+]+://)[^@/]+@", r"\1", url)


def is_dirty(path: str | Path) -> bool:
    return bool(run_git(["status", "--porcelain", "--untracked-files=no"], cwd=path))


def repo_name_from_url(url: str) -> str:
    """``git@github.com:org/my-repo.git`` -> ``my-repo`` (same rule as GenroPy)."""
    return url.rstrip("/").split("/")[-1].split(":")[-1].removesuffix(".git")


def normalize_url(url: str) -> str:
    """A comparison key that treats ssh and https forms of one repository as equal."""
    key = url.strip().rstrip("/").removesuffix(".git")
    key = re.sub(r"^[a-z+]+://", "", key)  # scheme
    key = re.sub(r"^[^@/]+@", "", key)  # user / credentials
    key = re.sub(r"^([^/:]+):(?!\d+/)", r"\1/", key)  # scp form host:path
    key = re.sub(r"^([^/:]+):\d+/", r"\1/", key)  # explicit port
    host, _, rest = key.partition("/")
    return f"{host.lower()}/{rest}"


def browse_url(url: str) -> str:
    """Web URL for a repository, turning ``git@host:org/repo.git`` into https."""
    if re.match(r"^[a-z+]+://", url):
        url = re.sub(r"^[a-z+]+://([^@/]+@)?", "https://", url)
    else:
        url = re.sub(r"^[^@/]+@([^:]+):", r"https://\1/", url)
    return url.removesuffix(".git")


def clone(url: str, dest: Path, ref: str) -> None:
    """Clone ``url`` into ``dest`` and check out ``ref`` (branch, tag or commit)."""
    logger.info("Cloning %s (%s)", url, ref)
    run_git(["clone", "--quiet", url, str(dest)])
    run_git(["checkout", "--quiet", ref], cwd=dest)


def export_head(repo_root: Path, dest: Path) -> None:
    """Copy the committed HEAD tree of a local repository into ``dest``.

    Uses ``git archive``, so it needs no network access and no credentials,
    and only committed files end up in the image."""
    dest.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert proc.stdout is not None
    with tarfile.open(fileobj=proc.stdout, mode="r|") as archive:
        if hasattr(tarfile, "tar_filter"):
            archive.extractall(dest, filter="tar")
        else:  # Python < 3.10.12; the archive comes from our own checkout
            archive.extractall(dest)
    _, stderr = proc.communicate()
    if proc.returncode != 0:
        raise ToolchainError(f"git archive failed in {repo_root}: {stderr.decode().strip()}")
