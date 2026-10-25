"""Initial schema with portable DDL for security, prices, corporate actions, and EAV financials.

Revision ID: 001_initial_schema
Revises: 
Create Date: 2026-10-25 11:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'security',
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('ticker_current', sa.String(length=20), nullable=False),
        sa.Column('company_name', sa.String(length=200), nullable=False),
        sa.Column('sector', sa.String(length=100), nullable=True),
        sa.Column('industry', sa.String(length=100), nullable=True),
        sa.Column('listing_date', sa.Date(), nullable=False),
        sa.Column('delisting_date', sa.Date(), nullable=True),
        sa.Column('series', sa.String(length=5), nullable=False),
        sa.Column('is_financial', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('isin')
    )
    op.create_index('idx_security_ticker', 'security', ['ticker_current'])

    op.create_table(
        'isin_history',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('old_isin', sa.String(length=12), nullable=False),
        sa.Column('new_isin', sa.String(length=12), nullable=False),
        sa.Column('change_date', sa.Date(), nullable=False),
        sa.Column('reason', sa.String(length=100), nullable=False),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['new_isin'], ['security.isin']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'price_raw',
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('trade_date', sa.Date(), nullable=False),
        sa.Column('open_raw', sa.Float(), nullable=True),
        sa.Column('high_raw', sa.Float(), nullable=True),
        sa.Column('low_raw', sa.Float(), nullable=True),
        sa.Column('close_raw', sa.Float(), nullable=False),
        sa.Column('volume_raw', sa.BigInteger(), nullable=False),
        sa.Column('delivery_pct', sa.Float(), nullable=True),
        sa.Column('source_file', sa.String(length=100), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('ingested_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['isin'], ['security.isin']),
        sa.PrimaryKeyConstraint('isin', 'trade_date')
    )
    op.create_index('idx_price_raw_isin_date', 'price_raw', ['isin', 'trade_date'])

    op.create_table(
        'corporate_action',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('ex_date', sa.Date(), nullable=False),
        sa.Column('record_date', sa.Date(), nullable=True),
        sa.Column('action_type', sa.String(length=30), nullable=False),
        sa.Column('ratio_numerator', sa.Integer(), nullable=True),
        sa.Column('ratio_denominator', sa.Integer(), nullable=True),
        sa.Column('dividend_per_share', sa.Float(), nullable=True),
        sa.Column('dividend_type', sa.String(length=20), nullable=True),
        sa.Column('subscription_price', sa.Float(), nullable=True),
        sa.Column('details_json', sa.Text(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('adj_factor', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['isin'], ['security.isin']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('isin', 'ex_date', 'action_type', name='uq_ca_isin_ex_type')
    )
    op.create_index('idx_ca_isin_ex', 'corporate_action', ['isin', 'ex_date'])

    op.create_table(
        'line_item_def',
        sa.Column('item_code', sa.String(length=50), nullable=False),
        sa.Column('item_name', sa.String(length=150), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('applicable_to', sa.String(length=50), nullable=False),
        sa.Column('unit_type', sa.String(length=20), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('item_code')
    )

    op.create_table(
        'financial_statement',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('period_type', sa.String(length=15), nullable=False),
        sa.Column('consolidated', sa.Boolean(), nullable=False),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('unit_multiplier', sa.Float(), nullable=False),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('ingested_at', sa.DateTime(), nullable=False),
        sa.Column('restated_at', sa.DateTime(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False),
        sa.Column('is_restatement', sa.Boolean(), nullable=False),
        sa.Column('supersedes_id', sa.Integer(), nullable=True),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_to', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['isin'], ['security.isin']),
        sa.ForeignKeyConstraint(['supersedes_id'], ['financial_statement.id']),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_fs_isin_period', 'financial_statement', ['isin', 'period_end'])
    op.create_index('idx_fs_validity', 'financial_statement', ['valid_from', 'valid_to'])

    op.create_table(
        'financial_line_item',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('statement_id', sa.Integer(), nullable=False),
        sa.Column('item_code', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('is_estimated', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['item_code'], ['line_item_def.item_code']),
        sa.ForeignKeyConstraint(['statement_id'], ['financial_statement.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('statement_id', 'item_code', name='uq_fs_item')
    )

    op.create_table(
        'index_constituent',
        sa.Column('index_name', sa.String(length=50), nullable=False),
        sa.Column('isin', sa.String(length=12), nullable=False),
        sa.Column('inclusion_date', sa.Date(), nullable=False),
        sa.Column('exclusion_date', sa.Date(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=True),
        sa.Column('source_url', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['isin'], ['security.isin']),
        sa.PrimaryKeyConstraint('index_name', 'isin', 'inclusion_date')
    )


def downgrade() -> None:
    op.drop_table('index_constituent')
    op.drop_table('financial_line_item')
    op.drop_table('financial_statement')
    op.drop_table('line_item_def')
    op.drop_table('corporate_action')
    op.drop_table('price_raw')
    op.drop_table('isin_history')
    op.drop_table('security')
