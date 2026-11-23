from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.core.config import settings
from app.email_delivery import EmailDeliveryError, send_activation_limit_notice, send_licence_email

from app.core.security import (
    decrypt_product_key,
    encrypt_product_key,
    generate_product_key,
    get_licence_signing_public_key,
    hash_product_key,
    mask_product_key,
    sign_licence_payload,
    verify_licence_signature,
)
from app.dependencies import get_current_admin_user, get_db
from app.models import AdminUser, Customer, DeviceActivation, EmailLog, Licence, Product
from app.database import SessionLocal
from app.schemas import (
    LicenceActivationRequest,
    LicenceActivationResponse,
    LicenceCreate,
    LicenceRead,
    LicenceReadDetail,
    LicenceSignatureVerificationRequest,
    LicenceSignatureVerificationResponse,
    LicenceUpdate,
    LicenceValidationRequest,
    SignedLicenceActivationResponse,
)

router = APIRouter(prefix="/licences", tags=["licences"])
logger = logging.getLogger(__name__)


def _send_licence_email_in_background(
    email_log_id: int,
    recipient: str,
    customer_name: str,
    product_name: str,
    licence_type: str,
    product_key: str,
    start_date: date,
    expiry_date: date,
) -> None:
    logger.info("Starting background licence email delivery (log_id=%s).", email_log_id)
    db = SessionLocal()
    try:
        email_log = db.query(EmailLog).filter(EmailLog.id == email_log_id).first()
        if email_log is None:
            return
        try:
            provider_message_id, _, _ = send_licence_email(
                recipient=recipient,
                customer_name=customer_name,
                product_name=product_name,
                licence_type=licence_type,
                product_key=product_key,
                start_date=start_date,
                expiry_date=expiry_date,
            )
            email_log.status = "SENT"
            email_log.provider_message_id = provider_message_id
            email_log.sent_at = datetime.utcnow()
            email_log.last_error = None
            logger.info("Licence email accepted by SMTP (log_id=%s).", email_log_id)
        except EmailDeliveryError as error:
            email_log.status = "FAILED"
            email_log.failed_at = datetime.utcnow()
            email_log.last_error = str(error)[:1000]
            logger.warning("Licence email failed (log_id=%s): %s", email_log_id, error)
        except Exception as error:
            email_log.status = "FAILED"
            email_log.failed_at = datetime.utcnow()
            email_log.last_error = f"Unexpected email error ({type(error).__name__})."
            logger.exception("Unexpected licence email error (log_id=%s).", email_log_id)
        db.commit()
    except Exception:
        logger.exception("Could not update licence email status (log_id=%s).", email_log_id)
        raise
    finally:
        db.close()


def _send_activation_limit_notice_in_background(email_log_id: int, recipient: str, customer_name: str, product_name: str) -> None:
    db = SessionLocal()
    try:
        email_log = db.query(EmailLog).filter(EmailLog.id == email_log_id).first()
        if email_log is None:
            return
        try:
            provider_message_id, _, _ = send_activation_limit_notice(recipient, customer_name, product_name)
            email_log.status = "SENT"
            email_log.provider_message_id = provider_message_id
            email_log.sent_at = datetime.utcnow()
            email_log.last_error = None
        except EmailDeliveryError as error:
            email_log.status = "FAILED"
            email_log.failed_at = datetime.utcnow()
            email_log.last_error = str(error)[:1000]
            logger.warning("Activation limit email failed (log_id=%s): %s", email_log_id, error)
        except Exception as error:
            email_log.status = "FAILED"
            email_log.failed_at = datetime.utcnow()
            email_log.last_error = f"Unexpected email error ({type(error).__name__})."
            logger.exception("Unexpected activation limit email error (log_id=%s).", email_log_id)
        db.commit()
    except Exception:
        logger.exception("Could not update activation limit email status (log_id=%s).", email_log_id)
        raise
    finally:
        db.close()


def _activate_licence_for_device(
    licence: Licence,
    payload: LicenceActivationRequest,
    db: Session,
    background_tasks: BackgroundTasks | None = None,
) -> LicenceActivationResponse | None:
    if licence.is_revoked or not licence.is_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Licence is disabled or revoked.")

    if not licence.product.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product is disabled.")

    if licence.start_date is not None and licence.start_date > date.today():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Licence is not active yet.")

    if licence.expiry_date < date.today():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Licence has expired.")

    if hash_product_key(payload.product_key) != licence.product_key_hash:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid product key.")

    existing_activations = db.query(DeviceActivation).filter(DeviceActivation.licence_id == licence.id).all()
    existing = next(
        (activation for activation in existing_activations if activation.device_fingerprint == payload.device_fingerprint),
        None,
    )
    if existing is not None:
        licence.status = "ACTIVE"
        licence.activation_state = "ACTIVE"
        licence.activated_at = licence.activated_at or datetime.utcnow()
        db.commit()
        return LicenceActivationResponse(
            status="already_active",
            licence_id=licence.id,
            device_fingerprint=payload.device_fingerprint,
            activation_state=licence.activation_state,
            active_devices=len(existing_activations),
            max_devices=licence.max_devices,
            remaining_devices=max(licence.max_devices - len(existing_activations), 0),
            message="This device is already activated for this licence.",
        )

    if len(existing_activations) >= licence.max_devices:
        if background_tasks is not None:
            subject = f"Activation limit reached for {licence.product.name}"
            email_log = EmailLog(
                licence_id=licence.id,
                customer_id=licence.customer_id,
                recipient=licence.customer.email,
                subject=subject,
                status="QUEUED",
            )
            db.add(email_log)
            db.commit()
            db.refresh(email_log)
            background_tasks.add_task(
                _send_activation_limit_notice_in_background,
                email_log.id,
                licence.customer.email,
                licence.customer.name,
                licence.product.name,
            )
            return None
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Maximum device activation limit reached.")

    activation = DeviceActivation(
        licence_id=licence.id,
        device_fingerprint=payload.device_fingerprint,
        device_name=payload.device_name,
        os_version=payload.os_version,
        user_agent=None,
        status="ACTIVE",
    )
    db.add(activation)
    licence.status = "ACTIVE"
    licence.activation_state = "ACTIVE"
    licence.activated_at = licence.activated_at or datetime.utcnow()
    db.commit()

    active_count = len(existing_activations) + 1
    return LicenceActivationResponse(
        status="activated",
        licence_id=licence.id,
        device_fingerprint=payload.device_fingerprint,
        activation_state=licence.activation_state,
        active_devices=active_count,
        max_devices=licence.max_devices,
        remaining_devices=max(licence.max_devices - active_count, 0),
        message="Licence activated successfully.",
    )


@router.post("", response_model=LicenceReadDetail)
def create_licence(
    payload: LicenceCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> LicenceReadDetail:
    customer = db.query(Customer).filter(Customer.id == payload.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    product = db.query(Product).filter(Product.id == payload.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    effective_start = payload.start_date or payload.issue_date
    if payload.expiry_date < payload.issue_date or payload.expiry_date < effective_start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expiry date cannot be before the issue or start date.")

    key = generate_product_key()
    while db.query(Licence).filter(Licence.product_key_hash == hash_product_key(key)).first():
        key = generate_product_key()

    licence = Licence(
        customer_id=payload.customer_id,
        product_id=payload.product_id,
        licence_type=payload.licence_type,
        issue_date=payload.issue_date,
        expiry_date=payload.expiry_date,
        start_date=effective_start,
        max_devices=payload.max_devices or 1,
        notes=payload.notes,
        product_key_hash=hash_product_key(key),
        product_key_ciphertext=encrypt_product_key(key),
        product_key_preview=mask_product_key(key),
        status="UNUSED",
        activation_state="UNUSED",
        administrative_state="ENABLED",
        expiry_state="VALID",
    )
    db.add(licence)
    db.commit()
    db.refresh(licence)
    email_log = EmailLog(
        licence_id=licence.id,
        customer_id=customer.id,
        recipient=customer.email,
        subject=f"Your {product.name} licence and installer are ready",
        status="QUEUED",
    )
    db.add(email_log)
    db.commit()
    db.refresh(email_log)
    background_tasks.add_task(
        _send_licence_email_in_background,
        email_log.id,
        customer.email,
        customer.name,
        product.name,
        licence.licence_type,
        key,
        licence.start_date or licence.issue_date,
        licence.expiry_date,
    )
    return LicenceReadDetail(
        id=licence.id,
        customer_id=licence.customer_id,
        product_id=licence.product_id,
        licence_type=licence.licence_type,
        issue_date=licence.issue_date,
        expiry_date=licence.expiry_date,
        status=licence.status,
        start_date=licence.start_date,
        max_devices=licence.max_devices,
        masked_product_key=licence.product_key_preview,
        product_key=key,
        notes=licence.notes,
        email_delivery_status=email_log.status.lower(),
        email_recipient=email_log.recipient,
        email_log_id=email_log.id,
    )


@router.get("", response_model=list[LicenceRead])
def list_licences(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> list[LicenceRead]:
    licences = db.query(Licence).order_by(Licence.created_at.desc()).all()
    return [LicenceRead.model_validate(licence) for licence in licences]


@router.get("/{licence_id}", response_model=LicenceReadDetail)
def get_licence(
    licence_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> LicenceReadDetail:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")
    return LicenceReadDetail(
        id=licence.id,
        customer_id=licence.customer_id,
        product_id=licence.product_id,
        licence_type=licence.licence_type,
        issue_date=licence.issue_date,
        expiry_date=licence.expiry_date,
        status=licence.status,
        start_date=licence.start_date,
        max_devices=licence.max_devices,
        masked_product_key=licence.product_key_preview,
        notes=licence.notes,
    )


@router.get("/{licence_id}/product-key")
def get_licence_product_key(
    licence_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> dict[str, str]:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")
    return {"product_key": decrypt_product_key(licence.product_key_ciphertext)}


@router.patch("/{licence_id}", response_model=LicenceRead)
def update_licence(
    licence_id: int,
    payload: LicenceUpdate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> LicenceRead:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")

    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No licence changes were provided.")
    if "is_revoked" in changes and changes["is_revoked"] is False and licence.is_revoked:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A revoked licence cannot be restored.")
    if changes.get("is_revoked") is True:
        changes["is_enabled"] = False

    for field in ("start_date", "expiry_date"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} cannot be cleared.")
    for field in ("max_devices", "is_enabled", "is_revoked"):
        if field in changes and changes[field] is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field} cannot be null.")

    start_date = changes.get("start_date", licence.start_date or licence.issue_date)
    expiry_date = changes.get("expiry_date", licence.expiry_date)
    if expiry_date < start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Expiry date cannot be before start date.")

    max_devices = changes.get("max_devices", licence.max_devices)
    active_device_count = (
        db.query(DeviceActivation)
        .filter(DeviceActivation.licence_id == licence.id, DeviceActivation.status == "ACTIVE")
        .count()
    )
    if max_devices < active_device_count:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Device limit cannot be lower than active devices.")

    for field, value in changes.items():
        if field not in {"is_revoked"}:
            setattr(licence, field, value)
    if changes.get("is_revoked") is True:
        licence.is_revoked = True

    if licence.is_revoked:
        licence.is_enabled = False
        licence.administrative_state = "REVOKED"
        licence.status = "REVOKED"
        for activation in licence.device_activations:
            activation.status = "REVOKED"
    elif not licence.is_enabled:
        licence.administrative_state = "DISABLED"
        licence.status = "DISABLED"
    else:
        licence.administrative_state = "ENABLED"
        if licence.expiry_date < date.today():
            licence.expiry_state = "EXPIRED"
            licence.status = "EXPIRED"
        else:
            licence.expiry_state = "VALID"
            active_count = (
                db.query(DeviceActivation)
                .filter(DeviceActivation.licence_id == licence.id, DeviceActivation.status == "ACTIVE")
                .count()
            )
            licence.status = "ACTIVE" if active_count else "UNUSED"

    db.commit()
    db.refresh(licence)
    return LicenceRead.model_validate(licence)


@router.post("/{licence_id}/activate", response_model=LicenceActivationResponse)
def activate_licence(
    licence_id: int,
    payload: LicenceActivationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> LicenceActivationResponse | JSONResponse:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")

    activation = _activate_licence_for_device(licence, payload, db, background_tasks)
    if activation is None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Maximum device activation limit reached."},
            background=background_tasks,
        )
    return activation


@router.post("/activate", response_model=SignedLicenceActivationResponse)
def activate_licence_with_key(
    payload: LicenceActivationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SignedLicenceActivationResponse | JSONResponse:
    licence = db.query(Licence).filter(Licence.product_key_hash == hash_product_key(payload.product_key)).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid product key.")

    activation = _activate_licence_for_device(licence, payload, db, background_tasks)
    if activation is None:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": "Maximum device activation limit reached."},
            background=background_tasks,
        )
    entitlement: dict[str, str | int | bool | None] = {
        "licence_id": licence.id,
        "product_id": licence.product_id,
        "device_fingerprint": payload.device_fingerprint,
        "start_date": licence.start_date.isoformat() if licence.start_date else None,
        "expiry_date": licence.expiry_date.isoformat(),
        "max_devices": licence.max_devices,
        "status": licence.status,
        "offline_until": (
            datetime.now(timezone.utc) + timedelta(hours=settings.licence_offline_grace_hours)
        ).isoformat(),
    }
    signed = sign_licence_payload(entitlement)
    return SignedLicenceActivationResponse(
        status=activation.status,
        message=activation.message,
        payload=entitlement,
        signature=signed["signature"],
        public_key=signed["public_key"],
    )


@router.post("/validate", response_model=SignedLicenceActivationResponse)
def validate_licence_for_device(
    payload: LicenceValidationRequest,
    db: Session = Depends(get_db),
) -> SignedLicenceActivationResponse:
    licence = db.query(Licence).filter(Licence.id == payload.licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")

    if licence.is_revoked or not licence.is_enabled or not licence.product.is_active:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Licence is disabled or revoked.")
    if licence.start_date is not None and licence.start_date > date.today():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Licence is not active yet.")
    if licence.expiry_date < date.today():
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Licence has expired.")

    activation = (
        db.query(DeviceActivation)
        .filter(
            DeviceActivation.licence_id == licence.id,
            DeviceActivation.device_fingerprint == payload.device_fingerprint,
            DeviceActivation.status == "ACTIVE",
        )
        .first()
    )
    if activation is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="This device is not activated.")

    entitlement: dict[str, str | int | bool | None] = {
        "licence_id": licence.id,
        "product_id": licence.product_id,
        "device_fingerprint": payload.device_fingerprint,
        "start_date": licence.start_date.isoformat() if licence.start_date else None,
        "expiry_date": licence.expiry_date.isoformat(),
        "max_devices": licence.max_devices,
        "status": licence.status,
        "offline_until": (
            datetime.now(timezone.utc) + timedelta(hours=settings.licence_offline_grace_hours)
        ).isoformat(),
    }
    signed = sign_licence_payload(entitlement)
    return SignedLicenceActivationResponse(
        status="validated",
        message="Licence is valid for this device.",
        payload=entitlement,
        signature=signed["signature"],
        public_key=signed["public_key"],
    )


@router.get("/{licence_id}/signing-public-key")
def get_licence_signing_public_key(
    licence_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> dict[str, str]:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")
    return {"public_key": get_licence_signing_public_key()}


@router.post("/{licence_id}/verify-signature", response_model=LicenceSignatureVerificationResponse)
def verify_licence_signature_endpoint(
    licence_id: int,
    payload: LicenceSignatureVerificationRequest,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> LicenceSignatureVerificationResponse:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")

    valid = verify_licence_signature(payload.payload, payload.signature, payload.public_key)
    if not valid:
        return LicenceSignatureVerificationResponse(valid=False, message="Signature verification failed.", licence_id=licence.id)

    return LicenceSignatureVerificationResponse(valid=True, message="Signature verified successfully.", licence_id=licence.id)


