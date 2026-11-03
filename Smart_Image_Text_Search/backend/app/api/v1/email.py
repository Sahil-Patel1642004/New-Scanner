from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin_user, get_db
from app.models import AdminUser, EmailLog
from app.schemas import EmailLogRead

router = APIRouter(tags=["email"])


@router.get("/email-logs", response_model=list[EmailLogRead])
def list_email_logs(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> list[EmailLogRead]:
    logs = db.query(EmailLog).order_by(EmailLog.created_at.desc()).all()
    return [EmailLogRead.model_validate(log) for log in logs]
