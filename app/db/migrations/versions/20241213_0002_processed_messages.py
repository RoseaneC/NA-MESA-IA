"""Add processed_messages table for deduplication"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241213_0002"
down_revision = "20241213_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_processed_messages_id"), "processed_messages", ["id"], unique=False)
    op.create_index(op.f("ix_processed_messages_message_id"), "processed_messages", ["message_id"], unique=True)
    op.create_index(op.f("ix_processed_messages_phone"), "processed_messages", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_processed_messages_phone"), table_name="processed_messages")
    op.drop_index(op.f("ix_processed_messages_message_id"), table_name="processed_messages")
    op.drop_index(op.f("ix_processed_messages_id"), table_name="processed_messages")
    op.drop_table("processed_messages")

