#!/usr/bin/env python

import click
import sys
from pathlib import Path

from .local_chamber import LocalChamber

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

    breakpoint()
    ctx.obj = LocalChamber(
        secrets_dir=secrets_dir, debug=debug, echo=click.echo
    )

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
            click.echo(f"{exception_type.__name__}: {exception}", err=True)
            click.Abort

    sys.excepthook = exception_handler


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def delete(ctx, service, key):
    """Delete a secret, including all versions"""
    return ctx.obj.delete(service, key)


@cli.command()
@click.argument("service", type=str, required=True)
@click.pass_context
def env(ctx, service):
    """Print the secrets from the secrets directory in a format to export as environment variables"""
    return ctx.obj.env(service)


@cli.command(
    context_settings=dict(ignore_unknown_options=True, allow_extra_args=True)
)
@click.argument("service", type=str, required=True)
@click.pass_context
def exec(ctx, service):
    """Executes a command with secrets loaded into the environment"""
    return ctx.obj.exec(service, **ctx.args)


@cli.command()
@click.option("-o", "--output_file", type=click.File("w"), default="-")
@click.option(
    "-f", "--format", "fmt", type=click.Choice(FORMATS), default="json"
)
@click.argument("service", type=str, required=True)
@click.pass_context
def export(ctx, output_file, fmt, service):
    """Exports parameters in the specified format"""
    return ctx.obj.export(output_file, fmt, service)


@cli.command()
@click.option("-v", "--by-value", is_flag=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def find(ctx, key, by_value):
    """Find the given secret across all services"""
    return ctx.obj.find(key, by_value)


@cli.command("import")
@click.argument("service", type=str, required=True)
@click.argument("input-file", type=click.File("rb"), default="-")
@click.pass_context
def _import(ctx, service, input_file):
    "import secrets from json or yaml"
    breakpoint()
    return ctx.obj._import(service, input_file)


@cli.command()
@click.argument("service", type=str, required=True)
@click.pass_context
def list(ctx, service):
    """List the secrets set for a service"""
    return ctx.obj.list(service)


@cli.command()
@click.pass_context
def list_services(ctx):
    """List services"""
    return ctx.obj.list_services()


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def read(ctx, service, key):
    """Read a specific secret from the parameter store"""
    return ctx.obj.read(service, key)


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.argument("value", type=str, required=True)
@click.pass_context
def write(ctx, service, key, value):
    """write a secret"""
    return ctx.obj.write(service, key, value)


if __name__ == "__main__":
    sys.exit(cli())
