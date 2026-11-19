"""Create validation runs and results."""

from alembic import op

from invoice_agent.persistence.validation_models import ValidationResultRow, ValidationRun

revision = "0003_validation"
down_revision = "0002_invoice_records"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (ValidationRun, ValidationResultRow):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in (ValidationResultRow, ValidationRun):
        model.__table__.drop(bind=bind, checkfirst=True)
