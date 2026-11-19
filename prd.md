# Product Requirements Document: Invoice Intake Assistant

## 1. Overview

### Problem
Accounts-payable (AP) staff receive invoices as digital PDFs, scanned documents, phone photos, and iPhone HEIC images. Manually reading these files, checking amounts, identifying duplicates and missing purchase order (PO) numbers, and updating an Excel invoice log is slow and error-prone.

### Product goal
Provide a chat-based assistant that reads uploaded invoices, extracts and validates invoice information, and prepares entries for an existing Excel log or a new spreadsheet. Anything uncertain or potentially problematic is presented to a person for review.

### Safety boundary
The assistant **never approves an invoice for payment and never initiates, schedules, or executes a payment**. A user may confirm an extracted record for logging, but this is not invoice or payment approval. Any actual approval and payment occur outside this product.

## 2. Users and primary workflows

- **AP operator:** uploads invoices, asks questions, corrects extracted fields, reviews flags, and confirms records for the log.
- **AP reviewer:** examines flagged records and records a review outcome; any invoice approval remains in the organization's external process.
- **Administrator:** configures spreadsheet mappings, validation settings, access, and retention.

### Typical workflow
1. An authorized user starts a chat, uploads an invoice, and selects an existing Excel log or chooses to create a new one.
2. The assistant extracts the invoice data and displays a structured preview with source references where available.
3. The assistant checks totals, possible duplicates, and PO presence, and shows all flags and uncertainty.
4. The user reviews and, if needed, corrects the extracted values and spreadsheet mapping.
5. The user explicitly confirms the record for logging. The assistant appends it to the selected spreadsheet, preserving its existing structure, and reports the result.
6. If a record requires further review, the assistant retains its review status and flags in the application; it does not treat logging as approval.

## 3. Scope

### In scope for the initial release
- Chat interface for invoice intake, questions, corrections, and status.
- PDF, scanned PDF, common photo formats (JPEG and PNG), and HEIC uploads.
- Text extraction, OCR where needed, structured invoice extraction, and source references where available.
- Existing `.xlsx` log import, configurable column mapping, and creation of a new `.xlsx` log.
- Arithmetic checks, duplicate detection, missing-PO detection, and uncertainty flags.
- Human confirmation before any spreadsheet write, with review status tracked separately from payment approval.
- Audit trail, access control, and basic operational monitoring.

### Out of scope
- Approving invoices, initiating payments, banking integrations, or automatic posting to an ERP or accounting system.
- Automated PO matching against a procurement system or determining whether a missing PO is policy-compliant.
- Tax or legal compliance certification, fraud determination, or a guarantee that all duplicates will be detected.
- Direct editing of macro-enabled workbooks, legacy `.xls` files, or collaborative cloud spreadsheets in the initial release.

## 4. Functional requirements

### 4.1 Chat and file intake
- **FR-01:** The interface shall accept invoice uploads in PDF, JPEG, PNG, and HEIC formats and provide clear progress, success, and error states. File size, page-count, and batch limits shall be configurable and communicated before upload.
- **FR-02:** The user shall be able to ask questions about an uploaded invoice, correct extracted values, and request a preview or validation summary in chat. Responses must distinguish extracted facts from uncertainty and must not fabricate missing fields.
- **FR-03:** The system shall extract embedded PDF text where available and use OCR for scans or image-based pages. HEIC files shall be converted to a supported image format for processing while retaining the original file according to the retention policy.
- **FR-04:** Unsupported, encrypted, corrupted, unreadable, or oversized files shall be rejected or flagged with an actionable explanation. Unreadable fields shall remain blank and be flagged; they shall not be inferred as facts.
- **FR-05:** Each uploaded invoice shall have a unique internal ID and a processing state: received, processing, ready for review, logged, or failed. Review status shall be tracked separately.

### 4.2 Extraction and validation
- **FR-06:** Extract, when present: vendor name, invoice number, invoice date, due date, PO number, currency, subtotal, tax, shipping or other charges, discounts, and total. Capture line items when available and useful for validation. Preserve raw values and normalized values, and associate fields with page or source evidence where feasible.
- **FR-07:** Validate dates and amounts; compare the stated total with subtotal plus tax and other charges minus discounts, using decimal arithmetic and a configurable currency-aware rounding tolerance. If sufficient values are unavailable, mark the check as not verifiable rather than passed. Flag mismatches and ambiguous signs or currency.
- **FR-08:** Compare new invoices against the selected log and records already processed by the application. Use available normalized identifiers, including vendor, invoice number, date, amount, and currency, and exact file hashes where available. Flag possible duplicates and show the matching record and reason; never silently discard an invoice. Comparison is limited to accessible records and available fields.
- **FR-09:** Flag missing or unreadable PO numbers. A missing PO is a review issue, not proof that the invoice is invalid.
- **FR-10:** Flag low-confidence or conflicting extraction, illegible content, missing key fields, arithmetic mismatches, and possible duplicates. The interface shall explain each flag, display supporting evidence where available, and allow a user to correct fields or record a review outcome.
- **FR-11:** Re-run relevant validations after a correction and immediately before writing to the spreadsheet. Preserve the original extracted values, corrections, flags, and review history for audit.

### 4.3 Spreadsheet handling
- **FR-12:** Allow the user to upload and select an existing `.xlsx` workbook and worksheet. Show detected headers and provide a configurable mapping from invoice fields to the organization's columns. The user must confirm the mapping before the first write; reusable mappings may be saved for future use.
- **FR-13:** Preserve unrelated sheets, existing rows, headers, and workbook structure. Append only to the intended worksheet using the confirmed mapping; leave unmapped columns untouched or blank in the new row. Do not silently overwrite existing data. If safe preservation cannot be guaranteed, stop and explain the limitation.
- **FR-14:** Allow a user to create and download a new `.xlsx` log with a default set of invoice columns and configurable headers. Show the resulting column layout before the first write.
- **FR-15:** Display the proposed row, active flags, and destination before an explicit per-record confirmation to log. Flagged records may be logged after confirmation, but shall retain their review status and flags in the application. Logging or recording a review outcome must never be labeled or interpreted as invoice/payment approval.
- **FR-16:** Prevent duplicate writes caused by repeated confirmations or retries using a record-level idempotency key. Detect stale workbook versions or concurrent updates and require the user to reload or resolve the conflict rather than overwrite changes. On write failure, retain the record and report the failure without claiming it was logged.
- **FR-17:** Provide the updated workbook as a downloadable file. For an uploaded local workbook, the user is responsible for saving or replacing their local copy; no direct modification of their local file is implied. Persist the application-managed version for subsequent comparisons, subject to retention policy.
- **FR-18:** Treat invoice-derived spreadsheet content as untrusted: prevent formula injection and preserve invoice identifiers such as leading-zero invoice and PO numbers as text. Never execute workbook macros or formulas supplied by uploaded files.

### 4.4 Human review and audit
- **FR-19:** Provide review statuses such as not reviewed, needs review, and reviewed. A reviewer may record a reason or note; this status indicates data review only, not authorization to pay.
- **FR-20:** Keep an audit trail of uploads, extracted and corrected values, validation outcomes, mapping changes, user confirmations, log writes, and review actions, including actor and timestamp. Do not allow the AI to create a human confirmation or review action on its own.
- **FR-21:** Require authenticated access and role-appropriate permissions for uploads, viewing, reviewing, configuring mappings, and downloading logs. Display only records the user is authorized to access.

## 5. AI and technical requirements

### Required stack
- **Backend:** Python for invoice processing and chatbot logic.
- **API:** FastAPI connecting the frontend and backend.
- **Frontend:** React with TypeScript.
- **LLM:** `qwen/qwen3.7-flash` via OpenRouter, integrated using LangChain. Verify the model identifier, availability, context limits, and image-input support with the provider before implementation; do not assume vision capability. Use a separate OCR or document-processing component if required.

### Proposed architecture
1. React client handles chat, uploads, previews, corrections, mapping, flags, and downloads.
2. FastAPI authenticates requests, manages processing jobs and record state, and exposes document, chat, review, mapping, and spreadsheet operations.
3. Python document processing extracts PDF text or performs OCR, including HEIC conversion; a LangChain workflow sends the minimum necessary content to the configured model and validates structured output against a schema.
4. Deterministic Python validation checks arithmetic, required fields, and duplicates independently of the LLM.
5. A spreadsheet service reads and writes `.xlsx` files with version checks, safe cell handling, and idempotent writes. Persistent storage holds authorized files, records, mappings, and audit events.

The LLM is an extraction and conversational aid, not an authority for approvals or financial calculations. Treat uploaded documents and chat content as untrusted input; instructions inside an invoice must not override application rules or trigger actions. The model must not have tools for approval or payment.

## 6. Non-functional requirements

- **Security and privacy:** Encrypt data in transit and at rest; restrict access by role; validate uploads and scan for malware where supported. Do not expose secrets to the browser or logs. Document the data sent to OpenRouter and obtain organizational approval for external processing before production use.
- **Retention:** Make retention periods and deletion procedures configurable for invoices, extracted data, workbooks, and audit records, subject to organizational policy. Define how deletion interacts with audit and legal-hold requirements before launch.
- **Reliability:** Preserve processing and review state across failures. Provide clear retry paths; retries must not produce extra spreadsheet rows. Use controlled, recoverable file writes.
- **Observability:** Track processing failures, OCR failures, validation flags, write failures, and latency without logging unnecessary invoice content or sensitive data.
- **Accessibility:** Support keyboard navigation, accessible labels, and readable status and error messages.
- **Performance:** Show processing progress and measure end-to-end latency by file type and page count. Establish measurable targets after representative invoice testing.

## 7. Acceptance criteria

1. A user can upload a text PDF, scanned PDF, JPEG, PNG, or HEIC invoice and see either an extracted preview or a clear actionable failure.
2. The preview identifies extracted fields, missing or uncertain values, and available source evidence; a user can correct values before logging.
3. A known arithmetic mismatch is flagged; an invoice with insufficient values is marked not verifiable rather than passed.
4. A repeated invoice in the selected log is flagged as a possible duplicate with the matching record and explanation; a missing PO is separately flagged.
5. An existing `.xlsx` workbook with non-default headers can be mapped and confirmed; logging appends one correctly mapped row without changing unrelated sheets or existing rows.
6. A new workbook can be created with confirmed headers and downloaded with the logged record.
7. No spreadsheet row is written before explicit user confirmation; repeated confirmation or a retry does not create another row. A stale workbook conflict does not overwrite changes.
8. A flagged record can be logged while remaining visibly marked for review; neither logging nor review is represented as payment approval.
9. Corrections, validation outcomes, confirmations, and writes are auditable by actor and timestamp. Formula-like invoice values are stored safely as text.
10. No interface, model tool, or backend workflow can approve an invoice or initiate a payment.

## 8. Success measures

Measure on a representative, human-labeled set of invoices before agreeing on launch thresholds:
- Field-level extraction accuracy and percentage of records requiring manual correction, broken down by file type and scan quality.
- Precision and recall for duplicate flags against known examples; arithmetic and missing-PO detection rates.
- Median and 95th-percentile time from upload to confirmed log entry; processing and write failure rates.
- Percentage of flagged records reviewed and percentage of audit events successfully captured.

These metrics support evaluation, not a guarantee that all issues will be detected. Targets and baseline measurements are to be agreed with AP stakeholders.

## 9. Assumptions and open decisions

- The initial integration is file-based `.xlsx` upload and download, not direct access to a shared Excel or Microsoft 365 service. Confirm whether shared-workbook integration is needed later.
- Confirm required fields, default columns, allowed currencies, rounding tolerances, and whether PO requirements vary by vendor or invoice type.
- Confirm acceptable file/page limits, expected volume, batch behavior, and performance targets.
- Confirm identity provider, role definitions, hosting, data residency, external-model processing approval, and retention periods.
- Confirm the model identifier and whether it supports the required input modalities; select OCR and HEIC conversion components accordingly.
- Confirm whether audit records and review status need to be exported alongside the workbook and how reviewers are notified of outstanding flags.