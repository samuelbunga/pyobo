# -*- coding: utf-8 -*-

"""Version information for PyOBO."""

__all__ = [
    'VERSION',
    'get_version',
]

VERSION = '0.0.8-dev'


def get_version() -> str:
    """Get the software version of PyOBO."""
    return VERSION
