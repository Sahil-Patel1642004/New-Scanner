import base64
import json
from datetime import date, datetime, timedelta, timezone

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app.scanora_licensing.client import LicenceClient, LicenceError


def _signed_record(client: LicenceClient, expiry_date: date) -> dict:
    payload = {
        "licence_id": 9,
        "product_id": 1,
        "device_fingerprint": client.device_fingerprint,
        "start_date": date.today().isoformat(),
        "expiry_date": expiry_date.isoformat(),
        "offline_until": (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
        "max_devices": 1,
        "status": "ACTIVE",
    }
    private_key = Ed25519PrivateKey.generate()
    signature = private_key.sign(
        json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode("utf-8")
    )
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return {
        "payload": payload,
        "signature": base64.b64encode(signature).decode("ascii"),
        "public_key": base64.b64encode(public_key).decode("ascii"),
    }


def test_cached_entitlement_requires_valid_signature_device_and_dates(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.scanora_licensing.client._data_directory", lambda: tmp_path)
    client = LicenceClient("http://localhost:8000/api/v1")
    record = _signed_record(client, date.today() + timedelta(days=1))

    assert client._verify_record(record)

    tampered = dict(record, payload=dict(record["payload"], device_fingerprint="other-device"))
    assert not client._verify_record(tampered)

    expired = _signed_record(client, date.today() - timedelta(days=1))
    assert not client._verify_record(expired)

    offline_expired = _signed_record(client, date.today() + timedelta(days=1))
    offline_expired["payload"]["offline_until"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    assert not client._verify_record(offline_expired)


def test_non_local_http_licence_service_is_rejected() -> None:
    try:
        LicenceClient("http://license.example.com/api/v1")
    except LicenceError as error:
        assert "HTTPS" in str(error)
    else:
        raise AssertionError("Non-local HTTP licence endpoints must be rejected")


def test_remote_endpoint_requires_and_enforces_pinned_signing_key(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.scanora_licensing.client._data_directory", lambda: tmp_path)
    monkeypatch.delenv("SCANORA_LICENCE_PUBLIC_KEY", raising=False)
    try:
        LicenceClient("https://license.example.com/api/v1")
    except LicenceError as error:
        assert "pinned public key" in str(error)
    else:
        raise AssertionError("Remote licence endpoints must require a pinned public key")

    record_client = LicenceClient("http://localhost:8000/api/v1")
    record = _signed_record(record_client, date.today() + timedelta(days=1))
    monkeypatch.setenv("SCANORA_LICENCE_PUBLIC_KEY", record["public_key"])
    pinned_client = LicenceClient("https://license.example.com/api/v1")
    assert pinned_client._verify_record(record)

    wrong_key = base64.b64encode(Ed25519PrivateKey.generate().public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )).decode("ascii")
    monkeypatch.setenv("SCANORA_LICENCE_PUBLIC_KEY", wrong_key)
    wrong_pin_client = LicenceClient("https://license.example.com/api/v1")
    assert not wrong_pin_client._verify_record(record)


def test_loads_remote_endpoint_and_pinned_key_from_local_config(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.scanora_licensing.client._data_directory", lambda: tmp_path)
    monkeypatch.delenv("SCANORA_LICENCE_API_URL", raising=False)
    monkeypatch.delenv("SCANORA_LICENCE_PUBLIC_KEY", raising=False)
    dev_client = LicenceClient("http://localhost:8000/api/v1")
    record = _signed_record(dev_client, date.today() + timedelta(days=1))
    (tmp_path / "licence-config.json").write_text(
        json.dumps({"api_base_url": "https://license.example.com/api/v1", "public_key": record["public_key"]}),
        encoding="utf-8",
    )

    client = LicenceClient()

    assert client.api_base_url == "https://license.example.com/api/v1"
    assert client.pinned_public_key == record["public_key"]
    assert client._verify_record(record)