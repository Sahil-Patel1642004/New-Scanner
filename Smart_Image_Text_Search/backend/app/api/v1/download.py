from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

router = APIRouter(tags=["download"])

# Installer is built into dist/installer/ relative to the project root.
# This file lives at  backend/app/api/v1/download.py  → 4 levels up = project root.
_HERE = os.path.dirname(os.path.abspath(__file__))
_INSTALLER_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "..", "dist", "installer", "SmartImageSearch-Setup.exe")
)
_INSTALLER_FILENAME = "SmartImageSearch-Setup.exe"


@router.get("/download/installer")
def download_installer() -> FileResponse:
    """Public endpoint – streams the SmartImageSearch installer to the client."""
    if not os.path.isfile(_INSTALLER_PATH):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Installer file not found on the server. Please contact support.",
        )
    return FileResponse(
        path=_INSTALLER_PATH,
        media_type="application/octet-stream",
        filename=_INSTALLER_FILENAME,
    )
