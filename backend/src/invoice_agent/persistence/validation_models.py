from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from invoice_agent.persistence.models import Base


class ValidationRun(Base):
    __tablename__ = "validation_runs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    workbook_version_id: Mapped[str | None] = mapped_column(String(64))
    mapping_id: Mapped[str | None] = mapped_column(String(64))
    rule_config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_id: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class ValidationResultRow(Base):
    __tablename__ = "validation_results"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("validation_runs.id", ondelete="CASCADE"), index=True
    )
    check_type: Mapped[str] = mapped_column(String(32), nullable=False)
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    matched_record_id: Mapped[str | None] = mapped_column(String(64))
    comparison_scope: Mapped[str | None] = mapped_column(String(255))
    source_references: Mapped[str | None] = mapped_column(Text)
