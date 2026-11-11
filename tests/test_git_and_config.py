import json

import pytest

from genro_toolchain import ToolchainError
from genro_toolchain.buildconfig import (
    apt_dependencies,
    dependency_repositories,
    docker_images,
    load_build_config,
)
from genro_toolchain.git import browse_url, normalize_url, repo_name_from_url
from genro_toolchain.instance import Instance, resolve_instance


@pytest.mark.parametrize(
    "url",
    [
        "git@github.com:Org/repo.git",
        "https://github.com/Org/repo.git",
        "https://github.com/Org/repo",
        "https://x-access-token:abc@github.com/Org/repo.git",
        "ssh://git@github.com:22/Org/repo.git",
        "ssh://git@GitHub.com/Org/repo/",
    ],
)
def test_normalize_url_equivalent_forms(url):
    assert normalize_url(url) == "github.com/Org/repo"


@pytest.mark.parametrize(
    "url,name",
    [
        ("git@github.com:org/my-repo.git", "my-repo"),
        ("https://github.com/org/my-repo", "my-repo"),
        ("/srv/git/deplib.git", "deplib"),
    ],
)
def test_repo_name_from_url(url, name):
    assert repo_name_from_url(url) == name


def test_browse_url():
    assert browse_url("git@github.com:org/repo.git") == "https://github.com/org/repo"
    assert browse_url("https://tok@github.com/org/repo.git") == "https://github.com/org/repo"


# ---------- instance lookup ----------


def test_resolve_instance_by_path(workspace):
    inst = resolve_instance(str(workspace["instance"]))
    assert inst.name == "myapp" and inst.path == workspace["instance"]


def test_resolve_instance_by_name_in_project_dir(workspace):
    inst = resolve_instance("myapp", workspace["project"])
    assert inst.path == workspace["instance"]


def test_resolve_instance_by_name_in_projects_folder(workspace):
    inst = resolve_instance("myapp", workspace["root"] / "projects")
    assert inst.path == workspace["instance"]


def test_resolve_instance_from_environment_xml(workspace, tmp_path, monkeypatch):
    gnr = tmp_path / "gnrfolder"
    gnr.mkdir()
    (gnr / "environment.xml").write_text(
        f'<GenRoBag><projects><mine path="{workspace["root"] / "projects"}"/></projects></GenRoBag>'
    )
    monkeypatch.setenv("GENRO_GNRFOLDER", str(gnr))
    monkeypatch.chdir(tmp_path)
    assert resolve_instance("myapp").path == workspace["instance"]


def test_resolve_instance_from_local_projects(workspace, tmp_path, monkeypatch):
    monkeypatch.setenv("GNR_LOCAL_PROJECTS", str(workspace["root"] / "projects"))
    monkeypatch.chdir(tmp_path)
    assert resolve_instance("myapp").path == workspace["instance"]


def test_resolve_instance_not_found(tmp_path):
    with pytest.raises(ToolchainError, match="not found"):
        resolve_instance("nope", tmp_path)
    with pytest.raises(ToolchainError, match="does not exist"):
        resolve_instance("instances/nope", tmp_path)


# ---------- build.json ----------


def _instance(tmp_path, build=None, apt=None):
    cfg = tmp_path / "inst" / "config"
    cfg.mkdir(parents=True)
    if build is not None:
        (cfg / "build.json").write_text(build if isinstance(build, str) else json.dumps(build))
    if apt is not None:
        (cfg / "apt-dependencies.txt").write_text(apt)
    return Instance("inst", tmp_path / "inst")


def test_missing_build_json(tmp_path):
    inst = _instance(tmp_path)
    assert load_build_config(inst) is None
    assert dependency_repositories(None) == []
    assert apt_dependencies(inst) == []


def test_invalid_build_json(tmp_path):
    with pytest.raises(ToolchainError, match="Invalid JSON"):
        load_build_config(_instance(tmp_path, build="{nope"))


def test_dependency_repositories_defaults_and_dedupe():
    config = {
        "dependencies": {
            "git_repositories": {
                "a": {"url": "git@github.com:org/a.git"},
                "a2": {"url": "https://github.com/org/a", "branch_or_commit": "v2"},
                "b": {"url": "git@github.com:org/b.git", "subfolder": "proj/b"},
            },
            "docker_images": [{"name": "redis", "tag": "7"}],
        }
    }
    repos = dependency_repositories(config)
    assert [(r.name, r.ref, r.subfolder) for r in repos] == [
        ("a", "v2", None),
        ("b", "master", "proj/b"),
    ]
    assert docker_images(config) == [{"name": "redis", "tag": "7", "description": "No description"}]


def test_dependency_without_url():
    with pytest.raises(ToolchainError, match="no url"):
        dependency_repositories({"dependencies": {"git_repositories": {"x": {}}}})


def test_apt_dependencies(tmp_path):
    inst = _instance(tmp_path, apt="pdftk\n\n  # comment\nghostscript  poppler-utils\n")
    assert apt_dependencies(inst) == ["pdftk", "ghostscript", "poppler-utils"]


def test_strip_credentials():
    from genro_toolchain.git import strip_credentials

    assert strip_credentials("https://gitlab-ci-token:xyz@gitlab.com/o/r.git") == (
        "https://gitlab.com/o/r.git"
    )
    assert strip_credentials("git@github.com:o/r.git") == "git@github.com:o/r.git"


def test_remote_url_ignores_insteadof_rewrites(workspace, monkeypatch):
    from genro_toolchain.git import remote_url

    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "url.https://tok@github.com/.insteadOf")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "git@github.com:")
    assert remote_url(workspace["project"]) == "git@github.com:example/myproj.git"
