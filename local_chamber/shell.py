# shell completion

from os import environ, system

import click


def _shell_completion(shell):
    """output shell completion code"""
    if shell == "[auto]":
        if "ZSH_VERSION" in environ:
            shell = "zsh"
        else:
            shell = "bash"
    if shell not in ["bash", "zsh"]:
        raise RuntimeError("cannot determine shell")

    if shell == "bash":
        click.echo("Writing file ~/.chamber-complete.bash...")
        system("_LOCAL_CHAMBER_COMPLETE=bash_source local_chamber >~/.local_chamber-complete.bash")
        click.echo("Source this file from ~/.bashrc")
        click.echo("ex: . ~/.local_chamber-complete.bash")

    elif shell == "zsh":
        click.echo("Writing file ~/.local_chamber-complete.zsh...")
        system("_LOCAL_CHAMBER_COMPLETE=zsh_source local_chamber >~/.local_chamber-complete.zsh")
        click.echo("Source this file from ~/.zshrc")
        click.echo("ex: . ~/.local_chamber-complete.zsh")
