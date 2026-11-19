"""Create invoice, revision and evidence records."""

from alembic import op

from invoice_agent.persistence.invoice_models import (
    FieldEvidence,
    Invoice,
    InvoiceRevision,
    LineItem,
)
from invoice_agent.persistence.job_repository import Job

revision = "0002_invoice_records"
down_revision = "0001_shared_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (Invoice, InvoiceRevision, FieldEvidence, LineItem, Job):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in (Job, LineItem, FieldEvidence, InvoiceRevision, Invoice):
        model.__table__.drop(bind=bind, checkfirst=True)
