"""Add current_flow, current_step, payload to conversation_state

Revision ID: 20241214_0003
Revises: 20241213_0002
Create Date: 2025-12-14
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241214_0003"
down_revision = "20241213_0002"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("conversation_state") as batch_op:
        batch_op.add_column(sa.Column("current_flow", sa.String(), nullable=False, server_default="MENU"))
        batch_op.add_column(sa.Column("current_step", sa.String(), nullable=False, server_default="MENU"))
        batch_op.add_column(sa.Column("payload", sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table("conversation_state") as batch_op:
        batch_op.drop_column("payload")
        batch_op.drop_column("current_step")
        batch_op.drop_column("current_flow")

