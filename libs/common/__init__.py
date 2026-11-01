"""Shared library for the admission-document pipeline functions.

Holds code every OpenFaaS function needs: settings, tenant context,
logging, storage and database access, and the document schemas.
"""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("admission-processor")
except PackageNotFoundError:  # running from a source tree without install
    __version__ = "0.0.0"

__all__ = ["__version__"]
