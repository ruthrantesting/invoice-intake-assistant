# Quickstart and Validation: Invoice Intake Assistant

This guide describes the current local development setup and the prerequisites for exercising data-backed features. See [API contract](contracts/api.md) and [data model](data-model.md).

## Prerequisites

- Linux, Python 3.12, uv, Node.js/npm, PostgreSQL, Tesseract plus language packs, and native PDF/HEIF libraries compatible with the selected packages.
- An organization-approved OIDC test identity/provider with operator, reviewer and administrator test accounts, and a private encrypted writable blob directory.
- For a live model check, a server-side OpenRouter credential and approval of the configured `qwen/qwen3.7-flash` provider/routing. Use synthetic invoices only until privacy review is complete. Never commit credentials or place them in frontend configuration.
- Representative synthetic text/scanned/mixed PDFs, JPEG/PNG/HEIC images, a safe custom-header `.xlsx` workbook, unsupported workbooks, and known duplicate/missing-PO examples. Set test-specific limits, currency tolerance, retention and permitted workbook profile explicitly.

## Setup and commands

From the repository root, `./run.sh` starts the local FastAPI and Vite servers and opens Google Chrome after the frontend responds. Alternatively, start each service separately:

`./run.sh` defaults to explicit local `PROTOTYPE_MODE=true` so the application is usable without OIDC or PostgreSQL. It stores state in an ignored local SQLite database and local blob directory, and auto-signs in the local prototype operator. The prototype uses rough deterministic text matching, displays low-confidence source evidence, and requires manual verification. It is not suitable for real sensitive invoice data or production. Set `PROTOTYPE_MODE=false` only after configuring OIDC, PostgreSQL, encryption, OCR, and production policy gates.

```bash
cd backend
uv sync --extra test
uv run pytest
uv run alembic upgrade head
uv run fastapi dev src/invoice_agent/main.py
```

In another terminal, after configuring PostgreSQL, the encryption key and blob storage, start the durable worker:

```bash
cd backend
uv run python -m invoice_agent.worker.runner
```

In a third terminal:

```bash
cd frontend
npm ci
npm run test
npm run dev
```

Run Playwright using the script in `frontend/package.json`. OCR tests requiring the Tesseract system executable are skipped where it is unavailable. Provider/model checks require approved external processing and credentials; ordinary tests must use deterministic substitutes. Configure credentials through an approved secret manager or untracked environment files, never source files.

### Required local configuration

- `DATABASE_URL`: PostgreSQL connection string used by the API and migrations.
- `DATA_ENCRYPTION_KEY`: base64-free raw AES key of 16, 24, or 32 bytes for local encrypted blob storage.
- `SESSION_SECRET`: at least 32 bytes for session token hashing; sign-in remains unavailable otherwise.
- `OIDC_ISSUER`, `OIDC_CLIENT_ID`, `OIDC_CLIENT_SECRET`, and `OIDC_CALLBACK_URL`: organization identity provider configuration.
- `EXTERNAL_PROVIDER_APPROVED=true`, `OPENROUTER_API_KEY`, and approved `OPENROUTER_ALLOWED_PROVIDERS`: required before model calls. Do not use invoice data before provider privacy and residency approval.
- `WORKBOOK_PROFILE_APPROVED=true`: explicitly signals organizational approval of the tested workbook compatibility profile.
- `CURRENCY_TOLERANCES_JSON`: configured currency-to-decimal tolerance map. Do not treat unapproved fallback tolerances as production policy.

The UI may be opened without these settings, but authenticated API calls and model/OCR-dependent operations are unavailable until configured. No demo identity is enabled by default. The model path fails closed until both provider approval and an explicit provider allowlist are configured.

## End-to-end validation scenarios

1. **Intake:** As an authorized operator, upload each supported document type. Verify status, preview, evidence, unknown/uncertain fields and safe failure on corrupt, encrypted, oversized or unreadable content.
2. **Validation:** Confirm a seeded mismatch is flagged, incomplete arithmetic is not verifiable, a missing PO is flagged, and a known duplicate identifies its match and scope. Correct a field and verify a new revision and refreshed validation.
3. **Existing log:** Upload a supported workbook with custom headers, map fields, preview destination/row/flags, and verify no row is appended before explicit confirmation. Confirm and download; inspect one appended row, unchanged other rows/sheets, leading-zero identifiers and safe text cells.
4. **New log and review:** Create a workbook, review its layout, log a flagged invoice, and verify flags/review state remain visible and logging is not payment approval. Record a reviewer note and inspect audit history.
5. **Retries and conflicts:** Repeat confirmation with the same key; verify one committed row. Change invoice revision, mapping, flags or workbook version after preview and verify conflict plus fresh confirmation requirement. Inject failures before and after candidate publication/commit and confirm recovery produces no false success or duplicate.
6. **Security:** Verify cross-tenant access and unauthorized download fail; malformed/ZIP-bomb workbooks, prompt-injection content and formula-like cell values cannot trigger actions or formula execution. Test keyboard navigation, labels, focus and status announcements.
7. **Operational gates:** On an approved human-labeled corpus measure extraction accuracy by format/quality, correction share, duplicate precision/recall and latency; obtain AP thresholds. Validate provider/model entitlement, data-processing approval, identity and role policy, retention, limits and workbook profile before production. The evaluation CLI expects JSON Lines rows with `format`, `quality`, `expected`, `predicted`, and optional boolean `expected_duplicate`/`predicted_duplicate` fields. Keep the corpus outside source control and use approved data only.
