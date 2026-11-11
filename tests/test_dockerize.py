import json
import subprocess

import pytest
import yaml
from conftest import git, make_repo

from genro_toolchain import ToolchainError
from genro_toolchain.cli import dockerize_main, main
from genro_toolchain.dockerize import DockerizeOptions, Dockerizer
from genro_toolchain.instance import resolve_instance


def _dockerizer(workspace, **opts):
    return Dockerizer(resolve_instance(str(workspace["instance"])), DockerizeOptions(**opts))


def _instructions(dockerfile_text):
    return [ln for ln in dockerfile_text.splitlines() if ln and not ln.startswith("#")]


def test_context_layout(workspace, tmp_path):
    ctx = tmp_path / "ctx"
    _dockerizer(workspace).prepare_context(ctx)

    assert sorted(p.name for p in ctx.iterdir()) == [
        "Dockerfile", "deplib", "gunicorn.py", "myproj", "supervisord.conf",
    ]  # fmt: skip
    # dependency checked out at the requested branch, without .git
    assert (ctx / "deplib/packages/deplib/new.py").exists()
    assert not (ctx / "deplib/.git").exists()
    # main repo exported from the local checkout
    assert (ctx / "myproj/packages/mypkg/main.py").exists()
    assert not (ctx / "myproj/.git").exists()

    gunicorn = (ctx / "gunicorn.py").read_text()
    assert "chdir = '/home/genro/genropy_projects/myproj/instances/myapp'" in gunicorn
    assert "pidfile = '/home/genro/gunicorn_myapp.pid'" in gunicorn
    compile(gunicorn, "gunicorn.py", "exec")
    assert (
        "command=gnr web serveprod myapp -c /home/genro/gunicorn.py"
        in (ctx / "supervisord.conf").read_text()
    )


def test_dockerfile_content(workspace, tmp_path):
    ctx = tmp_path / "ctx"
    text = _dockerizer(workspace).prepare_context(ctx).read_text()
    lines = _instructions(text)
    assert lines[:3] == [
        "FROM ghcr.io/genropy/genropy:latest AS build_stage",
        "WORKDIR /home/genro/genropy_projects",
        "RUN apt-get update && apt-get install -y --no-install-recommends "
        "pdftk ghostscript && rm -rf /var/lib/apt/lists/*",
    ]
    assert lines[3] == "USER genro"
    assert "COPY --chown=genro:genro deplib /home/genro/genropy_projects/deplib" in lines
    assert "COPY --chown=genro:genro myproj /home/genro/genropy_projects/myproj" in lines
    # dependencies first, instance repository last (as gnr app dockerize does)
    copies = [ln for ln in lines if ln.startswith("COPY") and "genropy_projects" in ln]
    assert copies[-1].endswith("/myproj")
    assert (
        "RUN ln -s /home/genro/genropy_projects/myproj/instances/myapp/site /home/genro/site"
        in lines
    )
    assert "RUN gnr app checkdep --loglevel=debug -v -n -i myapp" in lines
    assert lines[-1] == "CMD gnr db migrate -u myapp && /usr/bin/supervisord"

    main, dep = workspace["main_commit"], workspace["dep_develop"]
    assert f'"git:myproj"="@{main}"' in text
    assert f'"git:deplib"="develop@{dep}"' in text
    assert f'"git:myproj:url"="https://github.com/example/myproj/commit/{main}"' in text
    assert '"org.opencontainers.image.source"="git@github.com:example/myproj.git"' in text
    assert f'"org.opencontainers.image.revision"="{main}"' in text


def test_base_image_options(workspace):
    assert _dockerizer(workspace).base_image == "ghcr.io/genropy/genropy:latest"
    assert _dockerizer(workspace, bleeding=True).base_image == "ghcr.io/genropy/genropy:develop"
    assert _dockerizer(workspace, base_image="my/base:1").base_image == "my/base:1"


def test_dependency_pinned_commit(workspace, tmp_path):
    build_file = workspace["instance"] / "config/build.json"
    conf = json.loads(build_file.read_text())
    conf["dependencies"]["git_repositories"]["deplib"]["branch_or_commit"] = workspace["dep_commit"]
    build_file.write_text(json.dumps(conf))
    ctx = tmp_path / "ctx"
    text = _dockerizer(workspace).prepare_context(ctx).read_text()
    assert not (ctx / "deplib/packages/deplib/new.py").exists()
    assert f'"git:deplib"="@{workspace["dep_commit"]}"' in text


def test_uncommitted_changes_not_included(workspace, tmp_path, caplog):
    (workspace["project"] / "packages/mypkg/main.py").write_text("# dirty\n")
    (workspace["project"] / "untracked.txt").write_text("x")
    ctx = tmp_path / "ctx"
    _dockerizer(workspace).prepare_context(ctx)
    assert (ctx / "myproj/packages/mypkg/main.py").read_text() == "# main\n"
    assert not (ctx / "myproj/untracked.txt").exists()
    assert "Uncommitted changes" in caplog.text


def test_missing_build_json(workspace, tmp_path, caplog):
    (workspace["instance"] / "config/build.json").unlink()
    ctx = tmp_path / "ctx"
    _dockerizer(workspace).prepare_context(ctx)
    assert not (ctx / "deplib").exists()
    assert "No config/build.json" in caplog.text


def test_failed_clone_stops(workspace, tmp_path):
    build_file = workspace["instance"] / "config/build.json"
    conf = json.loads(build_file.read_text())
    conf["dependencies"]["git_repositories"]["deplib"]["branch_or_commit"] = "no-such-branch"
    build_file.write_text(json.dumps(conf))
    with pytest.raises(ToolchainError, match="checkout"):
        _dockerizer(workspace).prepare_context(tmp_path / "ctx")


def test_main_repo_listed_in_build_json_with_subfolder(tmp_path):
    """A repository holding the project in a subfolder (nested layout)."""
    build = {
        "dependencies": {
            "git_repositories": {
                "mono": {
                    "url": "https://github.com/example/mono.git",
                    "branch_or_commit": "main",
                    "subfolder": "apps/shop",
                }
            }
        }
    }
    repo = tmp_path / "mono"
    make_repo(
        repo,
        {
            "apps/shop/instances/shop/config/build.json": json.dumps(build),
            "apps/shop/packages/shop/main.py": "",
        },
        origin="git@github.com:example/mono.git",
    )
    d = Dockerizer(resolve_instance(str(repo / "apps/shop/instances/shop")))
    assert len(d.repositories) == 1 and d.main_repository.is_main
    lines = _instructions(d.prepare_context(tmp_path / "ctx").read_text())
    assert "COPY --chown=genro:genro mono /home/genro/genropy_projects/mono" in lines
    assert "COPY --chown=genro:genro mono/apps/shop /home/genro/genropy_projects/shop" in lines
    assert (
        "RUN ln -s /home/genro/genropy_projects/shop/instances/shop/site /home/genro/site" in lines
    )


def test_repo_without_origin(tmp_path, caplog):
    repo = tmp_path / "localonly"
    make_repo(repo, {"instances/x/config/.keep": ""})
    d = Dockerizer(resolve_instance(str(repo / "instances/x")))
    text = d.prepare_context(tmp_path / "ctx").read_text()
    assert "COPY --chown=genro:genro localonly /home/genro/genropy_projects/localonly" in text
    assert '"git:localonly:url"' not in text
    assert "no 'origin' remote" in caplog.text
    with pytest.raises(ToolchainError, match="origin"):
        Dockerizer(resolve_instance(str(repo / "instances/x")), DockerizeOptions(clone_main=True))


def test_clone_main(workspace, tmp_path):
    """--clone-main clones the instance repo from its origin, like gnr app dockerize."""
    bare = tmp_path / "remotes" / "myproj.git"
    git("clone", "-q", "--bare", str(workspace["project"]), str(bare), cwd=tmp_path)
    git("remote", "set-url", "origin", str(bare), cwd=workspace["project"])
    (workspace["project"] / "packages/mypkg/main.py").write_text("# dirty\n")
    ctx = tmp_path / "ctx"
    text = _dockerizer(workspace, clone_main=True).prepare_context(ctx).read_text()
    assert (ctx / "myproj/packages/mypkg/main.py").read_text() == "# main\n"
    assert not (ctx / "myproj/.git").exists()
    assert f'"git:myproj"="@{workspace["main_commit"]}"' in text


def test_build_push_and_compose(workspace, tmp_path, monkeypatch):
    calls = []

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "docker":
            calls.append(cmd)
            assert (tmp_path / "work").joinpath(cmd[-1]).exists() or cmd[1] != "build"
            return subprocess.CompletedProcess(cmd, 0)
        return real_run(cmd, *args, **kwargs)

    real_run = subprocess.run
    monkeypatch.setattr("genro_toolchain.dockerize.builder.subprocess.run", fake_run)
    monkeypatch.setattr("genro_toolchain.dockerize.builder.shutil.which", lambda _: "/bin/x")
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    d = _dockerizer(
        workspace,
        image_name="shop",
        version_tag="1.2",
        push=True,
        no_pull=True,
        compose=True,
        fqdns=["shop.example.com"],
        registry="ghcr.io",
        username="acme",
    )
    d.run()
    build, tag, push = calls
    assert build[:3] == ["docker", "build", "--pull=false"]
    assert build[3:9] == ["--platform", "linux/amd64", "--progress", "auto", "-t", "shop:1.2"]
    assert tag == ["docker", "tag", "shop:1.2", "ghcr.io/acme/shop:1.2"]
    assert push == ["docker", "push", "ghcr.io/acme/shop:1.2"]
    # temporary context removed
    assert [p.name for p in work.iterdir()] == ["myapp-compose.yml"]
    compose = yaml.safe_load((work / "myapp-compose.yml").read_text())
    assert compose["services"]["myapp"]["image"] == "shop:1.2"
    assert compose["services"]["myapp"]["labels"]["traefik.enable"] == "true"


def test_build_failure_reported(workspace, tmp_path, monkeypatch):
    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd[0] == "docker":
            return subprocess.CompletedProcess(cmd, 3)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("genro_toolchain.dockerize.builder.subprocess.run", fake_run)
    monkeypatch.setattr("genro_toolchain.dockerize.builder.shutil.which", lambda _: "/bin/x")
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ToolchainError, match="exit 3"):
        _dockerizer(workspace, keep_temp=True).run()
    assert list(tmp_path.glob(".genro-dockerize-*/Dockerfile"))


def test_missing_docker(workspace, monkeypatch):
    d = _dockerizer(workspace)
    monkeypatch.setattr("genro_toolchain.dockerize.builder.shutil.which", lambda _: None)
    with pytest.raises(ToolchainError, match="docker"):
        d.run()


# ---------- CLI ----------


def test_cli_context_only(workspace, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(workspace["project"])
    ctx = tmp_path / "ctx"
    assert main(["dockerize", "myapp", "--context-only", str(ctx), "-t", "9"]) == 0
    assert (ctx / "Dockerfile").exists()
    out = capsys.readouterr().out
    assert "docker build --platform linux/amd64 --progress auto -t myapp:9" in out


def test_cli_context_only_rejects_push_and_non_empty_dir(workspace, tmp_path, caplog):
    inst = str(workspace["instance"])
    assert dockerize_main([inst, "--context-only", str(tmp_path / "c"), "-p"]) == 1
    assert "--push" in caplog.text
    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "x").write_text("")
    assert dockerize_main([inst, "--context-only", str(busy)]) == 1
    assert "not empty" in caplog.text


def test_cli_legacy_flags_accepted(workspace, tmp_path, caplog):
    rc = dockerize_main(
        [str(workspace["instance"]), "--build-gen", "--mako", "--context-only", str(tmp_path / "c")]
    )
    assert rc == 0
    assert "--build-gen needs GenroPy" in caplog.text


def test_cli_unknown_instance(tmp_path, monkeypatch, caplog):
    monkeypatch.chdir(tmp_path)
    assert dockerize_main(["ghost", "--context-only", str(tmp_path / "c")]) == 1
    assert "Instance 'ghost' not found" in caplog.text
