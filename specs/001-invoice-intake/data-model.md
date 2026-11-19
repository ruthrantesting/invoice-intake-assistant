# Data Model: Invoice Intake Assistant

All tenant-owned entities include an opaque ID, `tenant_id`, created/updated timestamps, and authorization checks. Timestamps are UTC; monetary values are decimal strings at boundaries and exact decimals internally. Users are identified by external OIDC subject plus tenant; roles and per-record permissions are server-enforced.

## Entities and relationships

### Invoice and revision

- **Invoice**: `id`, `tenant_id`, source blob ID/hash, processing status (`received`, `processing`, `ready_for_review`, `logged`, `failed`), review status (`not_reviewed`, `needs_review`, `reviewed`), current revision, created-by user.
- **InvoiceRevision**: invoice ID, monotonic revision, vendor, invoice number, invoice/due dates, PO number, currency, subtotal, tax, shipping/other charges, discounts, total, optional line items; each nullable. Identifiers are strings; amounts retain exact precision and dates retain raw input.
- **FieldEvidence**: invoice revision and field name, raw extracted value, normalized value, source page and optional coordinates/snippet, confidence or uncertainty indicator, extraction method. A null field is not inferred. Evidence and original extraction are immutable; corrections create a new revision and audit event.
- **LineItem**: revision, position, raw description, quantity, unit price and line total as available; null when absent.

### Validation and review

- **ValidationRun**: invoice revision, workbook version and mapping used for duplicate checks, rule configuration version, timestamp, actor/system; rerun after correction and immediately before logging.
- **ValidationResult**: run, check type (`arithmetic`, `duplicate`, `missing_po`, `field`, `date`, `currency`), outcome (`passed`, `flagged`, `not_verifiable`), reason, source references and optional matched authorized invoice/log row. Deterministic rules only; comparison scope is recorded. Missing identifiers are never considered equal. A missing PO is a review flag, not invalidity.
- **ReviewEvent**: invoice, status, reviewer, time and optional note; review is data review only, not payment approval. Existing flags/history persist.

### Workbook, mapping and operation

- **Workbook**: tenant, label, source blob, current version ID and lifecycle; application-managed copies are distinct from the user's local file.
- **WorkbookVersion**: workbook, version number, immutable blob ID and SHA-256, parent version, created time, approved supported-feature profile. Version pointer advances through a transactional compare-and-swap.
- **ColumnMapping**: workbook, worksheet identity, header snapshot, field-to-column map, version, creator and human confirmation time; reusable mappings scoped to authorized tenants. Reject duplicate or invalid mappings; unmapped cells remain blank.
- **LogPreview**: invoice revision, workbook version, mapping revision, destination, canonical proposed row, validation results/flags digest, expiry and user; no write occurs on preview. The digest binds all review-relevant material.
- **LogOperation**: tenant, workbook and invoice IDs, idempotency key and request digest, preview ID, confirming human, state (`pending`, `committed`, `conflict`, `failed`), candidate blob ID, outcome/version, timestamps. The idempotency key is unique within the tenant and workbook. Same key and digest returns the existing operation outcome; reuse with different content conflicts. Failed/conflicted attempts require a fresh preview/confirmation where material data changed; they do not reserve a permanent committed uniqueness slot. A separate unique committed-write constraint prevents a second committed append of the same invoice to the same workbook.

### Supporting entities

- **Blob**: opaque private storage location, hash, media type, size, lifecycle/retention and encryption metadata; immutable originals and generated workbook versions.
- **Job**: invoice, stage, state, lease owner/expiry, attempts, next attempt, timestamps and safe error code; workers may be redelivered and must be idempotent.
- **ChatSession / ChatMessage**: authorized user/tenant, invoice context, timestamp, role and content; no message alone is a logging confirmation. External content and model output are untrusted.
- **AuditEvent**: actor type/ID, tenant, timestamp, action, resource, outcome and protected before/after details as applicable. Mutating DB state and its audit record commit together; audit access/retention follow approved policy.

## Validation and state transitions

1. Upload: validate type, size, page/pixel limits and malware policy; accepted invoice becomes `received`, then `processing`. Processing success produces revision/evidence and `ready_for_review`; failure becomes `failed` with actionable error and a retry path.
2. Extraction: absent/unreadable fields remain null; ambiguous date, currency or sign is flagged. Raw text and corrected values are distinguished. Text recognition must not be treated as certainty.
3. Arithmetic: `subtotal + tax + other_charges - discounts` compared to stated total using configured currency-aware decimal tolerance only when all required components and signs are known. Missing components are not automatically zero; result is `not_verifiable` if insufficient.
4. Revalidation: corrections create new revision and validation run. Duplicate checks cover authorized application records and selected workbook version, with reasons and scope. Changes invalidating a preview require a new preview and human confirmation.
5. Confirmation and write: authorize human, bind exact invoice/mapping/flags/workbook version and request digest; revalidate. Stage and verify immutable workbook blob. Transactionally compare current workbook version and commit pointer, operation outcome, invoice `logged` state and audit event. If stale or changed, return conflict; no overwrite. Retry same confirmed operation safely.
6. Recovery: after crash, a candidate with no committed pointer is an orphan, not a successful write. Reconcile operation state before retry/cleanup. Referenced missing or corrupt blobs trigger an integrity incident and block writes. Separate review state is never inferred from `logged`.
7. Deletion/retention: configurable and approved before production; legal holds and audit retention take precedence according to organizational policy. Do not hard-code unstated retention periods.
