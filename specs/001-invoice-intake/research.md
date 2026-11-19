# Phase 0 Research: Invoice Intake Assistant

## 1. Model integration and workflow

**Decision**: Use the required `qwen/qwen3.7-flash` through OpenRouter and LangChain's `ChatOpenRouter`; call the model directly with a Pydantic structured-output schema for extraction and grounded conversational answers. Business routing, validation and all write authorization remain deterministic application code. Chat has no write, filesystem, payment, or approval tools. A direct model call is appropriate because this feature does not require autonomous tool selection; revisit the installed `langchain-build-agent` guidance if that changes.

**Rationale**: The [OpenRouter catalog](https://openrouter.ai/api/v1/models) reported the model as accepting text/image/video, 1M context and supporting tools and response format at research time. This is discovery, not a successful authenticated inference or provider-policy verification. [ChatOpenRouter documentation](https://docs.langchain.com/oss/python/integrations/chat/openrouter) provides the provider integration. Strict structured-output behavior, account availability, current prices, endpoint region, routing and approved provider must be verified with synthetic data before use; never silently replace the required model.

**Alternatives**: A tool-calling Deep Agent is not necessary for the specified chat and extraction workflow; its additional capabilities expand the security surface. LangGraph can be added for explicitly controlled complex workflows but is not required for the initial direct-call design. Model output is not trusted as validation or authorization.

## 2. Document extraction and OCR

**Decision**: Use `pypdf` for embedded text and page references and `pypdfium2` to render pages; Pillow plus `pillow-heif` converts HEIC frames with orientation handling; Tesseract OCRs rendered and image content. Retain the original, track page/region provenance where feasible, and flag unreadable or conflicting values. Process mixed pages for image content as well as text. Pin compatible versions, validate PDF renderer and HEIC native dependencies and run parsers in a resource-limited isolated worker.

**Rationale**: Local OCR avoids another external invoice-data recipient; [pypdf](https://pypdf.readthedocs.io/en/stable/user/extract-text.html) describes text extraction limitations, [pypdfium2](https://pypdfium2.readthedocs.io/en/stable/) renders PDFs, [pillow-heif](https://pillow-heif.readthedocs.io/en/latest/pillow-plugin.html) supports HEIF input and [Tesseract](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html) documents preprocessing and OCR limitations. No OCR is assumed error-free. Test skew, frames, mixed content and license/OS dependencies on real target platforms.

**Alternatives**: PyMuPDF offers extraction and rendering but has AGPL/commercial licensing implications. Managed invoice OCR can be assessed against labeled samples after external-data, residency and retention approvals. Vision model input may be evaluated, but cannot replace proven OCR and source evidence.

## 3. Spreadsheet safety and recoverability

**Decision**: Use `openpyxl` only with an explicitly versioned, tested `.xlsx` compatibility profile. Inspect the ZIP package and workbook features before opening, reject macros, encryption, unsafe ZIPs, unrecognized parts, protected or unsupported structures and any workbook whose unchanged content cannot be reliably preserved. Explicitly type untrusted values as strings, verify serialized cells, reject invalid/oversized strings, and never execute formulas. Restrict append to a proven-empty destination. Preserve originals and immutable managed versions.

**Rationale**: [openpyxl warns](https://openpyxl.readthedocs.io/en/stable/tutorial.html#loading-from-a-file) that shapes may be lost on open/save; successful parsing is not proof of safe preservation. [openpyxl security guidance](https://openpyxl.readthedocs.io/en/stable/index.html#security) advises protecting XML parsing. Check cell XML and spreadsheet compatibility against a representative corpus; existing formulas can be evaluated by a user's spreadsheet client even though the service never evaluates them, so initially reject them unless a safe supported profile is proven. This is a deliberate fail-closed subset, not support for every possible workbook.

**Alternatives**: Blind load/save risks destroying unrelated content. Direct XML patching may preserve more features but introduces complex format and security risks; consider it only after corpus-based verification. A local uploaded file cannot be monitored for subsequent user edits.

## 4. Concurrency, jobs and storage

**Decision**: Use PostgreSQL as authoritative state and audit store, a durable job queue (PostgreSQL-backed job table with leased, retryable workers), and private encrypted filesystem blob storage on one host initially. Store immutable blobs by generated ID/checksum, with workbook current-version pointer and operation state in PostgreSQL. Prepare and durably publish a candidate blob, then use a short transaction with a workbook row lock to conditionally advance the version and atomically commit write outcome, invoice state and audit. Bind a per-record idempotency key and request digest to exact invoice revision, mapping, flags and expected workbook version. Revalidate immediately prior to commit; stale/materially changed data requires new preview and confirmation.

**Rationale**: DB and filesystem have no joint transaction. Same-filesystem atomic publish, file and directory `fsync`, and a transactional pointer prevent partial publication; reconcile orphan candidates after a crash and stop on missing or mismatched referenced blobs. Unique constraints and version compare-and-swap handle retries and concurrent writers. See [PostgreSQL locks](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS) and [Python os.replace](https://docs.python.org/3/library/os.html#os.replace). A multi-host/object-store deployment needs equivalent immutable-object durability and conditional publication, not local filesystem assumptions.

**Alternatives**: In-process background jobs are not durable across restarts ([FastAPI caveat](https://fastapi.tiangolo.com/tutorial/background-tasks/#caveat)); mutable workbook files cannot be transactionally coordinated with the DB. Redis-backed queues or object storage add operational dependencies and are future scaling options.

## 5. Authentication, privacy and security

**Decision**: Same-origin deployment with organization OIDC identity and server-side session, secure HttpOnly cookies, CSRF protection, and deny-by-default tenant/record-level authorization for every read and mutation. Encrypt traffic and private data, use managed secrets, validate real file signatures and parser results, impose request/file/page/pixel/ZIP/time limits, and isolate decoders. Privacy and security approval of OpenRouter and all routed providers is a production gate; restrict routing to approved providers and disable unapproved fallbacks. Use synthetic data until approved.

**Rationale**: [OWASP authorization guidance](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html), [CSRF guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html), and [file-upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html) support defense in depth. [OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection) settings are not a substitute for contractual approval and may have zero-retention exceptions. Sensitive content stays out of operational logs and queue payloads.

**Alternatives**: Client-held API keys or trusting UI gating are rejected; CORS alone is not CSRF protection. Actual identity provider, role matrix, retention, limits and residency require organizational approval before production, not architectural guesses.

## 6. Frontend and verification

**Decision**: React/TypeScript with Vite, an OpenAPI-generated typed client, accessible structured review controls and chat, separate state for review and processing, and polling of durable job status. Use pytest/HTTPX for API and logic tests, and Playwright for end-to-end and accessibility flows. Adopt the installed FastAPI and React skills; pin compatible versions at implementation time.

**Rationale**: Explicit forms and previews keep the confirmed row reviewable; polling is adequate without streaming complexity. Use keyboard accessibility, labels, focus management and non-color status indicators, targeting [WCAG 2.2 AA](https://www.w3.org/WAI/WCAG22/quickref/). Baseline performance and field accuracy using a labeled corpus before agreeing to production thresholds.

**Alternatives**: SSE could improve long-running status updates but adds connection complexity; evaluate if polling is insufficient. Conversation-only confirmation is rejected as ambiguous and unsafe.

## External release decisions

Provider/model entitlement, provider privacy approval and retention, organization identity/roles and residency, file/page/batch limits, workbook feature profile, currency/tolerance policies, and AP quality/performance thresholds are release gates. These are stakeholder approvals, not unresolved design choices; production use remains blocked until documented.
