"""Shared controller-level validation helpers."""

from fastapi import HTTPException, UploadFile, status

from cadence.constants import PLUGIN_FILE_EXTENSION


def validate_plugin_file(file: UploadFile) -> None:
    """Validate that the uploaded file is a plugin zip archive.

    Args:
        file: Uploaded file to validate

    Raises:
        HTTPException: 400 if filename is missing or not a .zip file
    """
    if not file.filename or not file.filename.endswith(PLUGIN_FILE_EXTENSION):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .zip files are supported",
        )
