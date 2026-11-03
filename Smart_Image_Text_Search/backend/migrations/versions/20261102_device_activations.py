"""Device activations

Revision ID: 20261102_device_activations
Revises: 20261102_email_logs
Create Date: 2026-11-02 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "20261102_device_activations"
down_revision = "20261102_email_logs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_activations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("licence_id", sa.Integer(), nullable=False),
        sa.Column("device_fingerprint", sa.String(length=255), nullable=False),
        sa.Column("device_name", sa.String(length=255), nullable=True),
        sa.Column("os_version", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("activated_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["licence_id"], ["licences.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("licence_id", "device_fingerprint", name="uq_device_activation_licence_fingerprint"),
    )
    op.create_index(op.f("ix_device_activations_id"), "device_activations", ["id"], unique=False)
    op.create_index(op.f("ix_device_activations_licence_id"), "device_activations", ["licence_id"], unique=False)
    op.create_index(op.f("ix_device_activations_device_fingerprint"), "device_activations", ["device_fingerprint"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_device_activations_device_fingerprint"), table_name="device_activations")
    op.drop_index(op.f("ix_device_activations_licence_id"), table_name="device_activations")
    op.drop_index(op.f("ix_device_activations_id"), table_name="device_activations")
    op.drop_table("device_activations")
