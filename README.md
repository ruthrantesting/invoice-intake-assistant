# Invoice Intake Assistant

A human-reviewed invoice intake application. It extracts evidence-backed fields, runs deterministic checks, and prepares confirmed `.xlsx` log entries. It does not approve invoices or initiate payments.

## Development prerequisites

- Python 3.12, uv, Node.js/npm, PostgreSQL and Tesseract OCR (production). The prototype needs only uv and Node.js/npm: a bundled local OCR engine (RapidOCR) is used when Tesseract is not installed.
- Native libraries required by `pypdfium2` and `pillow-heif` on your Linux distribution.
- Organization-approved OIDC configuration and private encrypted blob storage for integrated testing.
- Keep credentials in an approved secret manager or local untracked environment file; never put secrets in frontend configuration.

## Setup

Install Python dependencies with `cd backend && uv sync --extra test`, and frontend dependencies with `cd frontend && npm ci`. For a local-only prototype, run `./run.sh` from the repository root; it explicitly enables `PROTOTYPE_MODE=true`, uses local SQLite and local encrypted blobs, creates a development-only `Jamie Davis` session, and starts the processing worker. In a remote VS Code workspace, `.vscode/settings.json` forwards port 5173 and opens the app in your local browser; do not open the remote machine's `127.0.0.1` directly. If it does not open automatically, use **Ports** → **Invoice Intake UI** → **Open in Browser**. Keep the `./run.sh` terminal running. This mode is not production-secure and is not for real sensitive invoices. It reads uploads with local OCR and simple text-pattern extraction (low confidence, never guessed, always shown with source evidence) for manual verification, not the approved LLM. Missing "other charges" and "discounts" are pre-filled as 0.00 and flagged as assumptions; a bare `$` is not turned into a currency code. Set `PROTOTYPE_MODE=false` to require configured organization OIDC and PostgreSQL. Production requires all identity, provider, retention, residency, workbook and currency approvals described in `specs/001-invoice-intake/quickstart.md`.

**Prototype walkthrough:** run `./run.sh` → choose a PDF/JPEG/PNG/HEIC invoice → review/correct the extracted fields → **Run checks** → **Set up** a destination (create a new log or upload an `.xlsx`) → confirm the column mapping → review the preview → **Confirm logging** → **Download managed workbook**. Nothing is written until you confirm, and nothing is approved or paid.

The UI has an explicit empty upload state and API-backed invoice, validation, workbook mapping, chat, and audit flows. Data-backed features require a running database and authenticated organization OIDC session. Tests do not establish production readiness.

If the login link is not shown, organization OIDC is not configured in the backend environment. If sign-in works but upload returns `storage_not_configured`, configure `DATA_ENCRYPTION_KEY` and PostgreSQL; errors from upload display the backend's safe error reason. Image and scanned-PDF OCR use Tesseract when installed (with the appropriate language pack), otherwise the bundled RapidOCR engine. The app does not accept a `file://` URL pasted as a path: use the **Choose a local file** picker to select the file, then the application uploads its bytes.

Use synthetic invoices only for model/provider checks until the organization approves OpenRouter and every possible routed provider for data processing, retention, and residency. Never silently substitute the required model. Production use is blocked until identity/role policy, storage/hosting, retention/deletion, upload limits, workbook compatibility profile, currency tolerances and AP quality/performance thresholds are approved.
