from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin_user, get_db
from app.models import Customer, AdminUser
from app.schemas import CustomerCreate, CustomerRead

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post("", response_model=CustomerRead)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> CustomerRead:
    if db.query(Customer).filter(Customer.email == payload.email.lower()).first() is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A customer with this email already exists.")

    customer = Customer(
        name=payload.name,
        email=payload.email.lower(),
        phone=payload.phone,
        company_name=payload.company_name,
        order_reference=payload.order_reference,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer)


@router.get("", response_model=list[CustomerRead])
def list_customers(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> list[CustomerRead]:
    customers = db.query(Customer).order_by(Customer.created_at.desc()).all()
    return [CustomerRead.model_validate(customer) for customer in customers]


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> CustomerRead:
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")
    return CustomerRead.model_validate(customer)
