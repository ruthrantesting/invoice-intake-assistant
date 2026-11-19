from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from invoice_agent.persistence.models import Base


class Workbook(Base):
    __tablename__ = "workbooks"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    source_blob_id: Mapped[str | None] = mapped_column(String(64))
    current_version_id: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class WorkbookVersion(Base):
    __tablename__ = "workbook_versions"
    __table_args__ = (
        UniqueConstraint("workbook_id", "version_number", name="uq_workbook_version"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workbook_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbooks.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    blob_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parent_version_id: Mapped[str | None] = mapped_column(String(64))
    profile_version: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class ColumnMapping(Base):
    __tablename__ = "column_mappings"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workbook_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbooks.id", ondelete="CASCADE"), index=True
    )
    sheet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    header_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    field_to_column: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LogPreview(Base):
    __tablename__ = "log_previews"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    invoice_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    workbook_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbooks.id", ondelete="CASCADE"), index=True
    )
    workbook_version_id: Mapped[str] = mapped_column(String(64), nullable=False)
    mapping_id: Mapped[str] = mapped_column(ForeignKey("column_mappings.id"), nullable=False)
    proposed_row: Mapped[str] = mapped_column(Text, nullable=False)
    flags_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)


class LogOperation(Base):
    __tablename__ = "log_operations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "workbook_id", "idempotency_key", name="uq_log_idempotency"),
        UniqueConstraint("invoice_id", "workbook_id", name="uq_committed_invoice_workbook"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    workbook_id: Mapped[UUID] = mapped_column(
        ForeignKey("workbooks.id", ondelete="CASCADE"), index=True
    )
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    request_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    preview_id: Mapped[str] = mapped_column(ForeignKey("log_previews.id"), nullable=False)
    confirming_user: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="pending")
    candidate_blob_id: Mapped[str | None] = mapped_column(String(64))
    outcome_version_id: Mapped[str | None] = mapped_column(String(64))
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )
