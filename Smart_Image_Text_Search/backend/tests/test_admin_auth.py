from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.security import get_password_hash
from app.database import SessionLocal, engine
from app.main import app
from app.models import AdminSession, AdminUser, Base

Base.metadata.create_all(bind=engine)

client = TestClient(app)


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def seed_admin_user(email: str = "admin@example.com", password: str = "StrongPass123!") -> AdminUser:
    db = SessionLocal()
    try:
        user = AdminUser(email=email, password_hash=get_password_hash(password), is_active=True)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def test_admin_login_and_dashboard() -> None:
    reset_db()
    seed_admin_user()

    response = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"

    dashboard = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {payload['access_token']}"},
    )
    assert dashboard.status_code == 200, dashboard.text
    data = dashboard.json()
    assert data["admin_email"] == "admin@example.com"
    assert data["dashboard"]["total_customers"] == 0


def test_admin_login_rejects_wrong_password() -> None:
    reset_db()
    seed_admin_user()

    response = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "WrongPassword123!"},
    )
    assert response.status_code == 401


def test_dashboard_requires_authentication() -> None:
    reset_db()

    response = client.get("/api/v1/admin/dashboard")
    assert response.status_code == 401


def test_logout_revokes_session() -> None:
    reset_db()
    seed_admin_user()

    login = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    token = login.json()["access_token"]

    logout = client.post(
        "/api/v1/admin/logout",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert logout.status_code == 200

    dashboard = client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert dashboard.status_code == 401


def test_logout_revokes_only_the_presented_session() -> None:
    reset_db()
    seed_admin_user()

    first_login = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    second_login = client.post(
        "/api/v1/admin/login",
        json={"email": "admin@example.com", "password": "StrongPass123!"},
    )
    first_token = first_login.json()["access_token"]
    second_token = second_login.json()["access_token"]

    logout = client.post(
        "/api/v1/admin/logout",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert logout.status_code == 200
    assert client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {first_token}"},
    ).status_code == 401
    assert client.get(
        "/api/v1/admin/dashboard",
        headers={"Authorization": f"Bearer {second_token}"},
    ).status_code == 200
