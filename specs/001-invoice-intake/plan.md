# Implementation Plan: Invoice Intake Assistant

**Branch**: `001-invoice-intake` (feature identifier returned by setup; branch creation not performed) | **Date**: 2026-11-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-invoice-intake/spec.md`, `prd.md`, and project constitution.

## Summary

Provide authenticated AP staff a React chat and structured review workspace for uploading PDFs, scans, JPEG/PNG and HEIC invoices; extracting evidence-backed fields; deterministically checking totals, missing POs and duplicates; and explicitly confirming safe, idempotent logging to a mapped or newly created `.xlsx` workbook. A Python/FastAPI backend uses local document/OCR processing, LangChain/OpenRouter for schema-constrained extraction and grounded chat, PostgreSQL for state, jobs and audit, and immutable private workbook versions. The system has no invoice approval or payment functionality.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5.x; React 19. Pin compatible stable package versions and toolchain during implementation.

**Primary Dependencies**: FastAPI, Pydantic, LangChain with `langchain-openrouter`, OpenRouter `qwen/qwen3.7-flash`, pypdf, pypdfium2, Pillow/pillow-heif, Tesseract OCR, openpyxl, PostgreSQL driver/SQLAlchemy; React, Vite and an OpenAPI-generated typed client. Review licenses and platform support before selection is finalized.

**Storage**: PostgreSQL for tenants, roles, records, jobs, revisions, audit and workbook version pointers; private encrypted local filesystem for immutable blobs on a single host. No joint filesystem/database transaction; recovery uses staged immutable objects and transactional pointers.

**Testing**: pytest/HTTPX for unit, contract and integration tests; Playwright for end-to-end/accessibility; labeled invoice and workbook corpora, concurrency and crash-injection tests.

**Target Platform**: Linux server and modern desktop browsers; same-origin HTTPS deployment. Hosting, identity provider, actual deployment region and retention policy require stakeholder approval before production.

**Project Type**: Web application with separate Python API/worker and React frontend.

**Performance Goals**: Measure median/p95 upload-to-confirmed-log time and failure rates on representative inputs; agree quantitative thresholds and capacity with AP before launch. Show processing progress and enforce configured workload limits.

**Constraints**: Human confirmation for every write; no invoice/payment approval or payment actions; deterministic validation; deny-by-default authorization; no unsupported workbook mutation; approved external providers only. Exact limits, security policies and currency tolerances are production configuration decisions, not implicit defaults.

**Scale/Scope**: Single organization deployment initially with tenant-aware isolation; per-file processing through durable workers. PDF, JPEG, PNG, HEIC and `.xlsx` only. Direct shared-workbook integration, `.xls`, macros and ERP/payment integration excluded. Concurrency limits and volume targets determined from workload tests.

## Constitution Check

*Pre-research and post-design gate evaluation: PASS with release prerequisites; none of the principles are waived.*

| Principle | Planned evidence / gate |
| --- | --- |
| Human authority | Explicit authenticated UI confirmation binds exact preview; no chat/model write or payment/approval tool. Flagged logging is not financial approval. |
| Evidence and uncertainty | Structured extraction retains source evidence, raw/normalized values, nulls and corrections; unavailable evidence is explicit. |
| Deterministic validation | Decimal arithmetic, missing PO and explainable duplicate matching implemented outside the LLM and rerun before write. |
| Secure and auditable | OIDC-backed sessions, CSRF, tenant/record authorization, upload isolation, private encrypted blobs and transactional audit; external-provider approval blocks production. |
| Safe spreadsheets | Versioned compatibility allowlist, explicit text cells, confirmed preview, unique operation key, version compare-and-swap and immutable blob recovery; unsupported workbooks rejected. |
| Testability and observability | Automated tests across API, processing and spreadsheets, adversarial and crash/race scenarios, privacy-conscious telemetry and labeled evaluation. |

**Release prerequisites**: Confirm organizational role matrix, identity provider, privacy approval and routing for every external provider, storage/hosting/residency, retention and deletion, file limits, workbook support profile, currency/tolerance configuration, and AP evaluation thresholds. Model catalog presence does not establish account availability or production approval.

## Project Structure

### Documentation (this feature)

```text
specs/001-invoice-intake/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── api.md
└── tasks.md             # Generated later by /speckit-tasks
```

### Source Code (repository root)

```text
backend/
├── pyproject.toml
├── src/invoice_agent/
│   ├── api/             # routes, request/response models, auth dependencies
│   ├── domain/          # invoice, validation, confirmation, authorization rules
│   ├── services/        # document, extraction, chat, workbook, audit services
│   ├── persistence/     # DB models, repositories, immutable blob storage
│   └── worker/          # leased document-processing jobs
└── tests/
    ├── unit/
    ├── integration/
    └── contract/
frontend/
├── package.json
├── src/
│   ├── features/        # chat, invoice review, mapping, audit
│   ├── components/      # shared accessible controls
│   └── api/             # generated client and request integration
└── tests/               # UI and Playwright flows
```

**Structure Decision**: Separate backend and frontend projects within one repository. Processing workers use the same backend domain and persistence code; contract and failure tests cover service boundaries. Directory paths above are planned, not existing implementation.

## Complexity Tracking

No constitutional exceptions proposed. PostgreSQL, durable jobs, and immutable workbook blobs are justified by recovery, audit, version conflicts, and idempotency requirements; they cannot be replaced safely by in-process state or blind workbook writes.
