"""Add index_price and governance_event tables with idempotent reflection guards.

Revision ID: 002_add_index_price_and_governance
Revises: 001_initial_schema
Create Date: 2026-10-25 12:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

revision: str = '002_add_index_price_and_governance'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    # 1. index_price table
    if 'index_price' not in existing_tables:
        op.create_table(
            'index_price',
            sa.Column('index_name', sa.String(length=50), nullable=False),
            sa.Column('trade_date', sa.Date(), nullable=False),
            sa.Column('open', sa.Float(), nullable=True),
            sa.Column('high', sa.Float(), nullable=True),
            sa.Column('low', sa.Float(), nullable=True),
            sa.Column('close', sa.Float(), nullable=False),
            sa.Column('volume', sa.BigInteger(), nullable=True),
            sa.Column('turnover_cr', sa.Float(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('index_name', 'trade_date')
        )

    # 2. governance_event table
    if 'governance_event' not in existing_tables:
        op.create_table(
            'governance_event',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('isin', sa.String(length=12), nullable=False),
            sa.Column('event_date', sa.Date(), nullable=False),
            sa.Column('event_type', sa.String(length=50), nullable=False),
            sa.Column('title', sa.String(length=200), nullable=False),
            sa.Column('description', sa.Text(), nullable=True),
            sa.Column('severity', sa.String(length=20), nullable=False),
            sa.Column('metric_value', sa.Float(), nullable=True),
            sa.Column('source_url', sa.Text(), nullable=False),
            sa.Column('published_at', sa.DateTime(), nullable=False),
            sa.Column('ingested_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['isin'], ['security.isin']),
            sa.PrimaryKeyConstraint('id')
        )
        op.create_index('idx_gov_event_isin_date', 'governance_event', ['isin', 'event_date'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    existing_tables = inspector.get_table_names()

    if 'governance_event' in existing_tables:
        op.drop_index('idx_gov_event_isin_date', table_name='governance_event')
        op.drop_table('governance_event')
    if 'index_price' in existing_tables:
        op.drop_table('index_price')
