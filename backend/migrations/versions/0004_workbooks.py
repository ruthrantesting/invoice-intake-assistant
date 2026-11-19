"""Create managed workbook and idempotent logging tables."""

from alembic import op

from invoice_agent.persistence.workbook_models import (
    ColumnMapping,
    LogOperation,
    LogPreview,
    Workbook,
    WorkbookVersion,
)

revision = "0004_workbooks"
down_revision = "0003_validation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (Workbook, WorkbookVersion, ColumnMapping, LogPreview, LogOperation):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in (LogOperation, LogPreview, ColumnMapping, WorkbookVersion, Workbook):
        model.__table__.drop(bind=bind, checkfirst=True)
