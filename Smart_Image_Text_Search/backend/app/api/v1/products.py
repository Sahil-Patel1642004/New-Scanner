from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.dependencies import get_current_admin_user, get_db
from app.models import AdminUser, Product
from app.schemas import ProductCreate, ProductRead

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", response_model=ProductRead)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> ProductRead:
    name = payload.name.strip()
    sku = payload.sku.strip().upper()
    if db.query(Product).filter((Product.sku == sku) | (Product.name == name)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A product with this name or SKU already exists.")

    product = Product(name=name, sku=sku, description=payload.description)
    db.add(product)
    db.commit()
    db.refresh(product)
    return ProductRead.model_validate(product)


@router.get("", response_model=list[ProductRead])
def list_products(
    db: Session = Depends(get_db),
    _: AdminUser = Depends(get_current_admin_user),
) -> list[ProductRead]:
    products = db.query(Product).order_by(Product.name.asc()).all()
    return [ProductRead.model_validate(product) for product in products]