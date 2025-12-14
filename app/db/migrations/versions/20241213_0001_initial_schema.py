"""Initial schema for VEXIA"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20241213_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(), nullable=False, unique=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("neighborhood", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)
    op.create_index(op.f("ix_users_phone"), "users", ["phone"], unique=False)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False, unique=True),
        sa.Column("coverage_area", sa.Text(), nullable=True),
        sa.Column("can_pickup", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("hours", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_organizations_id"), "organizations", ["id"], unique=False)
    op.create_index(op.f("ix_organizations_phone"), "organizations", ["phone"], unique=False)

    op.create_table(
        "donations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("donor_phone", sa.String(), nullable=False),
        sa.Column("food_type", sa.Text(), nullable=False),
        sa.Column("qty", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_donations_id"), "donations", ["id"], unique=False)

    op.create_table(
        "active_distributions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("volunteer_phone", sa.String(), nullable=False),
        sa.Column("food_type", sa.Text(), nullable=False),
        sa.Column("qty", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_active_distributions_id"), "active_distributions", ["id"], unique=False)

    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("donation_id", sa.Integer(), sa.ForeignKey("donations.id"), nullable=False),
        sa.Column("org_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="suggested"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_matches_id"), "matches", ["id"], unique=False)

    op.create_table(
        "conversation_state",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("phone", sa.String(), nullable=False, unique=True),
        sa.Column("state", sa.String(), nullable=False),
        sa.Column("temp_json", sa.JSON(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index(op.f("ix_conversation_state_id"), "conversation_state", ["id"], unique=False)
    op.create_index(op.f("ix_conversation_state_phone"), "conversation_state", ["phone"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_conversation_state_phone"), table_name="conversation_state")
    op.drop_index(op.f("ix_conversation_state_id"), table_name="conversation_state")
    op.drop_table("conversation_state")

    op.drop_index(op.f("ix_matches_id"), table_name="matches")
    op.drop_table("matches")

    op.drop_index(op.f("ix_active_distributions_id"), table_name="active_distributions")
    op.drop_table("active_distributions")

    op.drop_index(op.f("ix_donations_id"), table_name="donations")
    op.drop_table("donations")

    op.drop_index(op.f("ix_organizations_phone"), table_name="organizations")
    op.drop_index(op.f("ix_organizations_id"), table_name="organizations")
    op.drop_table("organizations")

    op.drop_index(op.f("ix_users_phone"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")

