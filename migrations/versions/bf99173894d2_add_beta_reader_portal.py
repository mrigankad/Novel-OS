"""add beta reader portal

Revision ID: bf99173894d2
Revises: 1703f0f6a423
Create Date: 2026-11-13 13:26:59.957577
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel


revision = 'bf99173894d2'
down_revision = '1703f0f6a423'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pre-migration dev databases made with create_all() already have the tables.
    if sa.inspect(op.get_bind()).has_table('betaround'):
        return
    op.create_table('betaround',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('project_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('chapters', sa.JSON(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('closes_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('betaround', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_betaround_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_betaround_project_id'), ['project_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_betaround_status'), ['status'], unique=False)

    op.create_table('betareader',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('round_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('token', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
    sa.Column('invited_at', sa.DateTime(), nullable=False),
    sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    sa.Column('furthest_chapter', sa.Integer(), nullable=False),
    sa.Column('finished', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['round_id'], ['betaround.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('betareader', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_betareader_invited_at'), ['invited_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_betareader_round_id'), ['round_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_betareader_token'), ['token'], unique=True)

    op.create_table('betacomment',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('round_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reader_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('chapter', sa.Integer(), nullable=False),
    sa.Column('quote', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('from_offset', sa.Integer(), nullable=True),
    sa.Column('to_offset', sa.Integer(), nullable=True),
    sa.Column('body', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reaction', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['reader_id'], ['betareader.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['round_id'], ['betaround.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('betacomment', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_betacomment_chapter'), ['chapter'], unique=False)
        batch_op.create_index(batch_op.f('ix_betacomment_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_betacomment_reaction'), ['reaction'], unique=False)
        batch_op.create_index(batch_op.f('ix_betacomment_reader_id'), ['reader_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_betacomment_round_id'), ['round_id'], unique=False)

    op.create_table('betaprogress',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
    sa.Column('reader_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('chapter', sa.Integer(), nullable=False),
    sa.Column('percent', sa.Integer(), nullable=False),
    sa.Column('seconds_read', sa.Integer(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['reader_id'], ['betareader.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('betaprogress', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_betaprogress_chapter'), ['chapter'], unique=False)
        batch_op.create_index(batch_op.f('ix_betaprogress_reader_id'), ['reader_id'], unique=False)

    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('betaprogress', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_betaprogress_reader_id'))
        batch_op.drop_index(batch_op.f('ix_betaprogress_chapter'))

    op.drop_table('betaprogress')
    with op.batch_alter_table('betacomment', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_betacomment_round_id'))
        batch_op.drop_index(batch_op.f('ix_betacomment_reader_id'))
        batch_op.drop_index(batch_op.f('ix_betacomment_reaction'))
        batch_op.drop_index(batch_op.f('ix_betacomment_created_at'))
        batch_op.drop_index(batch_op.f('ix_betacomment_chapter'))

    op.drop_table('betacomment')
    with op.batch_alter_table('betareader', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_betareader_token'))
        batch_op.drop_index(batch_op.f('ix_betareader_round_id'))
        batch_op.drop_index(batch_op.f('ix_betareader_invited_at'))

    op.drop_table('betareader')
    with op.batch_alter_table('betaround', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_betaround_status'))
        batch_op.drop_index(batch_op.f('ix_betaround_project_id'))
        batch_op.drop_index(batch_op.f('ix_betaround_created_at'))

    op.drop_table('betaround')
    # ### end Alembic commands ###
