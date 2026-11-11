"""Command line entry points.

``genro-toolchain dockerize ...`` and the ``gnr-dockerize ...`` shortcut accept
the same options as ``gnr app dockerize``, plus a few CI-oriented ones."""

from __future__ import annotations

import argparse
import logging
import sys

from genro_toolchain import ToolchainError, __version__
from genro_toolchain.dockerize import DockerizeOptions, Dockerizer
from genro_toolchain.instance import resolve_instance

logger = logging.getLogger("genro_toolchain")

DOCKERIZE_HELP = "Create a Docker image for a Genropy instance"


def add_dockerize_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "instance",
        help="Instance name, or path to the instance folder (e.g. instances/myapp)",
    )

    compat = parser.add_argument_group("options from `gnr app dockerize`")
    compat.add_argument(
        "-c",
        "--compose",
        action="store_true",
        help="Generate a docker compose file for the created image",
    )
    compat.add_argument(
        "-f",
        "--fqdn",
        dest="fqdns",
        action="append",
        default=[],
        help="FQDN of the site deployment (repeatable)",
    )
    compat.add_argument(
        "-n", "--name", dest="image_name", help="Image name (default: instance name)"
    )
    compat.add_argument("-p", "--push", action="store_true", help="Push the image to the registry")
    compat.add_argument(
        "-r",
        "--registry",
        default="ghcr.io",
        help="Registry to push the image to (default: %(default)s)",
    )
    compat.add_argument(
        "-a",
        "--arch",
        "--platform",
        dest="architecture",
        default="linux/amd64",
        help="Target platform (default: %(default)s)",
    )
    compat.add_argument(
        "--progress",
        dest="build_progress",
        default="auto",
        choices=["auto", "plain", "tty", "quiet", "rawjson"],
        help="Docker build progress output (default: %(default)s)",
    )
    compat.add_argument(
        "-t",
        "--tag",
        dest="version_tag",
        default="latest",
        help="Image version tag (default: %(default)s)",
    )
    compat.add_argument(
        "-u",
        "--username",
        default="softwellsrl",
        help="Registry namespace to push to (default: %(default)s)",
    )
    compat.add_argument(
        "--bleeding", action="store_true", help="Build on the genropy 'develop' base image"
    )
    compat.add_argument(
        "--build-gen",
        dest="build_generate",
        action="store_true",
        help="Not supported (needs GenroPy); kept so old scripts still run",
    )
    compat.add_argument(
        "--keep-temp", action="store_true", help="Keep the temporary build context for debugging"
    )
    compat.add_argument("--no-pull", action="store_true", help="Do not pull the base image")
    compat.add_argument(
        "--router", default="traefik", choices=["traefik"], help="Router used for deployment labels"
    )
    compat.add_argument(
        "--mako", action="store_true", help="Ignored; kept so old scripts still run"
    )

    extra = parser.add_argument_group("genro-toolchain options")
    extra.add_argument(
        "--project-dir",
        metavar="DIR",
        help="Where to look up the instance by name (default: current dir)",
    )
    extra.add_argument(
        "--context-only",
        dest="context_dir",
        metavar="DIR",
        help="Write the build context (Dockerfile + sources) to DIR and "
        "stop, e.g. to build with buildx in CI",
    )
    extra.add_argument(
        "--base-image",
        metavar="IMAGE",
        help="Base image (default: ghcr.io/genropy/genropy:latest, or :develop with --bleeding)",
    )
    extra.add_argument(
        "--clone-main",
        action="store_true",
        help="Clone the instance repository from its remote instead of using the local checkout",
    )


def run_dockerize(args: argparse.Namespace) -> int:
    if args.build_generate:
        logger.warning(
            "--build-gen needs GenroPy and is ignored: write config/build.json "
            "by hand or generate it once with `gnr app dockerize --build-gen`"
        )
    if args.mako:
        logger.warning("--mako is ignored: there is a single compose generator")
    instance = resolve_instance(args.instance, args.project_dir)
    options = DockerizeOptions(
        image_name=args.image_name,
        version_tag=args.version_tag,
        architecture=args.architecture,
        build_progress=args.build_progress,
        bleeding=args.bleeding,
        base_image=args.base_image,
        no_pull=args.no_pull,
        push=args.push,
        registry=args.registry,
        username=args.username,
        compose=args.compose,
        fqdns=args.fqdns,
        router=args.router,
        keep_temp=args.keep_temp,
        context_dir=args.context_dir,
        clone_main=args.clone_main,
    )
    Dockerizer(instance, options).run()
    return 0


def _add_common(parser: argparse.ArgumentParser, loglevel: bool = True) -> None:
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    if loglevel:
        parser.add_argument(
            "--loglevel",
            default="info",
            choices=["debug", "info", "warning", "error"],
            help="Log level (default: %(default)s)",
        )


def _setup_logging(level: str) -> None:
    logging.basicConfig(level=level.upper(), format="%(levelname)s: %(message)s")


def _execute(func, args) -> int:
    _setup_logging(args.loglevel)
    try:
        return func(args)
    except ToolchainError as exc:
        logger.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        return 130


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="genro-toolchain", description="Build tools for Genropy applications"
    )
    _add_common(parser, loglevel=False)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    dockerize = commands.add_parser("dockerize", help=DOCKERIZE_HELP, description=DOCKERIZE_HELP)
    _add_common(dockerize)
    add_dockerize_arguments(dockerize)
    dockerize.set_defaults(func=run_dockerize)
    args = parser.parse_args(argv)
    return _execute(args.func, args)


def dockerize_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gnr-dockerize", description=DOCKERIZE_HELP)
    _add_common(parser)
    add_dockerize_arguments(parser)
    return _execute(run_dockerize, parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
