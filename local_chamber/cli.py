#!/usr/bin/env python

import sys
from pathlib import Path

import click

from .local_chamber import LocalChamber, LocalChamberError

FORMATS = ["json", "yaml", "csv", "tsv", "dotenv", "tfvars"]


@click.group("local_chamber")
@click.version_option()
@click.option(
    "-s",
    "--secrets_dir",
    default=Path(".") / "secrets",
    type=click.Path(
        exists=True,
        file_okay=False,
        writable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
    ),
    envvar="SECRETS_DIR",
    show_envvar=True,
    help="secrets directory",
)
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="debug mode, output detailed error diagnostics",
)
@click.pass_context
def cli(ctx, secrets_dir, debug):

    ctx.obj = LocalChamber(secrets_dir=secrets_dir, debug=debug, echo=click.echo)

    def exception_handler(
        exception_type,
        exception,
        traceback,
        debug_hook=sys.excepthook,
    ):
        if debug:
            debug_hook(
                exception_type,
                exception,
                traceback,
            )
        else:
            if exception_type is LocalChamberError:
                fail = exception.args[0]
            else:
                fail = f"{exception_type.__name__}: {exception}"
            click.echo(fail, err=True)
            sys.exit(1)

    sys.excepthook = exception_handler


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def delete(ctx, service, key):
    """Delete a secret, including all versions"""
    ctx.exit(ctx.obj.delete(service, key))


@cli.command()
@click.argument("service", type=str, required=True)
@click.pass_context
def env(ctx, service):
    """Print the secrets from the secrets directory in a format to export as environment variables"""  # noqa
    ctx.exit(ctx.obj.env(service))


@cli.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.option("--pristine", is_flag=True, help="do not inherit parent environment")
@click.option(
    "--strict",
    is_flag=True,
    help="ensure any env variables variables passed with <strict_value> are overwritten with service values",  # noqa
)
@click.option(
    "--strict_value",
    type=str,
    default="chamberme",
    help="override the default strict_value",
)
@click.argument("service", type=str, required=True)
@click.pass_context
def exec(ctx, pristine, strict, strict_value, service):
    """Executes a command with secrets loaded into the environment"""
    args = sys.argv.copy()
    if args[1] != "exec":
        raise LocalChamberError("malformed exec command line")
    if "--" not in args:
        raise LocalChamberError("exec requires '--' argument separator")
    knife = args.index("--")
    services = args[2:knife]
    cmd = args[knife + 1 :]  # noqa
    if not cmd:
        raise LocalChamberError("exec requires command list after '--'")
    if "--pristine" in services:
        pristine = True
        services.remove("--pristine")
    if "--strict" in services:
        strict = True
        services.remove("--strict")
    if "--strict_value" in services:
        i = services.index("--strict_value")
        services.pop(i)
        strict_value = services.pop(i)

    # pass strict_value as flag for strict mode as well as value to use
    if not strict:
        strict_value = None

    ctx.exit(
        ctx.obj._exec(
            pristine=pristine,
            strict_value=strict_value,
            services=services,
            cmd=cmd,
        )
    )


@cli.command()
@click.option("-o", "--output_file", type=click.File("w"), default="-")
@click.option("-f", "--format", "fmt", type=click.Choice(FORMATS), default="json")
@click.argument("service", type=str, required=True)
@click.pass_context
def export(ctx, output_file, fmt, service):
    """Exports parameters in the specified format"""
    ctx.exit(ctx.obj.export(output_file, fmt, service))


@cli.command()
@click.option("-r", "--regex", is_flag=True, help="enable regex search (local-only)")
@click.option("-v", "--by-value", is_flag=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def find(ctx, key, by_value, regex):
    """Find the given secret across all services"""
    ctx.exit(ctx.obj.find(key, by_value, regex))


@cli.command("import")
@click.argument("service", type=str, required=True)
@click.argument("input-file", type=click.File("rb"), default="-")
@click.pass_context
def _import(ctx, service, input_file):
    "import secrets from json or yaml"
    ctx.exit(ctx.obj._import(service, input_file))


@cli.command()
@click.argument("service", type=str, required=True)
@click.pass_context
def list(ctx, service):
    """List the secrets set for a service"""
    ctx.exit(ctx.obj.list(service))


@cli.command()
@click.argument("service", type=str, default=None, required=False)
@click.option("-s", "--secrets", is_flag=True, help="Include secret names in the list")
@click.pass_context
def list_services(ctx, secrets, service):
    """List services"""
    ctx.exit(ctx.obj.list_services(service_filter=service, include_secrets=secrets))


@cli.command()
@click.option("-q", "--quiet", is_flag=True, help="output only the secret value")
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def read(ctx, quiet, service, key):
    """Read a specific secret from the parameter store"""
    ctx.exit(ctx.obj.read(service, key, quiet))


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.argument("value", type=str, required=True)
@click.pass_context
def write(ctx, service, key, value):
    """write a secret"""
    ctx.exit(ctx.obj.write(service, key, value))
