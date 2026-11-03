"""Customer and licence tables

Revision ID: 20261102_customer_licence_tables
Revises: 20261102_initial_admin_tables
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_customer_licence_tables"
down_revision = "20261102_initial_admin_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("order_reference", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_customers_email"), "customers", ["email"], unique=True)
    op.create_index(op.f("ix_customers_id"), "customers", ["id"], unique=False)

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("sku"),
    )
    op.create_index(op.f("ix_products_id"), "products", ["id"], unique=False)
    op.create_index(op.f("ix_products_name"), "products", ["name"], unique=True)
    op.create_index(op.f("ix_products_sku"), "products", ["sku"], unique=True)

    op.create_table(
        "licences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("licence_type", sa.String(length=50), nullable=False),
        sa.Column("product_key_hash", sa.String(length=255), nullable=False),
        sa.Column("product_key_preview", sa.String(length=64), nullable=False),
        sa.Column("issue_date", sa.Date(), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("activation_state", sa.String(length=32), nullable=False),
        sa.Column("administrative_state", sa.String(length=32), nullable=False),
        sa.Column("expiry_state", sa.String(length=32), nullable=False),
        sa.Column("max_devices", sa.Integer(), nullable=False),
        sa.Column("notes", sa.String(length=1000), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_key_hash", name="uq_licences_product_key_hash"),
    )
    op.create_index(op.f("ix_licences_customer_id"), "licences", ["customer_id"], unique=False)
    op.create_index(op.f("ix_licences_id"), "licences", ["id"], unique=False)
    op.create_index(op.f("ix_licences_product_id"), "licences", ["product_id"], unique=False)
    op.create_index(op.f("ix_licences_product_key_hash"), "licences", ["product_key_hash"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_licences_product_key_hash"), table_name="licences")
    op.drop_index(op.f("ix_licences_product_id"), table_name="licences")
    op.drop_index(op.f("ix_licences_id"), table_name="licences")
    op.drop_index(op.f("ix_licences_customer_id"), table_name="licences")
    op.drop_table("licences")
    op.drop_index(op.f("ix_products_sku"), table_name="products")
    op.drop_index(op.f("ix_products_name"), table_name="products")
    op.drop_index(op.f("ix_products_id"), table_name="products")
    op.drop_table("products")
    op.drop_index(op.f("ix_customers_id"), table_name="customers")
    op.drop_index(op.f("ix_customers_email"), table_name="customers")
    op.drop_table("customers")
