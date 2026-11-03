from __future__ import annotations

from sqlalchemy.orm import Session

from app.database import Base, engine
from app.models import AdminUser


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)


def ensure_admin_user(db: Session) -> None:
    from app.core.config import settings
    from app.core.security import get_password_hash

    existing = db.query(AdminUser).filter(AdminUser.email == settings.admin_email).first()
    if existing is not None:
        return

    admin = AdminUser(
        email=settings.admin_email,
        password_hash=get_password_hash(settings.admin_password),
        is_active=True,
    )
    db.add(admin)
    db.commit()
