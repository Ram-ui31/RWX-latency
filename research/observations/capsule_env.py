from importlib.metadata import version
import platform
import sys


def fingerprint():
    return [sys.version, platform.system(), platform.machine(),
            *[version(n) for n in ('pytest','duckdb','numpy','pandas')]]
