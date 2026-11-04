from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import Base, engine
from app.models import AdminUser


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_admin_user(db: Session) -> None:
    from app.core.config import settings
    from app.core.security import get_password_hash, verify_password

    admin_email = settings.admin_email.strip().lower()
    existing = (
        db.query(AdminUser)
        .filter(func.lower(AdminUser.email) == admin_email)
        .first()
    )

    if existing is not None:
        # Always synchronize password if changed in environment variables
        if not verify_password(settings.admin_password, existing.password_hash):
            existing.password_hash = get_password_hash(settings.admin_password)
            existing.is_active = True
            db.commit()
        return

    admin = AdminUser(
        email=settings.admin_email.strip(),
        password_hash=get_password_hash(settings.admin_password),
        is_active=True,
    )
    db.add(admin)
    db.commit()
