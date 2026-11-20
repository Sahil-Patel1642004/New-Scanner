from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin_user, get_db
from app.email_delivery import EmailDeliveryError, send_test_email
from app.models import AdminUser, EmailLog
from app.schemas import EmailLogRead

router = APIRouter(tags=["email"])


class TestEmailRequest(BaseModel):
    recipient: EmailStr


@router.post("/email-logs/test")
def send_test_email_endpoint(
    payload: TestEmailRequest,
    _: AdminUser = Depends(get_current_admin_user),
) -> dict[str, str]:
    try:
        message_id, subject, sent_at = send_test_email(str(payload.recipient))
    except EmailDeliveryError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error)) from error
    return {
        "status": "sent",
        "recipient": str(payload.recipient),
        "subject": subject,
        "message_id": message_id,
        "sent_at": sent_at,
    }


@router.get("/email-logs", response_model=list[EmailLogRead])
def list_email_logs(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> list[EmailLogRead]:
    logs = db.query(EmailLog).order_by(EmailLog.created_at.desc()).all()
    return [EmailLogRead.model_validate(log) for log in logs]
