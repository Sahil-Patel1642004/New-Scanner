"""Email logs

Revision ID: 20261102_email_logs
Revises: 20261102_customer_licence_tables
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_email_logs"
down_revision = "20261102_customer_licence_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("licences", sa.Column("product_key_ciphertext", sa.String(length=512), nullable=True))
    op.create_table(
        "email_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("licence_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("recipient", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_message_id", sa.String(length=255), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("failed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["licence_id"], ["licences.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_email_logs_id"), "email_logs", ["id"], unique=False)
    op.create_index(op.f("ix_email_logs_licence_id"), "email_logs", ["licence_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_email_logs_licence_id"), table_name="email_logs")
    op.drop_index(op.f("ix_email_logs_id"), table_name="email_logs")
    op.drop_table("email_logs")
    op.drop_column("licences", "product_key_ciphertext")
