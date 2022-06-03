from sys import exit

from .cli import cli


def local_chamber():
    exit(cli(prog_name="local_chamber"))


def chamber():
    local_chamber()


if __name__ == "__main__":
    exit(chamber())
