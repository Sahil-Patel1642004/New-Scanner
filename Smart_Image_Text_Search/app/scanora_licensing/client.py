from __future__ import annotations

import base64
import hashlib
import json
import os
import platform
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


class LicenceError(Exception):
    pass


class LicenceServiceUnavailable(LicenceError):
    pass


def _data_directory() -> Path:
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".smart_image_search"))
    return root / "SmartImageSearch"


def _canonical_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")


class LicenceClient:
    def __init__(self, api_base_url: str | None = None):
        self.data_directory = _data_directory()
        config_path = self.data_directory / "licence-config.json"
        try:
            runtime_config = json.loads(config_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            runtime_config = {}
        except (OSError, UnicodeError, ValueError) as error:
            raise LicenceError("The local licence configuration file could not be read.") from error
        if not isinstance(runtime_config, dict):
            raise LicenceError("The local licence configuration must be a JSON object.")

        configured_url = os.environ.get("SCANORA_LICENCE_API_URL") or runtime_config.get("api_base_url")
        configured_pin = os.environ.get("SCANORA_LICENCE_PUBLIC_KEY") or runtime_config.get("public_key")
        if configured_url is not None and not isinstance(configured_url, str):
            raise LicenceError("The configured licence service URL is invalid.")
        if configured_pin is not None and not isinstance(configured_pin, str):
            raise LicenceError("The configured licence public key is invalid.")

        self.api_base_url = (api_base_url or configured_url or "http://127.0.0.1:8000/api/v1").rstrip("/")
        self._validate_api_url(self.api_base_url)
        self.pinned_public_key = configured_pin
        if self.pinned_public_key:
            try:
                if len(base64.b64decode(self.pinned_public_key, validate=True)) != 32:
                    raise ValueError("Invalid key size")
            except (ValueError, TypeError) as error:
                raise LicenceError("The configured licence public key is invalid.") from error
        elif urlparse(self.api_base_url).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise LicenceError("Production licence endpoints require a pinned public key in licence-config.json.")
        self.device_path = self.data_directory / "device.id"
        self.licence_path = self.data_directory / "licence.json"
        self.device_fingerprint = self._get_device_fingerprint()

    @staticmethod
    def _validate_api_url(api_base_url: str) -> None:
        parsed = urlparse(api_base_url)
        if parsed.scheme == "https" and parsed.hostname:
            return
        if parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
            return
        raise LicenceError("The licence service URL must use HTTPS. HTTP is allowed only for localhost.")

    def _get_device_fingerprint(self) -> str:
        self.data_directory.mkdir(parents=True, exist_ok=True)
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as machine_key:
                machine_guid, _ = winreg.QueryValueEx(machine_key, "MachineGuid")
            if isinstance(machine_guid, str) and machine_guid:
                return hashlib.sha256(f"scanora-search:{machine_guid}".encode("utf-8")).hexdigest()
        except (ImportError, OSError):
            pass

        try:
            installation_id = self.device_path.read_text(encoding="ascii").strip()
            if len(installation_id) != 64:
                raise ValueError("Invalid installation identifier")
        except (OSError, UnicodeError, ValueError):
            installation_id = secrets.token_hex(32)
            temporary_path = self.device_path.with_suffix(".tmp")
            temporary_path.write_text(installation_id, encoding="ascii")
            os.replace(temporary_path, self.device_path)
        return hashlib.sha256(f"scanora-search:{installation_id}".encode("ascii")).hexdigest()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self.api_base_url}/{path.lstrip('/')}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=8) as response:
                result = json.loads(response.read().decode("utf-8"))
        except (UnicodeError, ValueError) as error:
            raise LicenceError("The licence service returned invalid JSON.") from error
        except HTTPError as error:
            try:
                body = json.loads(error.read().decode("utf-8"))
                detail = body.get("detail", "Licence request was rejected.")
            except (ValueError, OSError, AttributeError):
                detail = "Licence request was rejected."
            raise LicenceError(str(detail)) from error
        except (URLError, TimeoutError, OSError) as error:
            raise LicenceServiceUnavailable("The licence service could not be reached.") from error
        if not isinstance(result, dict):
            raise LicenceError("The licence service returned an invalid response.")
        return result

    @staticmethod
    def _verify_signature(payload: dict[str, Any], signature: str, public_key: str) -> bool:
        try:
            key_bytes = base64.b64decode(public_key, validate=True)
            signature_bytes = base64.b64decode(signature, validate=True)
            Ed25519PublicKey.from_public_bytes(key_bytes).verify(signature_bytes, _canonical_payload(payload))
            return True
        except (ValueError, TypeError, InvalidSignature):
            return False

    def _verify_record(self, record: dict[str, Any]) -> bool:
        payload = record.get("payload")
        signature = record.get("signature")
        public_key = record.get("public_key")
        if not isinstance(payload, dict) or not isinstance(signature, str) or not isinstance(public_key, str):
            return False
        if not self._verify_signature(payload, signature, public_key):
            return False
        if self.pinned_public_key and public_key != self.pinned_public_key:
            return False
        if payload.get("status") != "ACTIVE" or payload.get("device_fingerprint") != self.device_fingerprint:
            return False
        try:
            today = date.today()
            starts = date.fromisoformat(payload["start_date"]) if payload.get("start_date") else None
            expires = date.fromisoformat(payload["expiry_date"])
            offline_until = datetime.fromisoformat(payload["offline_until"])
            licence_id = payload["licence_id"]
            return (
                isinstance(licence_id, int)
                and not isinstance(licence_id, bool)
                and licence_id > 0
                and (starts is None or starts <= today)
                and expires >= today
                and offline_until.tzinfo is not None
                and offline_until >= datetime.now(timezone.utc)
            )
        except (KeyError, TypeError, ValueError):
            return False

    def load_cached_licence(self) -> dict[str, Any] | None:
        try:
            record = json.loads(self.licence_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return record if isinstance(record, dict) and self._verify_record(record) else None

    def _accept_response(self, response: dict[str, Any], expected_public_key: str | None = None) -> dict[str, Any]:
        record = {
            "payload": response.get("payload"),
            "signature": response.get("signature"),
            "public_key": response.get("public_key"),
        }
        if expected_public_key and record["public_key"] != expected_public_key:
            raise LicenceError("The licence signing key changed. Contact the administrator.")
        if not self._verify_record(record):
            raise LicenceError("The licence response is invalid for this device.")
        self.data_directory.mkdir(parents=True, exist_ok=True)
        temporary_path = self.licence_path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
        os.replace(temporary_path, self.licence_path)
        return record

    def activate(self, product_key: str) -> dict[str, Any]:
        response = self._post(
            "licences/activate",
            {
                "product_key": product_key.strip(),
                "device_fingerprint": self.device_fingerprint,
                "device_name": os.environ.get("COMPUTERNAME"),
                "os_version": platform.platform(),
            },
        )
        return self._accept_response(response, self.pinned_public_key)

    def refresh(self) -> dict[str, Any]:
        cached = self.load_cached_licence()
        if cached is None:
            raise LicenceError("No valid local licence was found.")
        response = self._post(
            "licences/validate",
            {
                "licence_id": cached["payload"]["licence_id"],
                "device_fingerprint": self.device_fingerprint,
            },
        )
        return self._accept_response(response, cached["public_key"])