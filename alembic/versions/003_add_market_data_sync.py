"""Add verified market snapshot synchronization audit records.

Revision ID: 003_add_market_data_sync
Revises: 002_add_index_price_and_governance
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "003_add_market_data_sync"
down_revision: Union[str, None] = "002_add_index_price_and_governance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "market_data_sync" in inspect(op.get_bind()).get_table_names():
        return

    op.create_table(
        "market_data_sync",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("provider_published_at", sa.DateTime(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("inserted_count", sa.Integer(), nullable=False),
        sa.Column("updated_count", sa.Integer(), nullable=False),
        sa.Column("unchanged_count", sa.Integer(), nullable=False),
        sa.Column("skipped_count", sa.Integer(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "exchange", "trading_date", "source_hash",
            name="uq_market_data_sync_snapshot"
        ),
    )
    op.create_index(
        "idx_market_data_sync_date", "market_data_sync", ["trading_date"]
    )


def downgrade() -> None:
    if "market_data_sync" not in inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("idx_market_data_sync_date", table_name="market_data_sync")
    op.drop_table("market_data_sync")
