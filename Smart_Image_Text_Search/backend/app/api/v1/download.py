from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse

from app.core.config import settings

router = APIRouter(tags=["download"])

_HERE = os.path.dirname(os.path.abspath(__file__))
_INSTALLER_PATH = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "..", "dist", "installer", "SmartImageSearch-Setup.exe")
)
_INSTALLER_FILENAME = "SmartImageSearch-Setup.exe"


@router.get("/download/installer")
def download_installer():
    """Public endpoint - downloads the SmartImageSearch installer.

    If an external hosting URL (GitHub Releases, Google Drive, Dropbox, S3) is
    configured via INSTALLER_DOWNLOAD_URL, redirect the client to it.
    Otherwise, stream from local disk if present.
    """
    if settings.installer_download_url:
        return RedirectResponse(
            url=settings.installer_download_url,
            status_code=status.HTTP_302_FOUND,
        )

    if not os.path.isfile(_INSTALLER_PATH):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "Installer file not found on the server. "
                "Configure INSTALLER_DOWNLOAD_URL in environment settings to point to your hosted installer."
            ),
        )
    return FileResponse(
        path=_INSTALLER_PATH,
        media_type="application/octet-stream",
        filename=_INSTALLER_FILENAME,
    )
