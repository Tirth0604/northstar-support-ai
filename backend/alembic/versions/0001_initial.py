"""Create document, conversation, message, and citation tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("documents", sa.Column("id", sa.String(36), primary_key=True), sa.Column("original_filename", sa.String(255), nullable=False), sa.Column("stored_filename", sa.String(255), nullable=False, unique=True), sa.Column("file_type", sa.String(16), nullable=False), sa.Column("file_size", sa.Integer, nullable=False), sa.Column("file_hash", sa.String(64), nullable=False), sa.Column("upload_status", sa.Enum("PROCESSING", "READY", "FAILED", name="documentstatus"), nullable=False), sa.Column("chunk_count", sa.Integer, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("error_message", sa.Text, nullable=True))
    op.create_index("ix_documents_file_hash", "documents", ["file_hash"], unique=True)
    op.create_table("conversations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("title", sa.String(120), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_table("messages", sa.Column("id", sa.String(36), primary_key=True), sa.Column("conversation_id", sa.String(36), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False), sa.Column("role", sa.String(16), nullable=False), sa.Column("content", sa.Text, nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("latency_ms", sa.Integer, nullable=True), sa.Column("grounding_status", sa.String(32), nullable=True), sa.Column("retrieved_sources", sa.JSON, nullable=True))
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_table("citations", sa.Column("id", sa.String(36), primary_key=True), sa.Column("message_id", sa.String(36), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False), sa.Column("document_id", sa.String(36), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False), sa.Column("document_name", sa.String(255), nullable=False), sa.Column("chunk_id", sa.String(80), nullable=False), sa.Column("page_number", sa.Integer, nullable=True), sa.Column("excerpt", sa.Text, nullable=False), sa.Column("relevance_score", sa.Float, nullable=False))
    op.create_index("ix_citations_message_id", "citations", ["message_id"])
    op.create_index("ix_citations_document_id", "citations", ["document_id"])


def downgrade() -> None:
    op.drop_table("citations")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.drop_table("documents")
