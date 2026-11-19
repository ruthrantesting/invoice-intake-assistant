"""Create tenant, user and audit foundation."""

from alembic import op

from invoice_agent.persistence.models import AuditEvent, Tenant, User

revision = "0001_shared_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for model in (Tenant, User, AuditEvent):
        model.__table__.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for model in (AuditEvent, User, Tenant):
        model.__table__.drop(bind=bind, checkfirst=True)
