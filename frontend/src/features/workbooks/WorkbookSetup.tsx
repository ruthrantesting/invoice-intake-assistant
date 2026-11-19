import { useState } from "react";
import { apiRequest } from "../../api/client";

type Sheet = { name: string; headers: (string | null)[] };
type WorkbookInfo = { workbook_id: string; version_id: string; sheets: Sheet[] };
type Props = { onReady: (workbook: { id: string; version: string; mappingId: string; name: string }) => void };

const fields: Record<string, string> = {
  vendor_name: "Vendor",
  invoice_number: "Invoice No",
  invoice_date: "Invoice Date",
  due_date: "Due Date",
  po_number: "PO Number",
  currency: "Currency",
  subtotal: "Subtotal",
  tax: "Tax",
  total: "Total",
};

export function WorkbookSetup({ onReady }: Props) {
  const [name, setName] = useState("FY 2026 Invoice Log");
  const [headersText, setHeadersText] = useState("Vendor,Invoice No,Invoice Date,PO Number,Total");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [workbook, setWorkbook] = useState<WorkbookInfo | null>(null);
  const [sheetName, setSheetName] = useState("");
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const headers = workbook?.sheets.find((sheet) => sheet.name === sheetName)?.headers ?? [];
  const availableHeaders = headers.filter((header): header is string => Boolean(header));

  async function inspectExisting() {
    if (!selectedFile) return;
    setBusy(true);
    setStatus("");
    try {
      const body = new FormData();
      body.append("file", selectedFile);
      const result = await apiRequest<WorkbookInfo>("/workbooks", { method: "POST", body });
      setWorkbook(result);
      const first = result.sheets[0];
      setSheetName(first?.name ?? "");
      setMapping(Object.fromEntries(Object.entries(fields).filter(([, label]) => first?.headers.includes(label)).map(([field, label]) => [field, label])));
      setStatus("Workbook inspected. Review the worksheet and mapping before confirming.");
    } catch (reason) {
      setStatus(reason instanceof Error ? reason.message : "Could not inspect workbook.");
    } finally {
      setBusy(false);
    }
  }

  async function createNew() {
    setBusy(true);
    setStatus("");
    try {
      const headersToCreate = headersText.split(",").map((value) => value.trim()).filter(Boolean);
      const result = await apiRequest<WorkbookInfo>("/workbooks/new", { method: "POST", body: JSON.stringify({ name, headers: headersToCreate }) });
      setWorkbook(result);
      setSheetName(result.sheets[0]?.name ?? "");
      setMapping(Object.fromEntries(Object.entries(fields).filter(([, label]) => headersToCreate.includes(label))));
      setStatus("New workbook created. Review its headers and mapping before continuing.");
    } catch (reason) {
      setStatus(reason instanceof Error ? reason.message : "Could not create workbook.");
    } finally {
      setBusy(false);
    }
  }

  async function confirmMapping() {
    if (!workbook || !sheetName || Object.keys(mapping).length === 0) return;
    setBusy(true);
    try {
      const result = await apiRequest<{ mapping_id: string }>(`/workbooks/${workbook.workbook_id}/mappings`, { method: "POST", body: JSON.stringify({ expected_version_id: workbook.version_id, sheet: sheetName, field_to_column: mapping }) });
      onReady({ id: workbook.workbook_id, version: workbook.version_id, mappingId: result.mapping_id, name });
    } catch (reason) {
      setStatus(reason instanceof Error ? reason.message : "Could not confirm column mapping.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="card workbook-setup"><div className="section-top"><div><h2>Choose a logging destination</h2><p>Upload an existing workbook or create a new log.</p></div></div><label className="field"><span>Existing .xlsx workbook</span><input aria-label="Existing .xlsx workbook" type="file" accept=".xlsx" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}/></label><button className="secondary-button" type="button" disabled={!selectedFile || busy} onClick={inspectExisting}>{busy ? "Working…" : "Upload & inspect workbook"}</button><div className="divider-label">OR CREATE A NEW LOG</div><label className="field"><span>Log name</span><input value={name} onChange={(event) => setName(event.target.value)}/></label><label className="field"><span>Column headers (comma separated)</span><textarea value={headersText} onChange={(event) => setHeadersText(event.target.value)}/></label><button className="secondary-button" type="button" disabled={busy} onClick={createNew}>Create workbook and preview layout</button>{workbook && <div className="mapping-grid"><strong>Confirm worksheet and field mapping</strong><label><span>Worksheet</span><select value={sheetName} onChange={(event) => setSheetName(event.target.value)}>{workbook.sheets.map((sheet) => <option key={sheet.name}>{sheet.name}</option>)}</select></label>{Object.entries(mapping).map(([field, value]) => <label key={field}><span>{field.replaceAll("_", " ")}</span><select value={value} onChange={(event) => setMapping({ ...mapping, [field]: event.target.value })}>{availableHeaders.map((header) => <option key={header}>{header}</option>)}</select></label>)}<button className="primary-button" type="button" disabled={busy || Object.keys(mapping).length === 0} onClick={confirmMapping}>Confirm mapping →</button></div>}{status && <p role="status" className="setup-status">{status}</p>}<p className="chat-disclaimer">The application manages an immutable workbook copy. Your local original is not changed.</p></section>;
}
