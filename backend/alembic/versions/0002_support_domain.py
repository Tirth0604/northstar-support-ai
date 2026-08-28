"""Add customer-support domain, security state, and audit tables."""
from alembic import op
import sqlalchemy as sa

revision = "0002_support_domain"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(sa.Column("customer_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("status", sa.String(32), nullable=False, server_default="ai_active"))
        batch.add_column(sa.Column("assigned_agent_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch.add_column(sa.Column("summary", sa.Text(), nullable=True))
        batch.add_column(sa.Column("pending_action", sa.JSON(), nullable=True))
        batch.create_index("ix_conversations_customer_id", ["customer_id"])
        batch.create_index("ix_conversations_status", ["status"])
    with op.batch_alter_table("messages") as batch:
        batch.add_column(sa.Column("sender_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("structured_payload", sa.JSON(), nullable=True))
    from app.db.session import Base
    import app.models.entities  # noqa: F401
    existing = {"documents", "conversations", "messages", "citations"}
    for table in Base.metadata.sorted_tables:
        if table.name not in existing:
            table.create(op.get_bind(), checkfirst=True)


def downgrade() -> None:
    from app.db.session import Base
    import app.models.entities  # noqa: F401
    existing = {"documents", "conversations", "messages", "citations"}
    for table in reversed(Base.metadata.sorted_tables):
        if table.name not in existing:
            table.drop(op.get_bind(), checkfirst=True)
    with op.batch_alter_table("messages") as batch:
        batch.drop_column("structured_payload")
        batch.drop_column("sender_id")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_column("pending_action")
        batch.drop_column("summary")
        batch.drop_column("ai_enabled")
        batch.drop_column("assigned_agent_id")
        batch.drop_column("status")
        batch.drop_column("customer_id")
