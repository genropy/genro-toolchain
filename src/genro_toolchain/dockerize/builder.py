"""Build a Docker image for a Genropy instance (replacement for ``gnr app dockerize``)."""

from __future__ import annotations

import datetime
import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from genro_toolchain import ToolchainError, __version__, git
from genro_toolchain.buildconfig import (
    Repository,
    apt_dependencies,
    dependency_repositories,
    load_build_config,
)
from genro_toolchain.dockerize import compose, templates
from genro_toolchain.instance import Instance

logger = logging.getLogger(__name__)

BASE_IMAGE = "ghcr.io/genropy/genropy"
PROJECTS_ROOT = PurePosixPath("/home/genro/genropy_projects")


@dataclass
class DockerizeOptions:
    image_name: str | None = None
    version_tag: str = "latest"
    architecture: str = "linux/amd64"
    build_progress: str = "auto"
    bleeding: bool = False
    base_image: str | None = None
    no_pull: bool = False
    push: bool = False
    registry: str = "ghcr.io"
    username: str = "softwellsrl"
    compose: bool = False
    fqdns: list[str] = field(default_factory=list)
    router: str = "traefik"
    keep_temp: bool = False
    # Write the build context here and stop: no docker build, no push.
    context_dir: str | None = None
    # Clone the instance repository from its remote instead of exporting
    # the local checkout (the behaviour of `gnr app dockerize`).
    clone_main: bool = False


@dataclass
class _PlannedRepo:
    repo: Repository
    commit: str = ""


class Dockerizer:
    def __init__(self, instance: Instance, options: DockerizeOptions | None = None):
        self.instance = instance
        self.options = options or DockerizeOptions()
        self.image_name = self.options.image_name or instance.name
        git.require_git()
        self.main_root = git.toplevel(instance.path)
        self.config = load_build_config(instance)
        if self.config is None:
            logger.warning(
                "No config/build.json in %s: the image will contain only the instance "
                "repository. Generate one with `gnr app dockerize --build-gen` (needs "
                "GenroPy) or write it by hand.",
                instance.path,
            )
        self.apt_packages = apt_dependencies(instance)
        self.repositories = self._plan_repositories()

    # ------------------------------------------------------------------
    # Planning
    # ------------------------------------------------------------------

    @property
    def base_image(self) -> str:
        if self.options.base_image:
            return self.options.base_image
        return f"{BASE_IMAGE}:{'develop' if self.options.bleeding else 'latest'}"

    @property
    def image_ref(self) -> str:
        return f"{self.image_name}:{self.options.version_tag}"

    @property
    def main_repository(self) -> Repository:
        return next(r for r in self.repositories if r.is_main)

    def _plan_repositories(self) -> list[Repository]:
        repos = dependency_repositories(self.config)
        main_url = git.remote_url(self.main_root)
        if main_url is None:
            if self.options.clone_main:
                raise ToolchainError(f"--clone-main: {self.main_root} has no 'origin' remote")
            logger.warning("%s has no 'origin' remote; image labels omit its URL", self.main_root)
        main_commit = git.head_commit(self.main_root)
        main_key = git.normalize_url(main_url) if main_url else None

        main = next((r for r in repos if main_key and r.key == main_key), None)
        if main is None:
            main = Repository(
                url=main_url or str(self.main_root),
                ref=main_commit,
                description=self.instance.name,
            )
            repos.append(main)
        elif not self.options.clone_main and main.ref not in (main_commit, self._main_branch()):
            logger.warning(
                "build.json pins the instance repository at '%s', but the local checkout "
                "(HEAD %s) is used. Pass --clone-main to build from '%s' instead.",
                main.ref,
                main_commit[:12],
                main.ref,
            )
        main.is_main = True
        if main_url is None:
            main.url = str(self.main_root)

        names = [r.name for r in repos]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ToolchainError(
                f"Repositories with the same folder name: {', '.join(sorted(duplicates))}"
            )
        return repos

    def _main_branch(self) -> str | None:
        try:
            return git.run_git(["branch", "--show-current"], cwd=self.main_root) or None
        except ToolchainError:
            return None

    def _dest_folder(self, repo: Repository) -> str:
        return PurePosixPath(repo.subfolder).name if repo.subfolder else repo.name

    def site_folder(self) -> PurePosixPath:
        """Path of the instance's ``site`` folder inside the image."""
        main = self.main_repository
        rel = self.instance.path.relative_to(self.main_root)
        if main.subfolder:
            try:
                rel = self.instance.path.relative_to(self.main_root / main.subfolder)
            except ValueError:
                rel = Path("instances") / self.instance.name
        return PROJECTS_ROOT / self._dest_folder(main) / rel.as_posix() / "site"

    # ------------------------------------------------------------------
    # Build context
    # ------------------------------------------------------------------

    def _fetch(self, repo: Repository, context: Path) -> str:
        """Put the repository sources in ``context/<name>``; return the commit."""
        dest = context / repo.name
        if repo.is_main and not self.options.clone_main:
            logger.info("Exporting instance repository %s from %s", repo.name, self.main_root)
            if git.is_dirty(self.main_root):
                logger.warning("Uncommitted changes in %s are NOT included", self.main_root)
            git.export_head(self.main_root, dest)
            return git.head_commit(self.main_root)
        ref = repo.ref
        git.clone(repo.url, dest, ref)
        commit = git.head_commit(dest)
        shutil.rmtree(dest / ".git", ignore_errors=True)
        return commit

    def _labels(self, planned: list[_PlannedRepo]) -> dict[str, str]:
        now = str(datetime.datetime.now(datetime.UTC))
        main = next(p for p in planned if p.repo.is_main)
        source = (
            "" if main.repo.url == str(self.main_root) else git.strip_credentials(main.repo.url)
        )
        name = self.instance.name
        labels = {
            "gnr_app_dockerize_on": now,
            "org.opencontainers.image.created": now,
            "org.label-schema.build-date": now,
            "org.opencontainers.image.title": name,
            "org.label-schema.name": name,
            "org.opencontainers.image.description": f"Genropy application - instance {name}",
            "org.opencontainers.image.source": source,
            "org.label-schema.vcs-url": source,
            "org.opencontainers.image.revision": main.commit,
            "org.opencontainers.image.version": self.options.version_tag,
        }
        for item in planned:
            repo, commit = item.repo, item.commit
            ref = commit if (repo.is_main and not self.options.clone_main) else repo.ref
            labels[f"git:{repo.name}"] = f"@{commit}" if ref == commit else f"{ref}@{commit}"
            if not (repo.is_main and not source):
                labels[f"git:{repo.name}:url"] = f"{git.browse_url(repo.url)}/commit/{commit}"
        return labels

    def _dockerfile(self, planned: list[_PlannedRepo]) -> str:
        name = self.instance.name
        now = datetime.datetime.now(datetime.UTC)
        lines = [
            f"# Docker image for instance {name}",
            f"# Dockerfile built on {now} by genro-toolchain {__version__}",
            "",
            f"FROM {self.base_image} AS build_stage",
            f"WORKDIR {PROJECTS_ROOT}",
        ]
        if self.apt_packages:
            # Must run as root, before switching to the genro user.
            lines.append(
                "RUN apt-get update && apt-get install -y --no-install-recommends "
                f"{' '.join(self.apt_packages)} && rm -rf /var/lib/apt/lists/*"
            )
        lines += [
            "USER genro",
            "",
            'ENV PATH="/home/genro/.local/bin:$PATH"',
            'ENV GENRO_GNRFOLDER="/home/genro/.gnr/"',
        ]
        for item in planned:
            repo = item.repo
            lines.append(f"# {repo.description}")
            copy = "COPY --chown=genro:genro"
            if repo.subfolder:
                dest = self._dest_folder(repo)
                if "/" in repo.subfolder.strip("/"):
                    # Nested project: also copy the whole repository.
                    lines.append(f"{copy} {repo.name} {PROJECTS_ROOT}/{repo.name}")
                lines.append(f"{copy} {repo.name}/{repo.subfolder} {PROJECTS_ROOT}/{dest}")
            else:
                lines.append(f"{copy} {repo.name} {PROJECTS_ROOT}/{repo.name}")
        lines += [
            f"RUN ln -s {self.site_folder()} /home/genro/site",
            "EXPOSE 8888/tcp 9999/tcp",
            "",
            "# Final customizations",
            "COPY --chown=genro:genro gunicorn.py /home/genro/gunicorn.py",
            "COPY --chown=genro:genro supervisord.conf "
            f"/etc/supervisor/conf.d/{name}-supervisor.conf",
            f"RUN gnr app checkdep --loglevel=debug -v -n -i {name}",
            templates.label_instruction(self._labels(planned)),
            f"CMD gnr db migrate -u {name} && /usr/bin/supervisord",
        ]
        return "\n".join(lines) + "\n"

    def prepare_context(self, context: Path) -> Path:
        """Fill ``context`` with sources, configs and the Dockerfile; return its path."""
        context.mkdir(parents=True, exist_ok=True)
        planned = [_PlannedRepo(repo, self._fetch(repo, context)) for repo in self.repositories]
        site = self.site_folder()
        (context / "gunicorn.py").write_text(
            templates.gunicorn_conf(self.instance.name, str(site.parent))
        )
        (context / "supervisord.conf").write_text(templates.supervisord_conf(self.instance.name))
        dockerfile = context / "Dockerfile"
        dockerfile.write_text(self._dockerfile(planned))
        logger.info("Dockerfile generated at %s", dockerfile)
        return dockerfile

    # ------------------------------------------------------------------
    # Docker
    # ------------------------------------------------------------------

    def build_command(self, context: Path) -> list[str]:
        cmd = ["docker", "build"]
        if self.options.no_pull:
            cmd.append("--pull=false")
        cmd += [
            "--platform", self.options.architecture,
            "--progress", self.options.build_progress,
            "-t", self.image_ref,
            str(context),
        ]  # fmt: skip
        return cmd

    @property
    def push_ref(self) -> str:
        return f"{self.options.registry}/{self.options.username}/{self.image_ref}"

    def _docker(self, cmd: list[str]) -> None:
        logger.info("Running: %s", " ".join(cmd))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            raise ToolchainError(f"'{' '.join(cmd[:2])}' failed (exit {result.returncode})")

    def push(self) -> None:
        logger.info("Tagging %s as %s", self.image_ref, self.push_ref)
        self._docker(["docker", "tag", self.image_ref, self.push_ref])
        self._docker(["docker", "push", self.push_ref])

    def write_compose(self, folder: Path | None = None) -> Path:
        path = (folder or Path.cwd()) / f"{self.instance.name}-compose.yml"
        path.write_text(
            compose.compose_yaml(
                self.instance.name, self.image_ref, self.options.fqdns, self.options.router
            )
        )
        return path

    def run(self) -> None:
        opts = self.options
        if opts.context_dir:
            if opts.push:
                raise ToolchainError("--push needs a docker build; drop --context-only")
            context = Path(opts.context_dir).absolute()
            if context.exists() and any(context.iterdir()):
                raise ToolchainError(f"Context folder {context} is not empty")
            self.prepare_context(context)
            print(f"Build context ready in {context}")
            print(f"Build it with: {' '.join(self.build_command(context))}")
        else:
            if shutil.which("docker") is None:
                raise ToolchainError("Missing executable: docker - please install it")
            context = Path(tempfile.mkdtemp(prefix=".genro-dockerize-", dir=Path.cwd()))
            try:
                self.prepare_context(context)
                self._docker(self.build_command(context))
                logger.info("Docker image %s built successfully", self.image_ref)
            finally:
                if opts.keep_temp:
                    logger.warning("Build directory %s kept as requested", context)
                else:
                    shutil.rmtree(context, ignore_errors=True)
            if opts.push:
                self.push()

        if opts.compose:
            path = self.write_compose()
            print(f"Created docker compose file {path.name}")
            print(f"You can now execute 'docker compose -f {path.name} up'")
            print("YMMV, please adjust the generated file accordingly.")
