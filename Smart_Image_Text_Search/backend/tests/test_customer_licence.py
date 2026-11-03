from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.security import get_password_hash, sign_licence_payload, verify_licence_signature
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import AdminUser, Customer, Product, Licence

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

client = TestClient(app)


def seed_admin() -> str:
    db = SessionLocal()
    user = AdminUser(email="admin@example.com", password_hash=get_password_hash("StrongPass123!"), is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    login = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    return login.json()["access_token"]


def seed_product() -> Product:
    db = SessionLocal()
    product = db.query(Product).filter(Product.name == "Prakshal-Scanora Search").first()
    if product is None:
        product = Product(name="Prakshal-Scanora Search", sku="SCANORA-SEARCH", description="Desktop search licensing product")
        db.add(product)
        db.commit()
        db.refresh(product)
    db.close()
    return product


def test_customer_creation_and_listing() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    token = seed_admin()
    response = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Riya Patel",
            "email": "riya@example.com",
            "phone": "+919999999999",
            "company_name": "Example Labs",
            "order_reference": "ORD-1001",
        },
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["name"] == "Riya Patel"

    listing = client.get("/api/v1/customers", headers={"Authorization": f"Bearer {token}"})
    assert listing.status_code == 200, listing.text
    assert listing.json()[0]["email"] == "riya@example.com"


def test_admin_can_create_and_list_products() -> None:
    token = seed_admin()
    headers = {"Authorization": f"Bearer {token}"}
    created = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Prakshal Search", "sku": "SEARCH-001", "description": "Desktop search app"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["sku"] == "SEARCH-001"

    listing = client.get("/api/v1/products", headers=headers)
    assert listing.status_code == 200, listing.text
    assert [product["id"] for product in listing.json()] == [created.json()["id"]]

    duplicate = client.post(
        "/api/v1/products",
        headers=headers,
        json={"name": "Different name", "sku": "SEARCH-001"},
    )
    assert duplicate.status_code == 409


def test_admin_can_disable_and_irreversibly_revoke_licence() -> None:
    token = seed_admin()
    product = seed_product()
    customer = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Lifecycle User", "email": "lifecycle@example.com"},
    )
    created = client.post(
        "/api/v1/licences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_id": customer.json()["id"],
            "product_id": product.id,
            "licence_type": "ANNUAL",
            "issue_date": "2026-11-02",
            "expiry_date": "2027-11-02",
            "max_devices": 1,
        },
    )
    licence_id = created.json()["id"]
    headers = {"Authorization": f"Bearer {token}"}

    disabled = client.patch(f"/api/v1/licences/{licence_id}", headers=headers, json={"is_enabled": False})
    assert disabled.status_code == 200, disabled.text
    assert disabled.json()["status"] == "DISABLED"
    assert disabled.json()["is_enabled"] is False

    enabled = client.patch(f"/api/v1/licences/{licence_id}", headers=headers, json={"is_enabled": True})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["status"] == "UNUSED"

    null_limit = client.patch(f"/api/v1/licences/{licence_id}", headers=headers, json={"max_devices": None})
    assert null_limit.status_code == 400

    revoked = client.patch(f"/api/v1/licences/{licence_id}", headers=headers, json={"is_revoked": True})
    assert revoked.status_code == 200, revoked.text
    assert revoked.json()["status"] == "REVOKED"
    assert revoked.json()["is_revoked"] is True

    restore = client.patch(f"/api/v1/licences/{licence_id}", headers=headers, json={"is_revoked": False})
    assert restore.status_code == 409


def test_licence_creation_generates_hash_and_key() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    token = seed_admin()
    seed_product()

    customer_response = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "John Doe",
            "email": "john@example.com",
            "company_name": "Acme",
        },
    )
    customer_id = customer_response.json()["id"]

    response = client.post(
        "/api/v1/licences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_id": customer_id,
            "product_id": 1,
            "licence_type": "ONE_YEAR",
            "issue_date": "2026-11-02",
            "expiry_date": "2027-11-02",
            "max_devices": 1,
            "notes": "Customer project licence",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "product_key" in payload
    assert payload["product_key"].startswith("SCANORA-")
    assert payload["masked_product_key"] != payload["product_key"]
    assert payload["email_delivery_status"] == "mock"
    assert payload["email_recipient"] == "john@example.com"

    revealed = client.get(
        f"/api/v1/licences/{payload['id']}/product-key",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert revealed.status_code == 200, revealed.text
    assert revealed.json()["product_key"] == payload["product_key"]

    unauthorized_reveal = client.get(f"/api/v1/licences/{payload['id']}/product-key")
    assert unauthorized_reveal.status_code == 401

    stored = client.get(f"/api/v1/licences/{payload['id']}", headers={"Authorization": f"Bearer {token}"})
    assert stored.status_code == 200, stored.text
    assert stored.json()["masked_product_key"].startswith("SCANORA-")


def test_licence_activation_binds_device_and_enforces_limits() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    token = seed_admin()
    seed_product()

    customer_response = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Device User",
            "email": "device@example.com",
            "company_name": "Acme",
        },
    )
    customer_id = customer_response.json()["id"]

    licence_response = client.post(
        "/api/v1/licences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_id": customer_id,
            "product_id": 1,
            "licence_type": "ONE_YEAR",
            "issue_date": "2026-11-02",
            "expiry_date": "2027-11-02",
            "max_devices": 1,
        },
    )
    product_key = licence_response.json()["product_key"]
    licence_id = licence_response.json()["id"]

    first_activation = client.post(
        f"/api/v1/licences/{licence_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "product_key": product_key,
            "device_fingerprint": "device-1",
            "device_name": "Windows Laptop",
            "os_version": "Windows 11",
        },
    )
    assert first_activation.status_code == 200, first_activation.text
    assert first_activation.json()["activation_state"] == "ACTIVE"

    duplicate_activation = client.post(
        f"/api/v1/licences/{licence_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "product_key": product_key,
            "device_fingerprint": "device-1",
            "device_name": "Windows Laptop",
            "os_version": "Windows 11",
        },
    )
    assert duplicate_activation.status_code == 200, duplicate_activation.text
    assert duplicate_activation.json()["status"] == "already_active"

    bad_key = client.post(
        f"/api/v1/licences/{licence_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "product_key": "SCANORA-INVALID-KEY-9999",
            "device_fingerprint": "device-2",
        },
    )
    assert bad_key.status_code == 401, bad_key.text


def test_licence_signing_and_verification() -> None:
    payload = {
        "licence_id": 42,
        "customer_email": "customer@example.com",
        "product_key": "SCANORA-ABCD-EFGH-IJKL-MNOP",
        "device_fingerprint": "device-1",
        "expiry_date": "2027-11-02",
        "max_devices": 1,
    }

    signed = sign_licence_payload(payload)
    assert signed["signature"]
    assert verify_licence_signature(payload, signed["signature"], signed["public_key"]) is True

    tampered = dict(payload)
    tampered["device_fingerprint"] = "device-2"
    assert verify_licence_signature(tampered, signed["signature"], signed["public_key"]) is False


def test_public_licence_activation_returns_signed_device_entitlement() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    token = seed_admin()
    seed_product()

    customer_response = client.post(
        "/api/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "Desktop User", "email": "desktop@example.com"},
    )
    licence_response = client.post(
        "/api/v1/licences",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "customer_id": customer_response.json()["id"],
            "product_id": 1,
            "licence_type": "ONE_YEAR",
            "issue_date": "2026-11-02",
            "expiry_date": "2027-11-02",
            "max_devices": 1,
        },
    )
    product_key = licence_response.json()["product_key"]

    activation = client.post(
        "/api/v1/licences/activate",
        json={"product_key": product_key, "device_fingerprint": "desktop-device-1"},
    )

    assert activation.status_code == 200, activation.text
    response = activation.json()
    assert response["status"] == "activated"
    assert response["payload"]["device_fingerprint"] == "desktop-device-1"
    assert verify_licence_signature(response["payload"], response["signature"], response["public_key"])

    validation = client.post(
        "/api/v1/licences/validate",
        json={
            "licence_id": response["payload"]["licence_id"],
            "device_fingerprint": "desktop-device-1",
        },
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["status"] == "validated"
    assert verify_licence_signature(
        validation.json()["payload"],
        validation.json()["signature"],
        validation.json()["public_key"],
    )

    wrong_device = client.post(
        "/api/v1/licences/validate",
        json={
            "licence_id": response["payload"]["licence_id"],
            "device_fingerprint": "different-device-1",
        },
    )
    assert wrong_device.status_code == 401

    tampered_payload = dict(response["payload"], device_fingerprint="another-device")
    assert not verify_licence_signature(tampered_payload, response["signature"], response["public_key"])

    bad_key = client.post(
        "/api/v1/licences/activate",
        json={"product_key": "SCANORA-INVALID-KEY-9999", "device_fingerprint": "desktop-device-2"},
    )
    assert bad_key.status_code == 401
