# API Contract: Invoice Intake Assistant

This is a design contract, not an implemented API. Paths are relative to `/api/v1`. Responses are JSON except file uploads/downloads. All routes require an authenticated session and tenant/resource authorization. Mutations require CSRF protection. No endpoint approves an invoice or executes payment. Errors use `{ "code": "...", "message": "...", "details": {} }` without sensitive data.

## Common semantics

- Opaque IDs never substitute for authorization; unauthorized objects return a non-disclosing `404`; missing authentication returns `401`, unauthorized actions `403`.
- `400` malformed requests; `413` request/file too large; `415` unsupported format; `422` invalid values or unsupported workbook; `409` stale revision, preview, version or idempotency mismatch; `429` rate limited; `503` transient provider/service failure.
- Amounts are decimal strings, never binary floating point; dates use ISO dates where valid; raw values and source references are retained separately. Unknown values are `null` with a reason where available.
- Pagination: list responses have `items` and nullable `next_cursor`; filtered to the caller's authorized scope. Public errors and operational logs exclude document content and secrets.

## Session and configuration

| Method & path | Contract |
| --- | --- |
| `GET /session` | Current user, tenant, roles and CSRF token or session bootstrap information. Authentication uses organization-approved OIDC sign-in/session flow. |
| `GET /settings/upload-limits` | Allowed formats and current file, page, batch and byte limits for display before upload. |

## Invoices and processing

| Method & path | Contract |
| --- | --- |
| `POST /invoices` | Multipart `file`; validate PDF/JPEG/PNG/HEIC, limits and permissions; `202` returns `{invoice_id, job_id, status}`. Each upload is a distinct record, even if duplicate. |
| `GET /invoices/{id}` | Return current revision, field raw/normalized/corrected values, evidence, processing/review status and current validation summaries. |
| `GET /invoices/{id}/source` | Authorized download/view of original source; safe content disposition/type and no active content execution. |
| `GET /jobs/{id}` | Authorized status, stage, progress when known and safe failure/retry information. |
| `POST /invoices/{id}/retry` | Authorized explicit retry for a failed processing job; `202` and job ID. |
| `PATCH /invoices/{id}/fields` | `{expected_revision, changes}`; create new revision, preserve original, audit correction and rerun checks; `409` on stale revision. |
| `POST /invoices/{id}/validate` | `{workbook_id, workbook_version_id, mapping_id}`; return rule outcomes, reasons, authorized potential matches and comparison scope. If version changes return `409`. |
| `POST /invoices/{id}/review` | `{status, note}` with `status` in `not_reviewed`, `needs_review`, `reviewed`; record human actor/time; not an approval. |
| `GET /invoices/{id}/audit` | Paginated authorized history of extraction, changes, flags, review, mapping, confirmation and write events. |

## Chat

| Method & path | Contract |
| --- | --- |
| `POST /chat/sessions` | `{invoice_id}`; create an authorized session. |
| `POST /chat/sessions/{id}/messages` | `{message}`; return grounded response and available citations or uncertainty. Correction requests must resolve through validated field-correction workflow. No chat request, tool call or response can perform confirmation, spreadsheet write, invoice approval or payment. |
| `GET /chat/sessions/{id}/messages` | Return authorized paginated message history. |

## Workbook mapping, previews and writes

| Method & path | Contract |
| --- | --- |
| `POST /workbooks` | Multipart `.xlsx`; validate package and supported-feature profile; create immutable managed copy and return workbook/version IDs and selectable sheets/headers. Reject unsupported features without modifying the source. |
| `POST /workbooks/new` | `{name, headers}`; create managed blank workbook and return version, worksheet and layout. |
| `GET /workbooks/{id}` | Metadata, current version, sheets/headers and authorized mappings. |
| `POST /workbooks/{id}/mappings` | `{expected_version_id, sheet, field_to_column}`; user confirms mapping explicitly, persist new mapping revision and audit. |
| `POST /invoices/{id}/log-preview` | `{invoice_revision, workbook_id, workbook_version_id, mapping_id}`; validate and return `preview_id`, expiration, exact destination/row, flags, comparison scope and digest. Does not write. |
| `POST /invoices/{id}/log-confirmations` | Requires `Idempotency-Key` header and `{preview_id, preview_digest}` from an explicit human UI action. Reauthorize, rerun checks and verify revision/mapping/flags/version. `200` returns committed operation/version; `202` pending with operation ID; `409` on changed preview, stale workbook, or key reused for different content. The same key/digest returns the original operation result. No confirmation by chat, job or model. |
| `GET /log-operations/{id}` | Authorized pending/committed/conflict/failed outcome. `committed` only after version pointer, operation and audit commit. |
| `GET /workbooks/{id}/versions/{version_id}/download` | Download authorized immutable version; application copy does not automatically replace local original. |

## Protocol invariants

- Confirmation is bound to the exact preview and authenticated human; material changes invalidate it and require new explicit confirmation. Logs and reviews never imply payment approval.
- Failed writes keep the invoice retryable; repeated operation requests must not append twice. A crash between blob publish and DB commit cannot be reported as success; reconcile orphan candidates.
- Workbook versions may contain pre-existing formulas only if an explicitly tested supported profile permits them; the application never evaluates them. Unknown structures, protected workbooks, macros, signatures and unverified features are rejected.
- Service-side validation enforces scope, file signatures, limits, tenant access and spreadsheet-safe string cells regardless of client/model behavior.
