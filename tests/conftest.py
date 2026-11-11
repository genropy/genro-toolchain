import json
import subprocess
from pathlib import Path

import pytest


def git(*args, cwd):
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def make_repo(path: Path, files: dict[str, str], origin: str | None = None) -> str:
    """Create a git repository with ``files`` committed; return the commit."""
    path.mkdir(parents=True, exist_ok=True)
    git("init", "-q", "-b", "main", cwd=path)
    git("config", "user.email", "test@example.com", cwd=path)
    git("config", "user.name", "Test", cwd=path)
    git("config", "commit.gpgsign", "false", cwd=path)
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    git("add", "-A", cwd=path)
    git("commit", "-q", "-m", "init", cwd=path)
    if origin:
        git("remote", "add", "origin", origin, cwd=path)
    return git("rev-parse", "HEAD", cwd=path)


@pytest.fixture(autouse=True)
def isolated_gnr(tmp_path, monkeypatch):
    """Never read the developer's real ~/.gnr during tests."""
    monkeypatch.setenv("GENRO_GNRFOLDER", str(tmp_path / "no-gnr"))
    monkeypatch.delenv("GNR_LOCAL_PROJECTS", raising=False)


@pytest.fixture
def workspace(tmp_path):
    """A project repo with instance ``myapp`` depending on a ``deplib`` repo.

    Returns a dict with paths and commits."""
    dep_src = tmp_path / "src" / "deplib"
    dep_commit = make_repo(dep_src, {"packages/deplib/main.py": "# dep\n"})
    git("checkout", "-q", "-b", "develop", cwd=dep_src)
    (dep_src / "packages/deplib/new.py").write_text("# develop\n")
    git("add", "-A", cwd=dep_src)
    git("commit", "-q", "-m", "develop", cwd=dep_src)
    dep_develop = git("rev-parse", "HEAD", cwd=dep_src)
    dep_bare = tmp_path / "remotes" / "deplib.git"
    git("clone", "-q", "--bare", str(dep_src), str(dep_bare), cwd=tmp_path)

    build = {
        "dependencies": {
            "git_repositories": {
                "deplib": {
                    "url": str(dep_bare),
                    "branch_or_commit": "develop",
                    "description": "deplib",
                }
            }
        }
    }
    project = tmp_path / "projects" / "myproj"
    main_commit = make_repo(
        project,
        {
            "packages/mypkg/main.py": "# main\n",
            "instances/myapp/config/instanceconfig.xml": "<GenRoBag/>\n",
            "instances/myapp/config/build.json": json.dumps(build),
            "instances/myapp/config/apt-dependencies.txt": "pdftk\n# comment\nghostscript\n",
        },
        origin="git@github.com:example/myproj.git",
    )
    return {
        "root": tmp_path,
        "project": project,
        "instance": project / "instances" / "myapp",
        "main_commit": main_commit,
        "dep_bare": dep_bare,
        "dep_commit": dep_commit,
        "dep_develop": dep_develop,
    }
