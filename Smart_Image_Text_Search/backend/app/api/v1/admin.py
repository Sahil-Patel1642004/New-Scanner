from __future__ import annotations

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_session_token, get_password_hash, verify_password
from app.dependencies import bearer_scheme, get_current_admin_user, get_db
from app.models import AdminSession, AdminUser
from app.schemas import AdminDashboardResponse, AdminLoginRequest, AdminSessionPayload, AdminSummary

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminSessionPayload)
def login_admin(payload: AdminLoginRequest, db: Session = Depends(get_db)) -> AdminSessionPayload:
    admin_user = db.query(AdminUser).filter(AdminUser.email == payload.email).first()
    if admin_user is None or not verify_password(payload.password, admin_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    token = generate_session_token()
    expires_at = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    session = AdminSession(
        id=token,
        admin_user_id=admin_user.id,
        expires_at=expires_at,
    )
    db.add(session)
    admin_user.last_login = datetime.utcnow()
    db.commit()

    return AdminSessionPayload(access_token=token, token_type="bearer", expires_at=expires_at)


@router.post("/logout")
def logout_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin_user),
) -> dict[str, str]:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    session = (
        db.query(AdminSession)
        .filter(AdminSession.id == credentials.credentials)
        .filter(AdminSession.admin_user_id == current_admin.id)
        .filter(AdminSession.revoked_at.is_(None))
        .first()
    )
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session.",
        )

    session.revoked_at = datetime.utcnow()
    db.commit()

    return {"status": "logged_out"}


@router.get("/dashboard", response_model=AdminDashboardResponse)
def dashboard(
    current_admin: AdminUser = Depends(get_current_admin_user),
) -> AdminDashboardResponse:
    return AdminDashboardResponse(
        admin_email=current_admin.email,
        dashboard=AdminSummary(
            total_customers=0,
            total_licences=0,
            active_licences=0,
            inactive_licences=0,
            unused_product_keys=0,
            expired_licences=0,
            disabled_licences=0,
            revoked_licences=0,
            total_activated_devices=0,
            emails_sent=0,
            failed_email_deliveries=0,
        ),
    )


def create_initial_admin_user(db: Session) -> AdminUser | None:
    existing = db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first()
    if existing is not None:
        return existing

    if settings.environment == "production":
        return None

    password_hash = get_password_hash(settings.admin_password)
    admin_user = AdminUser(email=settings.admin_email, password_hash=password_hash, is_active=True)
    db.add(admin_user)
    db.commit()
    db.refresh(admin_user)
    return admin_user
