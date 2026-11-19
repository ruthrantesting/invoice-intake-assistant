import { useEffect, useState } from "react";
import { ValidationSummary } from "./ValidationSummary";
import { InvoiceChat } from "../chat/InvoiceChat";
import { apiRequest } from "../../api/client";
import { WorkbookSetup } from "../workbooks/WorkbookSetup";
import { LogConfirmation } from "../workbooks/LogConfirmation";
import { InvoiceHistory, type AuditItem } from "../audit/InvoiceHistory";
import { ReviewPanel } from "../audit/ReviewPanel";

declare const __PROTOTYPE_MODE__: boolean;

type InvoiceData = {
  id: string;
  processing_status: string;
  review_status: string;
  revision: number;
  fields: Record<string, string | null>;
  evidence: Array<{ field: string; raw_value: string | null; normalized_value: string | null; corrected_value: string | null; page_number: number | null; snippet: string | null; confidence: number | null }>;
};

const fieldLabels: Record<string, string> = { vendor_name: "Vendor", invoice_number: "Invoice number", invoice_date: "Invoice date", due_date: "Due date", po_number: "PO number", currency: "Currency", subtotal: "Subtotal", tax: "Tax", other_charges: "Other charges", discounts: "Discounts", total: "Total" };

export function InvoiceReviewPage() {
  const [activeTab, setActiveTab] = useState("Review invoice");
  const [notice, setNotice] = useState("");
  const [filename, setFilename] = useState("");
  const [saved, setSaved] = useState(false);
  const [invoice, setInvoice] = useState<InvoiceData | null>(null);
  const [jobId, setJobId] = useState("");
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [validation, setValidation] = useState<Array<{ check_type: string; outcome: "passed" | "flagged" | "not_verifiable"; reason: string; comparison_scope?: string | null; matched_record_id?: string | null }>>([]);
  const [destination, setDestination] = useState<{ id: string; version: string; mappingId: string; name: string }>();
  const [preview, setPreview] = useState<{ preview_id: string; preview_digest: string; proposed_row: string; flags_digest: string; workbook_version_id: string }>();
  const [operation, setOperation] = useState("");
  const [loggedVersionId, setLoggedVersionId] = useState("");
  const [auditItems, setAuditItems] = useState<AuditItem[]>([]);
  const [sessionError, setSessionError] = useState("");
  const [authenticated, setAuthenticated] = useState(false);
  const [loginAvailable, setLoginAvailable] = useState(false);
  const [prototypeMode, setPrototypeMode] = useState(false);
  const [displayName, setDisplayName] = useState("Accountant");

  useEffect(() => {
    if (__PROTOTYPE_MODE__) {
      // Enable the local prototype controls immediately; the API client supplies
      // the prototype CSRF token while /session sets its cookie asynchronously.
      setAuthenticated(true);
      setPrototypeMode(true);
      setDisplayName("Jamie Davis");
    }
    void apiRequest<{ user_id: string; display_name?: string; prototype_mode?: boolean }>("/session")
      .then((session) => { setAuthenticated(true); setSessionError(""); setDisplayName(session.display_name ?? session.user_id); setPrototypeMode(Boolean(session.prototype_mode)); })
      .catch(() => {
        if (__PROTOTYPE_MODE__) return;
        setSessionError("Uploads are unavailable until organization sign-in is configured. Choose a local file only after signing in.");
        void apiRequest<{ configured: boolean }>("/auth/status")
          .then((status) => setLoginAvailable(status.configured))
          .catch(() => setLoginAvailable(false));
      });
  }, []);

  async function refreshInvoice(id: string) {
    const result = await apiRequest<InvoiceData>(`/invoices/${id}`);
    setInvoice(result);
    setDraft(Object.fromEntries(Object.entries(result.fields).map(([key, value]) => [key, value ?? ""])));
  }

  useEffect(() => {
    if (!jobId || !invoice) return;
    const currentInvoice = invoice;
    let active = true;
    const interval = window.setInterval(async () => {
      try {
        const job = await apiRequest<{ status: string; error_code?: string | null }>(`/jobs/${jobId}`);
        if (!active) return;
        if (job.status === "completed") {
          window.clearInterval(interval);
          const result = await apiRequest<InvoiceData>(`/invoices/${currentInvoice.id}`);
          setInvoice(result);
          setDraft(Object.fromEntries(Object.entries(result.fields).map(([key, value]) => [key, value ?? ""])));
        } else if (job.status === "failed") {
          window.clearInterval(interval);
          setNotice(`Processing failed (${job.error_code ?? "unknown error"}). You can retry after configuration is checked.`);
        }
      } catch { /* transient polling failure is retried on the next interval */ }
    }, 1500);
    return () => { active = false; window.clearInterval(interval); };
  }, [jobId, invoice]);

  async function uploadFile(file: File) {
    setFilename(file.name);
    setInvoice(null);
    setJobId("");
    setDraft({});
    setPreview(undefined);
    setDestination(undefined);
    setOperation("");
    setLoggedVersionId("");
    setValidation([]);
    setSaved(false);
    setBusy(true);
    setNotice("Uploading securely…");
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await apiRequest<{ invoice_id: string; job_id: string; status: string }>("/invoices", { method: "POST", body });
      await refreshInvoice(result.invoice_id);
      setJobId(result.job_id);
      setNotice("Upload received. Extracting document text and preparing evidence…");
      const capabilities = await apiRequest<{ ocr_available: boolean; model_configured: boolean; prototype_mode?: boolean }>("/settings/capabilities");
      if (!capabilities.ocr_available || (!capabilities.model_configured && !capabilities.prototype_mode)) {
        setNotice(`Upload stored. Processing is waiting for server configuration: ${!capabilities.ocr_available ? "no OCR engine is available; " : ""}${!capabilities.model_configured && !capabilities.prototype_mode ? "approved model credentials/provider routing are not configured." : ""}`);
      }
    } catch (reason) {
      setNotice(reason instanceof Error ? `Upload failed: ${reason.message}` : "Upload failed due to an unexpected error.");
    } finally {
      setBusy(false);
    }
  }

  async function retryProcessing() {
    if (!invoice) return;
    try {
      const result = await apiRequest<{ job_id: string }>(`/invoices/${invoice.id}/retry`, { method: "POST", body: JSON.stringify({}) });
      setJobId(result.job_id);
      await refreshInvoice(invoice.id);
      setNotice("Processing retry queued.");
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Retry could not be scheduled.");
    }
  }

  async function saveCorrections() {
    if (!invoice) return;
    setBusy(true);
    try {
      const changes = Object.fromEntries(Object.entries(draft).filter(([key, value]) => value !== (invoice.fields[key] ?? "")));
      if (Object.keys(changes).length === 0) { setSaved(true); return; }
      await apiRequest(`/invoices/${invoice.id}/fields`, { method: "PATCH", body: JSON.stringify({ expected_revision: invoice.revision, changes }) });
      await refreshInvoice(invoice.id);
      setSaved(true);
      setNotice("Corrections saved as a new revision; validation should be rerun.");
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not save corrections."); }
    finally { setBusy(false); }
  }

  async function runValidation(context?: { workbook_id: string; workbook_version_id: string; mapping_id: string }) {
    if (!invoice) return false;
    try {
      const result = await apiRequest<{ results: typeof validation }>(`/invoices/${invoice.id}/validate`, { method: "POST", body: JSON.stringify(context ?? {}) });
      setValidation(result.results);
      return true;
    } catch (reason) {
      setNotice(reason instanceof Error ? reason.message : "Validation could not run.");
      return false;
    }
  }

  async function prepareLogPreview(selected: { id: string; version: string; mappingId: string; name: string }) {
    if (!invoice) return;
    setDestination(selected);
    try {
      const validated = await runValidation({ workbook_id: selected.id, workbook_version_id: selected.version, mapping_id: selected.mappingId });
      if (!validated) return;
      const result = await apiRequest<typeof preview>(`/invoices/${invoice.id}/log-preview`, { method: "POST", body: JSON.stringify({ invoice_revision: invoice.revision, workbook_id: selected.id, workbook_version_id: selected.version, mapping_id: selected.mappingId }) });
      if (result) setPreview(result);
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not create a log preview."); }
  }

  async function confirmLogging() {
    if (!invoice || !preview) return;
    const idempotencyKey = crypto.randomUUID();
    try {
      const result = await apiRequest<{ operation_id: string; state: string; workbook_version_id: string }>(`/invoices/${invoice.id}/log-confirmations`, { method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify({ preview_id: preview.preview_id, preview_digest: preview.preview_digest }) });
      setOperation(result.operation_id);
      setLoggedVersionId(result.workbook_version_id ?? "");
      setNotice(`Log operation status: ${result.state}. Logging is not approval.`);
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Log confirmation failed."); }
  }

  async function openHistory() {
    setActiveTab("Review history");
    if (!invoice) return;
    try {
      const result = await apiRequest<{ items: AuditItem[] }>(`/invoices/${invoice.id}/audit`);
      setAuditItems(result.items);
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not load review history."); }
  }

  async function saveReview(status: string, note: string) {
    if (!invoice) return;
    try {
      await apiRequest(`/invoices/${invoice.id}/review`, { method: "POST", body: JSON.stringify({ status, note }) });
      await refreshInvoice(invoice.id);
      await openHistory();
      setNotice("Review note saved. This records data review only.");
    } catch (reason) { setNotice(reason instanceof Error ? reason.message : "Could not save review note."); }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand" href="#home" aria-label="Ledgerly home">
          <span className="brand-mark">L</span><span>ledgerly</span>
        </a>
        <div className="workspace-label">WORKSPACE</div>
        <button className="workspace-switch" type="button"><span className="workspace-avatar">A</span><span>Acme & Co.<small>Accounts Payable</small></span><span className="chevron">⌄</span></button>
        <nav className="primary-nav" aria-label="Main navigation">
          <button className="nav-item active" type="button" onClick={() => setActiveTab("Review invoice")}><span className="nav-icon">▤</span>Invoice intake</button>
          <button className="nav-item" type="button" onClick={() => setNotice("Your invoice log will appear here.")}><span className="nav-icon">▦</span>Invoice log</button>
          <button className="nav-item" type="button" onClick={() => void openHistory()}><span className="nav-icon">◷</span>Review history</button>
        </nav>
        <div className="sidebar-bottom">
          <div className="help-card"><span className="help-icon">?</span><div><strong>Need a hand?</strong><p>Visit our help center</p></div><span className="arrow">↗</span></div>
          <button className="profile-button" type="button"><span className="profile-avatar">{displayName.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase()}</span><span>{displayName}<small>{prototypeMode ? "Local prototype operator" : "AP Operator"}</small></span><span className="chevron">···</span></button>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar"><div className="breadcrumbs">Workspace <span>/</span> <strong>Invoice intake</strong></div><div className="top-actions"><button className="icon-button" type="button" aria-label="Notifications">♧<i /></button><button className="icon-button avatar-small" type="button" aria-label="User profile">JD</button></div></header>
        <section className="page-content">
          {prototypeMode && <div className="prototype-banner" role="status"><strong>Local prototype mode</strong><span>Not for production or sensitive invoices. Processing uses local OCR and text-pattern extraction with low confidence; AI is not used. Verify and correct every field before logging.</span></div>}
          <div className="page-heading"><div><div className="eyebrow"><span className="eyebrow-dot"/>INVOICE INTAKE</div><h1>Let’s review this invoice</h1><p>Upload an invoice to extract its details, review issues, and prepare a log entry.</p></div><button className="quiet-button" type="button" disabled={!invoice} onClick={() => setNotice("Invoice remains saved in the local database.")}>Save draft <span>↗</span></button></div>
          {(notice || sessionError) && <div className="notice" role="status">{notice || sessionError}<button type="button" aria-label="Dismiss" onClick={() => setNotice("")}>×</button></div>}
          <div className="workspace-grid">
            <section className="document-card card" aria-label="Invoice document">
              <div className="document-toolbar"><div className="document-title"><span className="pdf-icon">FILE</span><span>{filename || "No invoice selected"}<small>{invoice ? `Revision ${invoice.revision} · ${invoice.processing_status.replaceAll("_", " ")}` : "Select a file from your computer to begin"}</small></span></div>{invoice?.processing_status === "failed" ? <button className="text-button" type="button" onClick={() => void retryProcessing()}>Retry processing</button> : <button className="more-button" type="button" aria-label="Document options">•••</button>}</div>
              <div className="document-canvas">
                {invoice ? <div className="paper source-evidence"><h2>Extracted source evidence</h2>{invoice.evidence.length ? invoice.evidence.map((item) => <blockquote key={`${item.field}-${item.page_number}`}><strong>{fieldLabels[item.field] ?? item.field}</strong><p>{item.snippet ?? item.raw_value ?? "No text evidence available."}</p><small>{item.page_number ? `Page ${item.page_number}` : "Source page unavailable"}</small></blockquote>) : <p>Evidence is not available yet. Current processing status: {invoice.processing_status.replaceAll("_", " ")}.</p>}</div> : <div className="upload-empty"><span>⇧</span><h2>Upload an invoice to begin</h2><p>Choose a PDF, JPEG, PNG, or HEIC file from your computer. Missing or unreadable fields stay unknown.</p>{authenticated ? <label className="secondary-button">Choose a local file<input type="file" accept=".pdf,.jpg,.jpeg,.png,.heic" onChange={(event) => { const input = event.currentTarget; const file = input.files?.[0]; input.value = ""; if (file) void uploadFile(file); }} /></label> : <p className="upload-blocked">{loginAvailable ? <a href="/api/v1/auth/login">Sign in with your organization account to upload.</a> : "Organization sign-in is not configured on this server, so uploads are currently disabled."}</p>}</div>}
              </div>
              <div className="document-footer"><span>{invoice ? `Processing: ${invoice.processing_status.replaceAll("_", " ")}` : "Original source is stored privately after upload."}</span></div>
            </section>

            <section className="details-column">
              <div className="tabs" role="tablist" aria-label="Invoice details tabs">{["Review invoice", "Ask Ledgerly"].map((tab) => <button key={tab} role="tab" aria-selected={activeTab === tab} className={activeTab === tab ? "tab active-tab" : "tab"} type="button" onClick={() => setActiveTab(tab)}>{tab}{tab === "Ask Ledgerly" && <span className="ai-spark">✳</span>}</button>)}</div>
              {activeTab === "Review history" ? <div className="review-panel"><ReviewPanel onSave={(status, note) => void saveReview(status, note)} /><InvoiceHistory items={auditItems} /></div> : activeTab === "Review invoice" ? <div className="review-panel">
                <div className="card extracted-card"><div className="section-top"><div><h2>Extracted details</h2><p>{invoice ? `${Object.keys(invoice.fields).length} fields · unknown values remain blank` : "No invoice uploaded"}</p></div><button className="text-button" type="button" onClick={() => void saveCorrections()} disabled={!invoice || busy}>{saved ? "Saved ✓" : "Save corrections"}</button></div>
                  <div className="fields-grid">{Object.entries(fieldLabels).map(([key, label]) => <label className="field" key={key}><span>{label}</span><input aria-label={label} value={draft[key] ?? ""} placeholder="Unknown" disabled={!invoice || busy} onChange={(event) => { setDraft({ ...draft, [key]: event.target.value }); setSaved(false); }} /></label>)}</div>
                  <div className="confidence-note"><span className="confidence-check">i</span><span>{invoice ? "Confirm each value against the source evidence." : "Upload a supported invoice before reviewing extracted fields."}<small>Missing or unreadable details remain unknown.</small></span></div>
                </div>
                <div className="validation-controls"><button className="secondary-button" type="button" disabled={!invoice} onClick={() => void runValidation()}>Run checks</button><ValidationSummary items={validation} /></div>
                <div className="card destination-card"><div className="section-top"><div><h2>Logging destination</h2><p>Choose a workbook and confirm mapping</p></div><button className="text-button" type="button" disabled={!invoice || !validation.length} onClick={() => setActiveTab("Logging destination")}>Set up</button></div><div className="workbook-row"><span className="sheet-icon">▦</span><span><strong>{destination?.name ?? (invoice ? "No workbook selected" : "Upload an invoice first")}</strong><small>Workbooks are application-managed copies.</small></span></div></div>
                <div className="authority-note"><span className="shield">♢</span><span>Logging records invoice data only. It does not approve the invoice or authorize payment.</span></div>
                <div className="bottom-actions"><button className="secondary-button" type="button" onClick={() => setNotice("Invoice remains saved in its current state.")} disabled={!invoice}>Save for later</button><button className="primary-button" type="button" onClick={() => setActiveTab("Logging destination")} disabled={!invoice || !validation.length}>Choose destination <span>→</span></button></div>
              </div> : activeTab === "Logging destination" ? <div className="review-panel">{preview ? <LogConfirmation destination={`${destination?.name ?? "Managed workbook"} · version ${preview.workbook_version_id}`} row={JSON.parse(preview.proposed_row) as Record<string, string | null>} flags={validation.filter((item) => item.outcome !== "passed").map((item) => `${item.check_type}: ${item.reason}`)} onConfirm={() => void confirmLogging()} /> : <WorkbookSetup onReady={(selected) => { void prepareLogPreview(selected); }} />}{operation && <div role="status" className="notice">Operation {operation} recorded. <a href={`/api/v1/workbooks/${destination?.id}/versions/${loggedVersionId || preview?.workbook_version_id}/download`}>Download managed workbook</a></div>}</div> : <InvoiceChat invoiceId={invoice?.id} />}
            </section>
          </div>
          <footer className="page-footer"><span>🔒 Your invoice data is encrypted and access-controlled.</span><span>Need help? <a href="#support">Contact AP support</a></span></footer>
        </section>
      </main>
      {!authenticated && loginAvailable && <a className="upload-fab" href="/api/v1/auth/login"><span>↗</span> Sign in with organization</a>}
      {authenticated && <label className="upload-fab"><input type="file" accept=".pdf,.jpg,.jpeg,.png,.heic" disabled={busy} onChange={(event) => { const input = event.currentTarget; const file = input.files?.[0]; input.value = ""; if (file) void uploadFile(file); }} /><span>＋</span> {busy ? "Working…" : "Upload invoice"}</label>}
    </div>
  );
}
