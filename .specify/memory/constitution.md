<!--
Sync Impact Report
- Version change: uninitialized scaffold → 1.0.0 (initial project constitution)
- Modified principles: none; this establishes project-specific principles
- Added sections: core principles; product and technical constraints; development workflow
- Removed sections: unresolved template placeholders and examples
- Follow-up TODOs: confirm original ratification date; current date is used provisionally
-->
# Invoice Intake Assistant Constitution

## Core Principles

### I. Human Authority Over Financial Decisions
The system MUST NOT approve invoices, authorize payment, or initiate, schedule, or execute payments. AI output, spreadsheet logging, and reviewer notes MUST NOT be represented as financial approval. A person MUST explicitly confirm each spreadsheet write; invoice approval and payment remain in external authorized processes. This separation prevents automation from exercising financial authority.

### II. Evidence-Based Extraction and Explicit Uncertainty
Extracted values MUST be traceable to invoice content where feasible, and the system MUST distinguish source facts, normalized values, user corrections, and model-generated uncertainty. Missing or unreadable values MUST remain unknown rather than be guessed. Users MUST be able to inspect and correct extracted data before logging. The LLM is an extraction and conversational aid, not an authoritative source of financial facts.

### III. Deterministic Validation and Safe Exception Handling
Arithmetic, required-field checks, and duplicate comparisons MUST use deterministic application logic, not LLM judgment. Unverifiable checks MUST be labeled as such. Mismatches, possible duplicates, missing PO numbers, and low-confidence or conflicting data MUST be surfaced with explanations and supporting evidence when available. Flags MUST never silently discard or automatically invalidate an invoice.

### IV. Secure and Auditable Data Handling
All access to invoices, extracted data, and workbooks MUST be authenticated and role-appropriate. Uploads and invoice-derived cell values MUST be treated as untrusted input; the application MUST prevent formula injection and MUST NOT execute uploaded macros or formulas. Sensitive data MUST be protected in transit and at rest, and external model processing MUST be disclosed and approved before production use. Material user actions, corrections, validations, confirmations, and writes MUST be auditable by actor and timestamp.

### V. Reliable, Reversible Spreadsheet Operations
Spreadsheet writes MUST require explicit per-record user confirmation and MUST be idempotent across retries. The system MUST preserve existing workbook content and MUST stop rather than overwrite or corrupt data when safe writes cannot be assured. Stale or conflicting workbook versions MUST require resolution. Failed writes MUST leave the record available for retry and MUST NOT be reported as successful. Invoice identifiers such as leading-zero numbers MUST be preserved as text.

### VI. Testability and Operational Clarity
Changes to extraction, validation, permissions, or spreadsheet behavior MUST include automated tests for relevant success, failure, and safety cases. Integration tests MUST cover API contracts, document-processing boundaries, and workbook read/write behavior. The system MUST expose actionable processing status and failures while avoiding unnecessary invoice content in logs. Performance and extraction quality MUST be measured on representative, human-labeled invoices before targets are committed.

## Product and Technical Constraints

- The initial product MUST support chat-based invoice intake for PDFs, scanned documents, JPEG, PNG, and HEIC, with OCR or conversion where required.
- The initial spreadsheet workflow MUST support `.xlsx` upload, worksheet and column mapping, append-only writes, and downloadable updated workbooks, as well as creation of a new `.xlsx` log. Direct cloud workbook editing, `.xls`, and macro-enabled workbooks are out of scope unless separately approved.
- The required stack is Python for backend chatbot and document logic, FastAPI for the API, React with TypeScript for the user interface, and LangChain for orchestration with `qwen/qwen3.7-flash` through OpenRouter. Model identity, availability, input modalities, and data-processing terms MUST be verified before production use. OCR MUST be provided separately if model input does not support the required documents.
- Application behavior MUST remain safe if the LLM or OCR provider is unavailable, returns invalid data, or receives prompt-injection content in an invoice. The model MUST NOT have approval or payment tools.
- Retention periods, deletion procedures, hosting, data residency, identity provider, roles, file/page limits, and currency-specific tolerances MUST be documented and approved before production deployment.

## Development Workflow and Quality Gates

- Each feature MUST define observable acceptance criteria and preserve the financial-authority boundary in this constitution.
- Before release, tests MUST verify supported file handling, extraction uncertainty, arithmetic mismatch and unverifiable cases, duplicate and missing-PO flags, authorization, audit events, formula-injection defenses, explicit confirmation, idempotent writes, and workbook conflict handling as applicable.
- Spreadsheet changes MUST be tested against representative workbooks containing non-default headers, unrelated sheets, existing rows, leading-zero identifiers, and formula-like values.
- Production readiness MUST include review of external LLM data handling, access controls, retention and deletion, error recovery, and auditability.
- Any exception to a MUST-level rule requires a documented amendment to this constitution before implementation; configuration MUST NOT weaken the prohibition on automated approval or payment.

## Governance

This constitution governs product and engineering decisions for the Invoice Intake Assistant. Amendments require a documented rationale, review by the project owner and relevant security or accounts-payable stakeholders, and an update to the version and amendment date. Versioning follows semantic versioning: MAJOR for incompatible governance changes or removal/redefinition of a principle; MINOR for new principles or materially expanded requirements; PATCH for clarifications and non-semantic wording changes. Every feature review and release review MUST check compliance with the principles and quality gates above. Non-compliant changes MUST be corrected or deferred until an approved amendment is made. Product-specific unresolved decisions MUST be recorded and resolved before the affected capability is released.

**Version**: 1.0.0 | **Ratified**: TODO(RATIFICATION_DATE): confirm original adoption date | **Last Amended**: 2026-11-17
