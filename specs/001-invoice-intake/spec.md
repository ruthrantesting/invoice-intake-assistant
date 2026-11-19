# Feature Specification: Invoice Intake Assistant

**Feature Branch**: `001-invoice-intake`

**Created**: 2026-11-18

**Status**: Draft

**Input**: User description: "Create a chat-based assistant for accounts-payable staff to intake invoices in PDF, scanned, phone photo, and HEIC formats; extract and validate invoice data; flag duplicates, missing purchase orders, and uncertainty; and prepare entries in an existing or new Excel log for human confirmation, without approving or paying invoices."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Extract and review an invoice (Priority: P1)

An AP operator uploads an invoice and receives a structured preview of its key information, with uncertain or unreadable fields clearly identified. The operator can correct extracted values before using them.

**Why this priority**: Reliable reviewable extraction is the foundation of the product and immediately reduces manual data entry while keeping a person in control.

**Independent Test**: Upload a representative PDF or image invoice; verify that the preview shows extracted values, missing or uncertain values, and available source evidence, and that the operator can correct a field.

**Acceptance Scenarios**:

1. **Given** an authorized operator has a supported invoice file, **When** they upload it, **Then** the assistant displays processing status and a structured preview with values, uncertainties, and available source references.
2. **Given** a field is unreadable or absent, **When** extraction is complete, **Then** that field remains unknown and is flagged rather than guessed.
3. **Given** the operator corrects an extracted value, **When** they save the correction, **Then** the preview reflects the correction and preserves the originally extracted value for audit.

---

### User Story 2 - Identify issues for human review (Priority: P1)

An AP operator sees deterministic checks for totals, possible duplicates, and PO presence, with explanations that let them decide what requires further review.

**Why this priority**: Catching common exceptions before recording an invoice reduces errors, but uncertainty and flags must remain visible to a person rather than become automatic decisions.

**Independent Test**: Submit test invoices with a total mismatch, insufficient arithmetic fields, matching log records, and missing PO numbers; verify the corresponding flags and explanations.

**Acceptance Scenarios**:

1. **Given** an invoice contains subtotal, tax, charges, discount, and total values, **When** the check runs, **Then** a total mismatch is flagged using the configured rounding tolerance.
2. **Given** required values for a total check are unavailable, **When** validation runs, **Then** the check is labeled not verifiable and is not reported as passed.
3. **Given** an invoice matches an accessible log record by available identifiers, **When** duplicate comparison runs, **Then** the assistant flags a possible duplicate and identifies the matching record and reason without discarding the invoice.
4. **Given** an invoice has no readable PO number, **When** validation completes, **Then** the assistant flags the missing PO as a review issue, not as proof of invalidity.

---

### User Story 3 - Confirm and log a record (Priority: P1)

An AP operator maps invoice fields to an existing workbook or creates a new log, reviews the proposed row and any flags, then explicitly confirms logging. The application provides an updated workbook without treating the action as payment approval.

**Why this priority**: Writing the reviewed data into the AP team's working log completes the core workflow while retaining human authority and spreadsheet integrity.

**Independent Test**: Map fields to a workbook with custom headers, review a proposed row, confirm once and retry; verify one row is appended, existing content is preserved, and an updated workbook is downloadable.

**Acceptance Scenarios**:

1. **Given** an operator uploads a supported workbook, **When** they select a worksheet, **Then** the application shows detected headers and requires confirmation of the field mapping before the first write.
2. **Given** an operator is ready to log an invoice, **When** they review the destination, proposed row, and flags and explicitly confirm, **Then** exactly one row is appended using the confirmed mapping and an updated workbook is made available.
3. **Given** a record is flagged or needs review, **When** the operator confirms logging, **Then** the record retains its review status and flags, and the action is labeled only as logging—not invoice or payment approval.
4. **Given** a confirmation is retried or the workbook is stale, **When** the write is attempted, **Then** idempotency prevents an extra row or the conflict is reported for resolution without overwriting newer changes.
5. **Given** an uploaded workbook or invoice contains formula-like text, **When** data is written, **Then** the text is stored safely and no uploaded formula or macro is executed.

---

### User Story 4 - Review processing state and history (Priority: P2)

An authorized reviewer examines a flagged record, records a review outcome or note, and can inspect the record's processing and action history. Review indicates data review only and does not authorize payment.

**Why this priority**: Persistent review status and an audit trail support accountability and handoffs for exceptions without expanding the product into financial approval.

**Independent Test**: Process and correct an invoice, log it, record a reviewer note, then verify actor, timestamps, original values, corrections, flags, confirmation, and write outcome are available to authorized users.

**Acceptance Scenarios**:

1. **Given** a record is flagged, **When** an authorized reviewer records a review note, **Then** the review status and note are saved with actor and timestamp and are not represented as payment authorization.
2. **Given** an authorized user opens a record's history, **When** they inspect it, **Then** uploads, extraction, corrections, validation, confirmations, mapping changes, review actions, and write outcomes are shown with actor and timestamp.
3. **Given** a user lacks permission for a record or operation, **When** they attempt access, **Then** the application denies the action and does not disclose the protected record.

### Edge Cases

- A PDF may contain selectable text, scanned pages, mixed text and images, encryption, corruption, or unsupported content; failures must be actionable and must not fabricate extracted values.
- A phone image or HEIC photo may be rotated, blurred, cropped, or contain multiple pages; uncertain fields remain flagged for human review.
- Currency, sign conventions, discounts, or rounding may be ambiguous; the result is flagged or marked not verifiable rather than silently accepted.
- Duplicate comparison may have incomplete identifiers or access only to a subset of records; the interface explains the available comparison basis and does not claim exhaustive detection.
- A workbook may contain unrelated sheets, formulas, unsupported features, locked content, non-default headers, or changes after upload; safe handling must preserve content or stop with an explanation.
- A write may fail or the user may repeat a request after a timeout; the record remains available, and retries do not create duplicate rows.
- Invoice text may contain instructions intended to manipulate the assistant; such content is treated as untrusted document data and cannot change system rules or trigger privileged actions.
- OCR, the language model, or external services may be unavailable or return invalid output; the user sees a clear failure/retry path, and no row is written automatically.
- No workflow, including administrative or reviewer workflows, may approve, schedule, or execute payment.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST allow authorized users to upload invoice files in PDF, JPEG, PNG, and HEIC formats and show progress and actionable completion or failure status.
- **FR-002**: The system MUST extract embedded PDF text when available and use text recognition for scanned documents and images; HEIC files MUST be processed through a supported conversion path.
- **FR-003**: The system MUST extract, when present, vendor name, invoice number, invoice date, due date, PO number, currency, subtotal, tax, other charges, discounts, total, and useful line-item details.
- **FR-004**: The system MUST distinguish extracted values, normalized values, user corrections, missing values, and uncertainty, and MUST provide source evidence such as page references when available.
- **FR-005**: The system MUST leave unreadable or absent values unknown and MUST NOT present guesses as extracted facts.
- **FR-006**: The system MUST provide chat-based questions, extraction previews, validation summaries, and field corrections for the selected invoice.
- **FR-007**: The system MUST validate total arithmetic using decimal-safe calculations and configured currency-aware rounding tolerance; insufficient values MUST result in a not-verifiable status.
- **FR-008**: The system MUST flag possible duplicates using available normalized invoice identifiers and exact file matches where available, identify matching records and reasons, and MUST NOT silently discard an invoice.
- **FR-009**: The system MUST flag missing or unreadable PO numbers as review issues and MUST NOT infer that an invoice is invalid solely because a PO is missing.
- **FR-010**: The system MUST show explanations and available evidence for low-confidence or conflicting fields, illegible content, missing key fields, arithmetic mismatches, and possible duplicates.
- **FR-011**: The system MUST rerun relevant validation after corrections and immediately before a spreadsheet write, preserving original values, corrections, flags, and review history.
- **FR-012**: The system MUST allow authorized users to upload an `.xlsx` workbook, select a worksheet, inspect headers, map invoice fields to workbook columns, and confirm the mapping before first use.
- **FR-013**: The system MUST append only to the selected worksheet, preserve unrelated sheets, existing rows, and headers, and stop with an explanation if safe preservation cannot be assured.
- **FR-014**: The system MUST allow a user to create a new spreadsheet log with configurable headers and review the column layout before the first write.
- **FR-015**: The system MUST display the proposed row, active flags, and destination and require explicit per-record user confirmation before any spreadsheet write.
- **FR-016**: Logging or recording a review outcome MUST NOT be labeled or interpreted as invoice approval, payment approval, or authorization to pay; flagged records logged after confirmation MUST retain their flags and review status.
- **FR-017**: The system MUST make updated workbooks downloadable and MUST clearly distinguish application-managed workbook copies from the user's local original.
- **FR-018**: The system MUST prevent duplicate spreadsheet writes across repeated confirmations and retries, and MUST detect stale or conflicting workbook versions without overwriting newer changes.
- **FR-019**: The system MUST safely store invoice-derived text, preserve leading-zero identifiers, and MUST NOT execute uploaded formulas or macros.
- **FR-020**: The system MUST provide separate processing and review statuses, with review outcomes and optional notes attributable to the responsible user.
- **FR-021**: The system MUST maintain an audit history of uploads, extracted and corrected values, validations, mapping changes, confirmations, writes, and review actions, including actor and timestamp.
- **FR-022**: The system MUST require authentication and role-appropriate authorization for upload, viewing, review, mapping configuration, and workbook download.
- **FR-023**: The system MUST preserve invoice and review state across recoverable failures and show clear retry paths without claiming a failed spreadsheet write succeeded.
- **FR-024**: The system MUST never approve an invoice, authorize payment, or initiate, schedule, or execute payment.

### Key Entities *(include if feature involves data)*

- **Invoice Record**: One uploaded invoice with unique identity, source file, extracted and normalized values, corrections, field evidence, processing state, and validation flags.
- **Validation Result**: A deterministic check outcome, such as passed, flagged, or not verifiable, with explanation, evidence, and applicable tolerance.
- **Workbook and Column Mapping**: A selected spreadsheet and worksheet, its detected headers, confirmed mapping, managed version, and write status.
- **Review Event**: A human-authored review status or note with actor, timestamp, and relationship to invoice flags; it does not represent payment approval.
- **Audit Event**: A timestamped, attributable account of a material user or system action, preserving relevant before/after values without unnecessary sensitive content.
- **Chat Session**: A user's conversation associated with selected invoices and their questions, assistant responses, and correction requests.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In evaluation on a representative, human-labeled sample, field-level extraction accuracy is reported separately for each supported file type and scan-quality group, and the share of records requiring correction is measurable.
- **SC-002**: Every seeded arithmetic mismatch and missing-PO case in the validation test set is flagged, and every case lacking necessary arithmetic inputs is reported as not verifiable.
- **SC-003**: Duplicate-detection precision and recall are measured on a labeled set of matching and non-matching records; flagged matches include the reason and comparison record.
- **SC-004**: In workbook acceptance tests, a confirmed record is appended exactly once, existing workbook rows and unrelated sheets remain unchanged, and the updated workbook is downloadable.
- **SC-005**: No spreadsheet entry is written before explicit user confirmation, and no workflow presents logging or data review as payment approval.
- **SC-006**: Authorized AP users can complete the upload-to-preview-to-confirmed-log journey in usability testing without assistance, and the completion rate and median elapsed time are recorded before launch thresholds are set.
- **SC-007**: The application records all required audit event types with actor and timestamp in acceptance testing, and access attempts by unauthorized users do not disclose protected invoice data.

## Assumptions

- Initial workbook integration is upload and download of `.xlsx` copies; direct Microsoft 365 or collaborative workbook editing is not included.
- The initial supported image formats are JPEG, PNG, and HEIC; file-size, page-count, and batch limits will be configured before launch.
- Field extraction uses a model-assisted process with text recognition as needed; the model may not support image input, so image/PDF OCR or conversion remains necessary.
- Arithmetic checks use a configurable currency-aware rounding tolerance, with decimal-safe calculations; rules for currencies and PO requirements will be configured by the organization.
- Duplicate matching is limited to the selected log and records accessible to the application; flags indicate possible matches, not definitive fraud or invalidity.
- Users can confirm logging even when flags remain, provided the flags remain visible and the application preserves review status. This action never authorizes payment.
- Authentication roles, hosting, data residency, retention periods, deletion policy, file limits, and organizational approval for external model processing are prerequisites for production deployment.
- Acceptance and quality thresholds for extraction accuracy, duplicate detection, performance, and operator completion time will be established using representative AP data before release.
