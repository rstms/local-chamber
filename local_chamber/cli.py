#!/usr/bin/env python

import subprocess
import sys
import tempfile
from pathlib import Path

import click

from .archive import Backup, Restore
from .chamber import ChamberError, EnvdirChamber, FileChamber, VaultChamber
from .shell import _shell_completion
from .version import __version__

FORMATS = ["json", "yaml", "csv", "tsv", "dotenv", "tfvars"]

BACKENDS = {"file": FileChamber, "envdir": EnvdirChamber, "vault": VaultChamber}


class SysArgs:

    argv = None

    def __init__(self):
        if self.argv is None:
            SysArgs.set(sys.argv)

    @classmethod
    def set(self, args):
        self.argv = args


@click.group("local_chamber")
@click.version_option()
@click.option(
    "-f",
    "--secrets-file",
    default=Path(".secrets.json"),
    type=click.Path(
        file_okay=True,
        dir_okay=False,
        writable=True,
        resolve_path=True,
        allow_dash=False,
        path_type=Path,
    ),
    envvar="SECRETS_FILE",
    show_envvar=True,
    help="secrets json file",
)
@click.option(
    "-s",
    "--secrets-dir",
    default=Path("/etc/local_chamber"),
    type=click.Path(file_okay=False, writable=True, resolve_path=True, allow_dash=False, path_type=Path),
    envvar="SECRETS_DIR",
    show_envvar=True,
    help="secrets directory",
)
@click.option("-t", "--token", type=str, envvar="SECRETS_TOKEN")
@click.option("-r", "--root", type=str, default="chamber", envvar="SECRETS_ROOT")
@click.option(
    "-d",
    "--debug",
    is_flag=True,
    help="debug mode, output detailed error diagnostics",
)
@click.option(
    "-b",
    "--backend",
    envvar="SECRETS_BACKEND",
    default="vault",
    type=click.Choice(list(BACKENDS.keys())),
    help="selected backend system",
)
@click.option(
    "-e/-E",
    "--exists/--if-exists",
    is_flag=True,
    default=True,
    envvar="CHAMBER_REQUIRE_EXISTS",
    help="(default) exit with error if service or key does not exist",
)
@click.pass_context
def cli(ctx, secrets_file, secrets_dir, token, root, debug, backend, exists):

    config = {"file": secrets_file, "dir": secrets_dir, "token": token, "root": root, "backend": backend}

    ctx.obj = BACKENDS[backend](config=config, debug=debug, echo=click.echo, require_exists=exists)

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
            if exception_type is ChamberError:
                fail = exception.args[0]
            else:
                fail = f"{exception_type.__name__}: {exception}"
            click.echo(fail, err=True)
            sys.exit(1)

    sys.excepthook = exception_handler


@cli.command()
@click.pass_context
def version(ctx):
    """show the version"""
    click.echo(f"local_chamber, version {__version__}")
    ctx.exit(0)


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def delete(ctx, service, key):
    """Delete a secret, including all versions"""
    with ctx.obj as chamber:
        ctx.exit(chamber.delete(service, key))


@cli.command()
@click.option("-f", "--force", is_flag=True, help="bypass confirmation")
@click.argument("service", type=str, required=True)
@click.pass_context
def prune(ctx, force, service):
    """Prune a service, including all subkeys"""
    if not force:
        click.confirm(f"About to DELETE {service} and all subkeys.", abort=True)
    with ctx.obj as chamber:
        ctx.exit(chamber.prune(service))


@cli.command()
@click.argument("service", type=str, required=True)
@click.pass_context
def env(ctx, service):
    """Print the secrets from the secrets directory in a format to export as environment variables"""  # noqa
    with ctx.obj as chamber:
        ctx.exit(chamber.env(service))


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
@click.option("--child/--exec", is_flag=True, default=False, help="run command as subprocess or exec in current process")
@click.option("--buffer-output/--no-buffer-output", is_flag=True, default=False, help="buffer output during subprocess run")
@click.argument("service", type=str, nargs=-1)
@click.pass_context
def exec(ctx, pristine, strict, strict_value, child, buffer_output, service):
    """execute command with environment vars loaded from one or more services
    \b
    chamber exec [OPTIONS] SERVICE [SERVICE...] [--] COMMAND [OPTION ...] [ARG...]]]
    """

    args = SysArgs().argv

    if "exec" not in args:
        raise ChamberError("malformed exec command line")

    if "--" not in args:
        raise ChamberError("exec requires '--' argument separator")

    i_exec = args.index("exec")
    i_knife = args.index("--")

    services = args[i_exec + 1 : i_knife]  # noqa: E203

    cmd = args[i_knife + 1 :]  # noqa: E203

    if not cmd:
        raise ChamberError("exec requires command list after '--'")

    for flag in ["--child", "--exec", "--buffer-output", "--no-buffer-output", "--pristine", "--strict"]:
        if flag in services:
            services.remove(flag)
    if "--strict_value" in services:
        i = services.index("--strict_value")
        services.pop(i)
        strict_value = services.pop(i)

    # pass strict_value as flag for strict mode as well as value to use
    if not strict:
        strict_value = None

    with ctx.obj as chamber:
        chamber._exec(
            pristine=pristine,
            strict_value=strict_value,
            child=child,
            services=services,
            buffer_output=buffer_output,
            cmd=cmd,
        )
        click.echo(chamber.proc.stdout)
        click.echo(chamber.proc.stderr, err=True)
        ctx.exit(chamber.proc.returncode)


@cli.command()
@click.option("-o", "--output_file", type=click.File("w"), default="-")
@click.option("-f", "--format", "fmt", type=click.Choice(FORMATS), default="json")
@click.option("-c", "--compact-json", is_flag=True, help="select compact JSON output")
@click.option("-s/-S", "--sort-keys/--no-sort-keys", is_flag=True, default=True, help="select JSON key sorting")
@click.argument("service", type=str, required=True)
@click.pass_context
def export(ctx, output_file, fmt, compact_json, sort_keys, service):
    """Exports parameters in the specified format"""
    with ctx.obj as chamber:
        ctx.exit(chamber.export(output_file=output_file, fmt=fmt, compact_json=compact_json, sort_keys=sort_keys, service=service))


@cli.command()
@click.option("-e", "--editor", type=str, envvar="VISUAL", default="vi", help="editor pathname")
@click.argument("service", type=str, required=True)
@click.pass_context
def edit(ctx, editor, service):
    with tempfile.NamedTemporaryFile("a+") as buffer_file:
        with ctx.obj as chamber:
            chamber.export(output_file=buffer_file, fmt="json", service=service)
        buffer_file.seek(0)
        original_text = buffer_file.read()
        buffer_file.seek(0)
        subprocess.run([editor, buffer_file.name])
        new_text = buffer_file.read()
        buffer_file.seek(0)
        if new_text != original_text:
            with ctx.obj as chamber:
                ctx.exit(chamber._import(service, buffer_file))
    ctx.exit(0)


@cli.command()
@click.option("-r", "--regex", is_flag=True, help="enable regex search (local-only)")
@click.option("-v", "--by-value", is_flag=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def find(ctx, key, by_value, regex):
    """Find the given secret across all services"""
    with ctx.obj as chamber:
        ctx.exit(chamber.find(key, by_value, regex))


@cli.command("import")
@click.argument("service", type=str, required=True)
@click.argument("input-file", type=click.File("rb"), default="-")
@click.pass_context
def _import(ctx, service, input_file):
    "import secrets from json or yaml"
    with ctx.obj as chamber:
        ctx.exit(chamber._import(service, input_file))


@cli.command()
@click.argument("service", type=str, required=True)
@click.pass_context
def list(ctx, service):
    """List the secrets set for a service"""
    with ctx.obj as chamber:
        ctx.exit(chamber.list(service))


@cli.command()
@click.argument("service", type=str, default=None, required=False)
@click.option("-s", "--secrets", is_flag=True, help="Include secret names in the list")
@click.pass_context
def list_services(ctx, secrets, service):
    """List services"""
    with ctx.obj as chamber:
        ctx.exit(chamber.list_services(service_filter=service, include_secrets=secrets))


@cli.command()
@click.option("-q", "--quiet", is_flag=True, help="output only the secret value")
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.pass_context
def read(ctx, quiet, service, key):
    """Read a specific secret from the parameter store"""
    with ctx.obj as chamber:
        ctx.exit(chamber.read(service, key, quiet))


@cli.command()
@click.argument("service", type=str, required=True)
@click.argument("key", type=str, required=True)
@click.argument("value", type=str, required=True)
@click.pass_context
def write(ctx, service, key, value):
    """write a secret"""
    with ctx.obj as chamber:
        ctx.exit(chamber.write(service, key, value))


@cli.command()
@click.option("-f", "--filename", type=click.Path(exists=False, dir_okay=False, path_type=Path))
@click.argument(
    "output-path", type=click.Path(exists=True, file_okay=False, writable=True, resolve_path=True, path_type=Path), default="."
)
@click.pass_context
def backup(ctx, filename, output_path):
    """write secrets data as a gzipped tarball on OUTPUT-PATH

    A timestamp-based filename will be generated.
    Use the --filename option to specify an output filename.
    OUTPUT-PATH defaults to the current directory.
    """

    if filename and filename.suffix != ".tgz":
        filename = Path(str(filename) + ".tgz")

    with ctx.obj as chamber:
        msg = Backup(chamber=chamber, output_path=output_path, file_name=filename).write()
    click.echo(msg)
    ctx.exit(0)


@cli.command()
@click.option("-p", "--patch", is_flag=True, help="merge restore data into current without deleting existing values")
@click.option("-f", "--force", is_flag=True, help="bypass confirmation")
@click.argument("input", type=click.Path(exists=True, dir_okay=False, allow_dash=True, path_type=Path), default="-")
@click.pass_context
def restore(ctx, input, force, patch):
    """restore secrets data from a gzipped tarball file

    Unless --patch is selected, all existing data is purged before restoring.

    """

    if not force:
        click.confirm("Restore will DESTRUCTIVELY overwrite existing data.", abort=True)

    with ctx.obj as chamber:
        msg = Restore(chamber=chamber, tarball=input, patch=patch, echo=click.echo).read()
    click.echo(msg)
    ctx.exit(0)


@cli.command()
@click.option("-s", "--shell", type=click.Choice(["bash", "zsh", "[auto]"]), default="[auto]")
def shell_completion(shell):
    """output shell completion code and instructions"""
    _shell_completion(shell)
