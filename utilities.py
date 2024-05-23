import argparse
import os
from pathlib import Path

def existent(path):
    """
    Check if a path exists
    :param path: Path to check
    :return: Existent path as a Path object
    """
    if not Path(path).exists():
        raise argparse.ArgumentTypeError(f"{path} does not exist")
    return Path(path).absolute()


def readable(path):
    """
    Check if a path is readable
    :param path: Path to check
    :return: Readable path as a Path object
    """
    if not os.access(path, os.R_OK):
        raise argparse.ArgumentTypeError(f"{path} is not readable")
    return Path(path).absolute()


def writable(path):
    """
    Check if a path is writable
    :param path: Path to check
    :return: Writable path as a Path object
    """
    if not os.access(path, os.W_OK):
        raise argparse.ArgumentTypeError(f"{path} is not writable")
    return Path(path).absolute()


def executable(path):
    """
    Check if a path is executable
    :param path: Path to check
    :return: Executable path as a Path object
    """
    if not os.access(path, os.X_OK):
        raise argparse.ArgumentTypeError(f"{path} is not executable")
    return Path(path).absolute()


def available(path):
    """
    Check if a path has a parent and is available to write to
    :param path: Path to check
    :return: Available path as a Path object
    """
    parent = Path(path).parent.resolve()
    if not (parent.exists() and os.access(str(parent), os.W_OK)):
        raise argparse.ArgumentTypeError(f"""{path} is either not writable or 
                                          the parent directory does not exist""")

    if Path(path).exists():
        return writable(path)
    else:
        return Path(path).absolute()

