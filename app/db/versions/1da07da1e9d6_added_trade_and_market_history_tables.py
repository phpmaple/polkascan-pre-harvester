"""Added trade and market history tables

Revision ID: 1da07da1e9d6
Revises: 38a7f29de7c7
Create Date: 2020-01-20 16:43:14.600902

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1da07da1e9d6'
down_revision = '38a7f29de7c7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('data_market_history_1d',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('time', sa.DateTime(
                        timezone=True), nullable=False),
                    sa.Column('open', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('high', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('low', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('close', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('quote_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base', sa.String(length=66), nullable=False),
                    sa.Column('quote', sa.String(length=66), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('ix_data_market_history_1d_base_quote',
                    'data_market_history_1d', ['base', 'quote'], unique=False)
    op.create_table('data_market_history_1h',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('time', sa.DateTime(
                        timezone=True), nullable=False),
                    sa.Column('open', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('high', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('low', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('close', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('quote_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base', sa.String(length=66), nullable=False),
                    sa.Column('quote', sa.String(length=66), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('ix_data_market_history_1h_base_quote',
                    'data_market_history_1h', ['base', 'quote'], unique=False)
    op.create_table('data_market_history_1m',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('time', sa.DateTime(
                        timezone=True), nullable=False),
                    sa.Column('open', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('high', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('low', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('close', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('quote_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base', sa.String(length=66), nullable=False),
                    sa.Column('quote', sa.String(length=66), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('ix_data_market_history_1m_base_quote',
                    'data_market_history_1m', ['base', 'quote'], unique=False)
    op.create_table('data_market_history_5m',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('time', sa.DateTime(
                        timezone=True), nullable=False),
                    sa.Column('open', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('high', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('low', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('close', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('quote_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base', sa.String(length=66), nullable=False),
                    sa.Column('quote', sa.String(length=66), nullable=False),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_index('ix_data_market_history_5m_base_quote',
                    'data_market_history_5m', ['base', 'quote'], unique=False)
    op.create_table('data_trade',
                    sa.Column('trade_hash', sa.String(
                        length=66), nullable=False),
                    sa.Column('block_id', sa.Integer(), nullable=True),
                    sa.Column('extrinsic_idx', sa.Integer(), nullable=True),
                    sa.Column('event_idx', sa.Integer(), nullable=True),
                    sa.Column('base', sa.String(length=66), nullable=False),
                    sa.Column('quote', sa.String(length=66), nullable=False),
                    sa.Column('buyer', sa.String(length=64), nullable=False),
                    sa.Column('seller', sa.String(length=64), nullable=False),
                    sa.Column('maker', sa.String(length=64), nullable=False),
                    sa.Column('taker', sa.String(length=64), nullable=False),
                    sa.Column('otype', sa.SmallInteger(), nullable=False),
                    sa.Column('price', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('base_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.Column('quote_amount', sa.Numeric(
                        precision=65, scale=0), nullable=False),
                    sa.PrimaryKeyConstraint('trade_hash')
                    )
    op.create_index('ix_data_trade_block_id_base_quote', 'data_trade', [
                    'block_id', 'base', 'quote'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_data_trade_block_id_base_quote', table_name='data_trade')
    op.drop_table('data_trade')
    op.drop_index('ix_data_market_history_5m_base_quote',
                  table_name='data_market_history_5m')
    op.drop_table('data_market_history_5m')
    op.drop_index('ix_data_market_history_1m_base_quote',
                  table_name='data_market_history_1m')
    op.drop_table('data_market_history_1m')
    op.drop_index('ix_data_market_history_1h_base_quote',
                  table_name='data_market_history_1h')
    op.drop_table('data_market_history_1h')
    op.drop_index('ix_data_market_history_1d_base_quote',
                  table_name='data_market_history_1d')
    op.drop_table('data_market_history_1d')
    # ### end Alembic commands ###