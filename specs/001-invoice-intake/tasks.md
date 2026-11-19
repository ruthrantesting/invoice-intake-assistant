---
description: "Actionable task list for Invoice Intake Assistant"
---

# Tasks: Invoice Intake Assistant

**Input**: Design documents from `specs/001-invoice-intake/` (`plan.md`, `spec.md`, `research.md`, `data-model.md`, `contracts/api.md`, and `quickstart.md`)

**Prerequisites**: Plan and specification are required; research, data model, API contract, quickstart, and project constitution were also used.

**Organization**: Tasks are grouped by user story. The constitution requires automated coverage of relevant success, failure, and safety cases, so story-specific tests are included.

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Initialize the planned backend and frontend projects and shared development configuration.

- [X] T001 Create `backend/pyproject.toml` for Python 3.12, FastAPI, Pydantic, SQLAlchemy/PostgreSQL, LangChain/OpenRouter and planned document/workbook dependencies; pin compatible versions and declare test tooling.
- [X] T002 [P] Create `frontend/package.json`, `frontend/tsconfig.json`, and `frontend/vite.config.ts` for React 19, TypeScript 5, Vite, accessible UI, Playwright, and generated API-client scripts.
- [X] T003 [P] Add repository `.gitignore`, `.env.example`, and `README.md` entries for local setup without credentials, synthetic-data-only provider checks, Tesseract/native prerequisites, and separate backend/worker/frontend commands.
- [X] T004 Configure Python lint/format/test tooling in `backend/pyproject.toml` and frontend lint/format/typecheck scripts in `frontend/package.json`.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Deliver security, persistence and service primitives required by all user stories.

**⚠️ CRITICAL**: Complete this phase before user-story implementation.

- [X] T005 Create SQLAlchemy database configuration and Alembic migration setup in `backend/src/invoice_agent/persistence/database.py` and `backend/alembic.ini`.
- [X] T006 Implement server-side OIDC session, tenant/role authorization, deny-by-default resource checks, secure cookie and CSRF dependencies in `backend/src/invoice_agent/api/auth.py` and `backend/src/invoice_agent/api/dependencies.py`.
- [X] T007 [P] Create FastAPI application assembly, request limits, common error responses and security middleware in `backend/src/invoice_agent/main.py` and `backend/src/invoice_agent/api/errors.py`.
- [X] T008 [P] Implement immutable private blob storage interface with generated IDs, hash verification, encryption configuration, atomic publication and fsync behavior in `backend/src/invoice_agent/persistence/blob_store.py`.
- [X] T009 [P] Implement durable PostgreSQL job records, leases, retries and idempotent worker claims in `backend/src/invoice_agent/worker/queue.py` and `backend/src/invoice_agent/persistence/job_repository.py`.
- [X] T010 Implement tenant-scoped audit-event persistence and transaction helper so mutations and audit records commit together in `backend/src/invoice_agent/persistence/audit_repository.py` and `backend/src/invoice_agent/services/audit_service.py`.
- [X] T011 Generate the typed TypeScript API client from the FastAPI OpenAPI schema and add authenticated request/CSRF handling in `frontend/src/api/client.ts` and `frontend/package.json`.
- [X] T012 Add tenant, role, session and authorization persistence models plus the initial shared migration in `backend/src/invoice_agent/persistence/models.py` and `backend/migrations/versions/0001_shared_foundation.py`.

**Checkpoint**: Database, authorization, audit, blob and durable-job foundations are ready.

---

## Phase 3: User Story 1 - Extract and review an invoice (Priority: P1) 🎯 MVP

**Goal**: Upload supported invoice documents, extract evidence-backed fields with explicit uncertainty, and let an operator correct fields while retaining original values.

**Independent Test**: With an authorized operator, upload a representative PDF and image; verify progress, structured values, unknown/uncertain fields and source evidence, then correct a field and confirm both the correction and original extraction remain available.

### Tests for User Story 1

- [X] T013 [P] [US1] Add parser/extraction unit tests for embedded PDF text, scanned/mixed pages, rotated HEIC/JPEG, unreadable fields, malformed/encrypted files and prompt-injection text in `backend/tests/unit/test_document_extraction.py`.
- [X] T014 [P] [US1] Add API contract tests for upload, job status/retry, invoice detail, source retrieval, field correction and chat non-write semantics in `backend/tests/contract/test_invoice_intake_api.py`.
- [X] T015 [P] [US1] Add an end-to-end upload, preview, uncertainty and correction flow with keyboard/accessibility assertions in `frontend/tests/invoice-review.spec.ts`.

### Implementation for User Story 1

- [X] T016 [US1] Add invoice, revision, field-evidence and line-item persistence models; enforce `processing status (received, processing, ready_for_review, logged, failed)`, `review status (not_reviewed, needs_review, reviewed)`, nullable invoice fields, immutable original evidence and revision uniqueness in `backend/src/invoice_agent/persistence/invoice_models.py` and `backend/migrations/versions/0002_invoice_records.py`.
- [X] T017 [US1] Implement signature/type, byte, page, pixel and corruption checks for PDF/JPEG/PNG/HEIC uploads, returning actionable safe errors in `backend/src/invoice_agent/services/upload_service.py`.
- [X] T018 [US1] Implement PDF text extraction/rendering, image orientation and HEIC conversion, mixed-page OCR using Tesseract, and page/region provenance in `backend/src/invoice_agent/services/document_service.py`.
- [X] T019 [US1] Implement schema-constrained extraction and grounded responses with `qwen/qwen3.7-flash` via LangChain `ChatOpenRouter`; keep provider/model failures actionable and do not silently substitute models in `backend/src/invoice_agent/services/extraction_service.py` and `backend/src/invoice_agent/services/model_client.py`.
- [X] T020 [US1] Implement revision creation and field correction preserving raw, normalized, corrected and evidence values; absent/unreadable values remain null and corrections create an audit event in `backend/src/invoice_agent/services/invoice_service.py`.
- [X] T021 [US1] Implement idempotent processing worker stages for document extraction and record state transitions, with safe error codes and retry behavior in `backend/src/invoice_agent/services/invoice_worker.py`.
- [X] T022 [US1] Add authenticated upload, invoice detail/source, job status/retry and field-correction routes matching `contracts/api.md` in `backend/src/invoice_agent/api/invoices.py` and `backend/src/invoice_agent/api/jobs.py`.
- [X] T023 [US1] Implement authorized chat session/history and grounded message endpoints; correction requests must route through validated field-correction workflow, and no chat action can confirm or write in `backend/src/invoice_agent/api/chat.py` and `backend/src/invoice_agent/services/chat_service.py`.
- [X] T024 [US1] Build the accessible upload, processing progress, field/evidence preview, uncertainty labels, correction form and invoice-scoped chat UI in `frontend/src/features/invoice-review/InvoiceReviewPage.tsx` and `frontend/src/features/chat/InvoiceChat.tsx`.
- [X] T025 [US1] Add file type/size/page limits configuration and user-visible upload-limit endpoint in `backend/src/invoice_agent/api/settings.py` and `backend/src/invoice_agent/config.py`.

**Checkpoint**: An operator can independently upload, inspect and correct an invoice without any spreadsheet write.

---

## Phase 4: User Story 2 - Identify issues for human review (Priority: P1)

**Goal**: Run deterministic, explainable total, duplicate and PO checks; explicitly distinguish passed, flagged and not-verifiable outcomes.

**Independent Test**: Run seeded invoices with arithmetic mismatch, insufficient arithmetic inputs, matching accessible records and missing PO; verify the correct outcome, comparison scope and explanation for each.

### Tests for User Story 2

- [X] T026 [P] [US2] Add decimal arithmetic tests for configured currency tolerance, signs/discounts, absent components and not-verifiable outcomes in `backend/tests/unit/test_arithmetic_validation.py`.
- [X] T027 [P] [US2] Add duplicate and missing-PO tests for normalized identifiers, missing identifiers never equal, accessible comparison scope and explanatory matches in `backend/tests/unit/test_issue_validation.py`.
- [X] T028 [P] [US2] Add API contract coverage for validation result outcomes, reasons, evidence, authorized matches and scope in `backend/tests/contract/test_validation_api.py`.

### Implementation for User Story 2

- [X] T029 [P] [US2] Add validation-run and validation-result persistence models enforcing check types (`arithmetic`, `duplicate`, `missing_po`, `field`, `date`, `currency`) and outcomes (`passed`, `flagged`, `not_verifiable`) in `backend/src/invoice_agent/persistence/validation_models.py` and `backend/migrations/versions/0003_validation.py`.
- [X] T030 [US2] Implement decimal-safe total arithmetic with configured currency-aware tolerances; missing components are not zero and insufficient inputs return `not_verifiable` in `backend/src/invoice_agent/domain/arithmetic_validation.py`.
- [X] T031 [US2] Implement normalized invoice identifier and exact-file duplicate comparison against authorized records, recording matched record, reason and comparison scope without discarding invoices in `backend/src/invoice_agent/domain/duplicate_validation.py`.
- [X] T032 [US2] Implement missing/unreadable PO and uncertain/conflicting field checks as review flags, never as automatic invalidity, in `backend/src/invoice_agent/domain/issue_validation.py`.
- [X] T033 [US2] Implement validation orchestration that stores version/configuration-bound runs and reruns applicable checks after revision corrections in `backend/src/invoice_agent/services/validation_service.py`.
- [X] T034 [US2] Add the authorized validate endpoint with workbook/version context, privacy-safe errors and stale-version conflict handling in `backend/src/invoice_agent/api/validation.py`.
- [X] T035 [US2] Display issue summaries, passed/flagged/not-verifiable states, explanations, match scope and evidence without color-only indicators in `frontend/src/features/invoice-review/ValidationSummary.tsx`.

**Checkpoint**: Deterministic checks can be run and verified independently on invoice records and authorized comparison data.

---

## Phase 5: User Story 3 - Confirm and log a record (Priority: P1)

**Goal**: Map to an existing or new `.xlsx` workbook, preview the exact row, and append once only after explicit human confirmation.

**Independent Test**: Map a custom-header workbook, preview a row and confirm; verify no write before confirmation, exactly one row after retry, preserved existing content, safe text cells and downloadable managed workbook. Repeat with a stale version and verify a conflict without overwrite.

### Tests for User Story 3

- [X] T036 [P] [US3] Add workbook tests for custom headers, multiple sheets, existing rows, formulas/macros/unsupported ZIP parts, protected files, leading zeros, formula-like text and round-trip preservation in `backend/tests/integration/test_workbook_safety.py`.
- [X] T037 [P] [US3] Add contract tests for workbook upload/new, mapping, preview, confirmation idempotency, operation status and immutable download in `backend/tests/contract/test_workbook_logging_api.py`.
- [X] T038 [P] [US3] Add confirmation UI end-to-end tests proving no pre-confirmation write, one append on retry, review flags remain visible and stale preview requires reconfirmation in `frontend/tests/workbook-confirmation.spec.ts`.

### Implementation for User Story 3

- [X] T039 [P] [US3] Add workbook/version/mapping/preview/operation persistence models; enforce unique tenant-workbook idempotency key, same key+digest replay, changed digest conflict and unique committed append per invoice/workbook in `backend/src/invoice_agent/persistence/workbook_models.py` and `backend/migrations/versions/0004_workbooks.py`.
- [X] T040 [US3] Implement `.xlsx` package inspection, ZIP/resource limits and fail-closed compatibility profile; reject macros, encryption, unsafe or unsupported structures and unverified preservation cases in `backend/src/invoice_agent/services/workbook_inspection.py`.
- [X] T041 [US3] Implement safe workbook loading, selected-sheet header detection, custom field mappings, append-only row serialization and explicit string cells; preserve leading-zero identifiers, reject invalid strings and verify serialized output in `backend/src/invoice_agent/services/workbook_service.py`.
- [X] T042 [US3] Implement new managed `.xlsx` creation with configurable headers and a reviewed worksheet layout in `backend/src/invoice_agent/services/workbook_creation_service.py`.
- [X] T043 [US3] Implement mapping validation and human-confirmed mapping revisions; reject duplicate/invalid mappings and leave unmapped cells blank in `backend/src/invoice_agent/services/mapping_service.py`.
- [X] T044 [US3] Implement exact-row log previews bound to invoice revision, mapping, workbook version, validation/flags digest and expiry; previews must not write in `backend/src/invoice_agent/services/log_preview_service.py`.
- [X] T045 [US3] Implement explicit confirmation with reauthorization and revalidation, staged immutable candidate blob, workbook version compare-and-swap, transactional operation/invoice/audit update, crash recovery and idempotent retry in `backend/src/invoice_agent/services/log_operation_service.py`.
- [X] T046 [US3] Add workbook upload/metadata/new/mapping, log-preview, confirmation, operation-status and version-download routes matching `contracts/api.md` in `backend/src/invoice_agent/api/workbooks.py` and `backend/src/invoice_agent/api/logging.py`.
- [X] T047 [US3] Build workbook selection, mapping review, new-log layout, exact proposed-row/flags/destination preview, explicit per-record confirmation and managed-copy download UI in `frontend/src/features/workbooks/WorkbookSetup.tsx` and `frontend/src/features/workbooks/LogConfirmation.tsx`.

**Checkpoint**: A reviewed invoice can be safely appended to a managed workbook exactly once, only after a human confirmation.

---

## Phase 6: User Story 4 - Review processing state and history (Priority: P2)

**Goal**: Let authorized reviewers record a data-review outcome/note and inspect attributable processing and action history without implying payment authorization.

**Independent Test**: Process, correct and log a flagged invoice; record a reviewer note and inspect the timeline for actor, timestamps, original values, corrections, flags, confirmation and write result. Verify unauthorized access is denied without disclosing protected records.

### Tests for User Story 4

- [X] T048 [P] [US4] Add authorization tests covering tenant and record isolation for invoice, audit, review, workbook and download operations in `backend/tests/integration/test_authorization_boundaries.py`.
- [X] T049 [P] [US4] Add audit/review contract tests for allowed review states, attributed note, event pagination and non-approval semantics in `backend/tests/contract/test_review_audit_api.py`.
- [X] T050 [P] [US4] Add reviewer history UI flow and keyboard-accessibility checks in `frontend/tests/review-history.spec.ts`.

### Implementation for User Story 4

- [X] T051 [US4] Implement review-event persistence with status limited to `not_reviewed`, `needs_review`, `reviewed`, reviewer, timestamp and optional note; review is data review only in `backend/src/invoice_agent/persistence/review_models.py` and `backend/migrations/versions/0005_review_events.py`.
- [X] T052 [US4] Implement review outcome/note service and authenticated route with tenant/record authorization and audit attribution in `backend/src/invoice_agent/services/review_service.py` and `backend/src/invoice_agent/api/reviews.py`.
- [X] T053 [US4] Implement paginated, authorized audit-history query for upload, extraction, corrections, validation, mapping, confirmation, write and review events in `backend/src/invoice_agent/services/audit_query_service.py` and `backend/src/invoice_agent/api/audit.py`.
- [X] T054 [US4] Build processing/review status display, review note form and chronological action history with explicit data-review-not-payment wording in `frontend/src/features/audit/InvoiceHistory.tsx` and `frontend/src/features/audit/ReviewPanel.tsx`.

**Checkpoint**: Authorized users can review and audit the invoice lifecycle; no action constitutes invoice or payment approval.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Verify end-to-end safety, operational readiness and release gates across stories.

- [X] T055 [P] Add crash-injection and concurrent-confirmation integration coverage for orphan candidate recovery, missing/corrupt referenced blobs, version races and exactly-once append in `backend/tests/integration/test_write_recovery_and_concurrency.py`.
- [X] T056 [P] Add Playwright cross-story accessibility coverage for keyboard navigation, labels, focus management, status announcements and non-color status indicators in `frontend/tests/accessibility.spec.ts`.
- [X] T057 Add privacy-conscious structured operational logging and metrics for job states, processing latency and safe failure codes without invoice content or secrets in `backend/src/invoice_agent/observability.py`.
- [X] T058 Add labeled-corpus evaluation scripts reporting extraction accuracy by supported file type/scan quality, correction share, duplicate precision/recall and measured latency in `backend/tests/evaluation/evaluate_invoice_corpus.py`.
- [X] T059 Update `specs/001-invoice-intake/quickstart.md` with actual setup/test/worker commands and document synthetic-data-only model integration plus release prerequisites in `README.md`.
- [X] T060 Validate production configuration gates for OIDC roles, external-provider approval/routing, storage/residency, retention/deletion, upload limits, workbook profile, currency tolerance and AP thresholds in `backend/src/invoice_agent/config.py` and `specs/001-invoice-intake/quickstart.md`.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies; complete project scaffolding first.
- **Foundational (Phase 2)**: Depends on Setup; blocks every story because persistence, authorization, API, blobs, jobs and audit are shared prerequisites.
- **US1 (Phase 3)**: Depends on Phase 2; establishes persisted invoice revisions and evidence.
- **US2 (Phase 4)**: Depends on Phase 2 and the invoice revision/evidence contract from US1; requires validation context and authorized comparison records.
- **US3 (Phase 5)**: Depends on Phase 2, US1 and US2; writes reviewed invoice data and must revalidate before commit.
- **US4 (Phase 6)**: Depends on Phase 2 and the audit events produced by US1-US3; review and history expose the complete lifecycle.
- **Polish (Phase 7)**: Cross-cutting; run after affected capabilities exist, with release gates completed before production.

### User Story Completion Order

- **US1 (P1)** → **US2 (P1)** → **US3 (P1)** → **US4 (P2)** is the safe MVP sequence because logging consumes extraction and validation outputs and full history consumes their audit events.
- US2's deterministic domain checks can be developed in parallel with independent US1 UI work once the invoice revision interface is agreed. US3 workbook inspection and creation can proceed alongside independent US2 UI work, but confirmation integration requires validation and invoice APIs.
- US4 authorization and audit tests can be prepared early; lifecycle history is complete only after the preceding story events are implemented.

### Parallel Opportunities

- Setup tasks T002-T004 can run in parallel with backend scaffolding T001 when changes do not overlap.
- Foundational tasks T007-T009 can proceed in parallel after database conventions are agreed; T010 depends on persistence configuration and T011 depends on the OpenAPI application surface.
- In US1, T013-T015 test authoring and T016-T017 model/upload work can proceed in separate files; extraction/OCR and frontend work can parallelize after interface schemas are agreed.
- In US2, T026-T028 tests, T030-T032 rule implementations and T035 UI can parallelize after validation result shapes are agreed.
- In US3, T036-T038 tests and T040-T043 workbook/mapping services can be split across files; T045 confirmation must follow blob, mapping, preview and validation contracts.
- In US4, T048-T050 test authoring can parallelize, while review model/service and audit query/UI are separate once event schemas are agreed.

### Parallel Example: User Story 1

```text
Task T013: Parser/extraction unit tests in backend/tests/unit/test_document_extraction.py
Task T014: Intake API contract tests in backend/tests/contract/test_invoice_intake_api.py
Task T015: Invoice review UI end-to-end tests in frontend/tests/invoice-review.spec.ts
```

### Parallel Example: User Story 3

```text
Task T036: Workbook safety tests in backend/tests/integration/test_workbook_safety.py
Task T037: Workbook/logging API contract tests in backend/tests/contract/test_workbook_logging_api.py
Task T038: Confirmation flow UI tests in frontend/tests/workbook-confirmation.spec.ts
```

## Implementation Strategy

### MVP First

1. Complete Phase 1 and Phase 2.
2. Complete US1 and verify upload-to-evidence-backed-preview-to-correction independently.
3. Complete US2 and verify deterministic flags and not-verifiable outcomes.
4. Complete US3 for explicit, safe, idempotent logging; this is the first end-to-end operational MVP.
5. Add US4 for review notes and full history before broad operational rollout.

### Incremental Delivery

Deliver each story only after its independent criteria pass. Use synthetic invoices for model/provider checks until privacy and routing approval; production remains blocked until documented release prerequisites are approved. Keep payment approval and payment execution outside the product at every stage.

## Notes

- Every task line uses `- [ ] T###`, includes a file path, and uses `[P]` only where the work can proceed in parallel without touching the same implementation artifact or depending on incomplete work.
- User-story tasks carry exactly one `[US#]` label; setup, foundational and polish tasks have none.
- Tests are included because the constitution and acceptance requirements call for automated success, failure and safety verification. Implement and run each story's tests with the relevant capability.
- Numeric production thresholds, retention periods and unsupported workbook behavior are not invented here; configure and obtain stakeholder approval as specified in the plan and release gates.