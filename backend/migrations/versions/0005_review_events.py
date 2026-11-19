"""Create review and chat history tables."""

from alembic import op

from invoice_agent.persistence.chat_models import ChatMessage, ChatSession
from invoice_agent.persistence.review_models import ReviewEvent

revision = "0005_review_events"
down_revision = "0004_workbooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (ReviewEvent, ChatSession, ChatMessage):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in (ChatMessage, ChatSession, ReviewEvent):
        model.__table__.drop(bind=bind, checkfirst=True)
