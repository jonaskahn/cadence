"""Exception handling package.

This package provides custom exception classes and global exception handlers
that map domain exceptions to HTTP responses.
"""

from cadence.exception.api_exceptions import CadenceException

__all__ = ["CadenceException"]
