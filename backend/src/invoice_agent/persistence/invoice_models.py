from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from invoice_agent.persistence.models import Base


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), index=True
    )
    source_blob_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_media_type: Mapped[str] = mapped_column(String(100), nullable=False)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, default="received")
    review_status: Mapped[str] = mapped_column(String(32), nullable=False, default="not_reviewed")
    current_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latest_validation_run_id: Mapped[UUID | None] = mapped_column(Uuid)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


class InvoiceRevision(Base):
    __tablename__ = "invoice_revisions"
    __table_args__ = (UniqueConstraint("invoice_id", "revision", name="uq_invoice_revision"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    vendor: Mapped[str | None] = mapped_column(String(500))
    invoice_number: Mapped[str | None] = mapped_column(String(255))
    invoice_date_raw: Mapped[str | None] = mapped_column(String(100))
    due_date_raw: Mapped[str | None] = mapped_column(String(100))
    po_number: Mapped[str | None] = mapped_column(String(255))
    currency: Mapped[str | None] = mapped_column(String(3))
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(24, 8, asdecimal=True))
    tax: Mapped[Decimal | None] = mapped_column(Numeric(24, 8, asdecimal=True))
    other_charges: Mapped[Decimal | None] = mapped_column(Numeric(24, 8, asdecimal=True))
    discounts: Mapped[Decimal | None] = mapped_column(Numeric(24, 8, asdecimal=True))
    total: Mapped[Decimal | None] = mapped_column(Numeric(24, 8, asdecimal=True))


class FieldEvidence(Base):
    __tablename__ = "field_evidence"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoice_revisions.id", ondelete="CASCADE"), index=True
    )
    field_name: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_value: Mapped[str | None] = mapped_column(Text)
    normalized_value: Mapped[str | None] = mapped_column(Text)
    corrected_value: Mapped[str | None] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    snippet: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    extraction_method: Mapped[str] = mapped_column(String(32), nullable=False)


class LineItem(Base):
    __tablename__ = "line_items"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoice_revisions.id", ondelete="CASCADE"), index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
