from __future__ import annotations

from datetime import date, datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class AdminSessionPayload(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime


class AdminSummary(BaseModel):
    total_customers: int = 0
    total_licences: int = 0
    active_licences: int = 0
    inactive_licences: int = 0
    unused_product_keys: int = 0
    expired_licences: int = 0
    disabled_licences: int = 0
    revoked_licences: int = 0
    total_activated_devices: int = 0
    emails_sent: int = 0
    failed_email_deliveries: int = 0


class AdminDashboardResponse(BaseModel):
    admin_email: str
    dashboard: AdminSummary


class CustomerCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    company_name: str | None = Field(default=None, max_length=255)
    order_reference: str | None = Field(default=None, max_length=255)


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str | None = None
    company_name: str | None = None
    order_reference: str | None = None
    created_at: datetime
    updated_at: datetime


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    sku: str = Field(..., min_length=2, max_length=100)
    description: str | None = Field(default=None, max_length=1000)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sku: str
    description: str | None = None
    is_active: bool = True
    created_at: datetime


class LicenceCreate(BaseModel):
    customer_id: int
    product_id: int
    licence_type: str = Field(..., min_length=2, max_length=50)
    issue_date: date
    expiry_date: date
    start_date: date | None = None
    max_devices: int = Field(default=1, ge=1)
    notes: str | None = Field(default=None, max_length=1000)


class LicenceUpdate(BaseModel):
    start_date: date | None = None
    expiry_date: date | None = None
    max_devices: int | None = Field(default=None, ge=1)
    is_enabled: bool | None = None
    is_revoked: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)


class LicenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    customer_id: int
    product_id: int
    licence_type: str
    issue_date: date
    expiry_date: date
    start_date: date | None = None
    status: str
    max_devices: int
    masked_product_key: str = Field(
        validation_alias=AliasChoices("masked_product_key", "product_key_preview")
    )
    notes: str | None = None
    is_enabled: bool = True
    is_revoked: bool = False


class LicenceReadDetail(LicenceRead):
    product_key: str | None = None
    email_delivery_status: str | None = None
    email_recipient: str | None = None
    email_log_id: int | None = None


class LicenceActivationRequest(BaseModel):
    product_key: str = Field(..., min_length=8, max_length=128)
    device_fingerprint: str = Field(..., min_length=8, max_length=255)
    device_name: str | None = Field(default=None, max_length=255)
    os_version: str | None = Field(default=None, max_length=255)


class LicenceValidationRequest(BaseModel):
    licence_id: int = Field(..., gt=0)
    device_fingerprint: str = Field(..., min_length=8, max_length=255)


class LicenceActivationResponse(BaseModel):
    status: str
    licence_id: int
    device_fingerprint: str
    activation_state: str
    active_devices: int
    max_devices: int
    remaining_devices: int
    message: str


class SignedLicenceActivationResponse(BaseModel):
    status: str
    message: str
    payload: dict[str, str | int | bool | None]
    signature: str
    public_key: str


class LicenceSignatureVerificationRequest(BaseModel):
    payload: dict[str, str | int | bool | None]
    signature: str
    public_key: str | None = None


class LicenceSignatureVerificationResponse(BaseModel):
    valid: bool
    message: str
    licence_id: int | None = None


class EmailLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    licence_id: int
    customer_id: int
    recipient: str
    subject: str
    status: str
    provider_message_id: str | None = None
    retry_count: int = 0
    sent_at: datetime | None = None
    failed_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime


class EmailSendResponse(BaseModel):
    status: str
    recipient: str
    subject: str
    delivery_status: str
    email_log_id: int
