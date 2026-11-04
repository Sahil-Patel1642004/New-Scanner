from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_session_token, get_password_hash, verify_password
from app.dependencies import bearer_scheme, get_current_admin_user, get_db
from app.models import AdminSession, AdminUser, Customer, DeviceActivation, EmailLog, Licence
from app.schemas import AdminDashboardResponse, AdminLoginRequest, AdminSessionPayload, AdminSummary

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminSessionPayload)
def login_admin(payload: AdminLoginRequest, db: Session = Depends(get_db)) -> AdminSessionPayload:
    clean_email = payload.email.strip().lower()
    admin_user = db.query(AdminUser).filter(func.lower(AdminUser.email) == clean_email).first()
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
    db: Session = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin_user),
) -> AdminDashboardResponse:
    today = date.today()
    total_customers = db.query(Customer).count()
    total_licences = db.query(Licence).count()
    active_licences = (
        db.query(Licence)
        .filter(Licence.is_enabled.is_(True))
        .filter(Licence.is_revoked.is_(False))
        .filter(Licence.expiry_date >= today)
        .count()
    )
    expired_licences = (
        db.query(Licence)
        .filter(Licence.expiry_date < today)
        .count()
    )
    disabled_licences = (
        db.query(Licence)
        .filter(Licence.is_enabled.is_(False))
        .filter(Licence.is_revoked.is_(False))
        .count()
    )
    revoked_licences = (
        db.query(Licence)
        .filter(Licence.is_revoked.is_(True))
        .count()
    )
    total_devices = db.query(DeviceActivation).filter(DeviceActivation.status == "ACTIVE").count()
    emails_sent = db.query(EmailLog).filter(EmailLog.status.in_(["SENT", "ACCEPTED"])).count()
    failed_emails = db.query(EmailLog).filter(EmailLog.status == "FAILED").count()
    unused_keys = db.query(Licence).filter(Licence.status == "UNUSED").count()
    inactive_licences = total_licences - active_licences

    return AdminDashboardResponse(
        admin_email=current_admin.email,
        dashboard=AdminSummary(
            total_customers=total_customers,
            total_licences=total_licences,
            active_licences=active_licences,
            inactive_licences=inactive_licences,
            unused_product_keys=unused_keys,
            expired_licences=expired_licences,
            disabled_licences=disabled_licences,
            revoked_licences=revoked_licences,
            total_activated_devices=total_devices,
            emails_sent=emails_sent,
            failed_email_deliveries=failed_emails,
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
