from __future__ import annotations

import html
import os
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.config import settings
from app.email_delivery import EmailDeliveryError, send_email

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
from app.schemas import (
    EmailLogRead,
    EmailSendResponse,
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


def _deliver_licence_email(
    db: Session,
    licence: Licence,
    customer: Customer,
    product: Product,
) -> EmailLog:
    actual_key = decrypt_product_key(licence.product_key_ciphertext)
    subject = "Your Prakshal-Scanora Search Licence"
    text_body = (
        f"Dear {customer.name},\n\n"
        f"Thank you for purchasing {product.name}.\n\n"
        f"Product: {product.name}\n"
        f"Product Key: {actual_key}\n"
        f"Licence Type: {licence.licence_type}\n"
        f"Start Date: {licence.start_date or licence.issue_date}\n"
        f"Expiry Date: {licence.expiry_date}\n\n"
        "Installation instructions:\n"
        "1. Download and install Scanora.\n"
        "2. Open the application.\n"
        "3. Enter your product key.\n"
        "4. Click Activate.\n"
        "5. Start using Scanora after successful activation.\n"
    )
    # Build download link for the installer (served by /api/v1/download/installer)
    download_url = f"{settings.public_base_url}/api/v1/download/installer"

    text_body += (
        f"\nDownload the installer here:\n"
        f"{download_url}\n"
    )
    safe_text = html.escape(text_body)
    link_html = (
        f'<br><br><strong>Download the installer:</strong><br>'
        f'<a href="{download_url}">{download_url}</a>'
    )
    html_body = safe_text.replace("\n", "<br>\n") + link_html
    try:
        provider_message_id = send_email(
            customer.email,
            subject,
            text_body,
            html_body,
        )
    except EmailDeliveryError as error:
        email_log = EmailLog(
            licence_id=licence.id,
            customer_id=customer.id,
            recipient=customer.email,
            subject=subject,
            status="FAILED",
            retry_count=0,
            failed_at=datetime.utcnow(),
            last_error=str(error)[:1000],
        )
    else:
        is_mock = settings.email_provider == "mock"
        email_log = EmailLog(
            licence_id=licence.id,
            customer_id=customer.id,
            recipient=customer.email,
            subject=subject,
            status="MOCK" if is_mock else "ACCEPTED",
            provider_message_id=provider_message_id,
            retry_count=0,
            sent_at=datetime.utcnow(),
        )
    db.add(email_log)
    db.commit()
    db.refresh(email_log)
    return email_log


def _activate_licence_for_device(
    licence: Licence,
    payload: LicenceActivationRequest,
    db: Session,
) -> LicenceActivationResponse:
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
    email_log = _deliver_licence_email(db, licence, customer, product)

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
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> LicenceActivationResponse:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")

    return _activate_licence_for_device(licence, payload, db)


@router.post("/activate", response_model=SignedLicenceActivationResponse)
def activate_licence_with_key(
    payload: LicenceActivationRequest,
    db: Session = Depends(get_db),
) -> SignedLicenceActivationResponse:
    licence = db.query(Licence).filter(Licence.product_key_hash == hash_product_key(payload.product_key)).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid product key.")

    activation = _activate_licence_for_device(licence, payload, db)
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


@router.post("/{licence_id}/send-email", response_model=EmailSendResponse)
def send_licence_email(
    licence_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> EmailSendResponse:
    licence = db.query(Licence).filter(Licence.id == licence_id).first()
    if licence is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Licence not found.")

    customer = db.query(Customer).filter(Customer.id == licence.customer_id).first()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")

    product = db.query(Product).filter(Product.id == licence.product_id).first()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")

    email_log = _deliver_licence_email(db, licence, customer, product)
    if email_log.status == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Email delivery failed. {email_log.last_error or 'The failure was recorded.'}",
        )

    return EmailSendResponse(
        status=email_log.status.lower(),
        recipient=customer.email,
        subject=email_log.subject,
        delivery_status=email_log.status.lower(),
        email_log_id=email_log.id,
    )
