import { expect, test } from "@playwright/test";

test("workbook logging requires reviewed preview and explicit confirmation", async ({ page }) => {
  await page.route("**/api/v1/session", async (route) => route.fulfill({ json: { user_id: "test-operator", tenant_id: "tenant-1", roles: ["operator"] } }));
  await page.route("**/api/v1/invoices/*/validate", async (route) => route.fulfill({ json: { run_id: "run-1", revision: 1, results: [{ check_type: "arithmetic", outcome: "passed", reason: "Decimal total matches." }, { check_type: "missing_po", outcome: "flagged", reason: "No PO number found." }, { check_type: "duplicate", outcome: "passed", reason: "No matching record found." }] } }));
  await page.route("**/api/v1/workbooks/new", async (route) => route.fulfill({ json: { workbook_id: "book-1", version_id: "version-1", sheets: [{ name: "Invoice Log", headers: ["Vendor", "Invoice No", "Invoice Date", "PO Number", "Total"] }] } }));
  await page.route("**/api/v1/workbooks/book-1/mappings", async (route) => route.fulfill({ json: { mapping_id: "mapping-1", confirmed: true } }));
  await page.route("**/api/v1/invoices/invoice-1/log-preview", async (route) => route.fulfill({ json: { preview_id: "preview-1", preview_digest: "digest-1", proposed_row: JSON.stringify({ vendor_name: "Acme", invoice_number: "00042", invoice_date: null, due_date: null, po_number: null, currency: "USD", subtotal: "10.00", tax: "0.00", other_charges: "0.00", discounts: "0.00", total: "10.00" }), flags_digest: "flags-1", workbook_version_id: "version-1" } }));
  let confirmations = 0;
  await page.route("**/api/v1/invoices/invoice-1/log-confirmations", async (route) => {
    confirmations += 1;
    await route.fulfill({ json: { operation_id: "operation-1", state: "committed", workbook_version_id: "version-2" } });
  });
  await page.route("**/api/v1/invoices", async (route) => route.fulfill({ json: { invoice_id: "invoice-1", job_id: "job-1", status: "received" }, status: 202 }));
  await page.route("**/api/v1/invoices/invoice-1", async (route) => route.fulfill({ json: { id: "invoice-1", processing_status: "ready_for_review", review_status: "needs_review", revision: 1, fields: { vendor_name: "Acme", invoice_number: "00042", invoice_date: null, due_date: null, po_number: null, currency: "USD", subtotal: "10.00", tax: "0.00", other_charges: "0.00", discounts: "0.00", total: "10.00" }, evidence: [] } }));

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Upload invoice" })).toBeVisible();
  await page.getByLabel("Upload invoice").setInputFiles({ name: "invoice.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4 fixture") });
  await expect(page.getByRole("heading", { name: "Extracted details" })).toBeVisible();
  await page.getByRole("button", { name: "Run checks" }).click();
  await expect(page.getByText("No PO number found.")).toBeVisible();
  await page.getByRole("button", { name: "Choose destination" }).click();
  await page.getByLabel("Log name").fill("AP 2026");
  await page.getByRole("button", { name: "Create workbook and preview layout" }).click();
  await page.getByRole("button", { name: "Confirm mapping" }).click();
  await expect(page.getByRole("heading", { name: "Review proposed log entry" })).toBeVisible();
  await expect(page.getByText("No PO number found.")).toBeVisible();
  expect(confirmations).toBe(0);
  await page.getByRole("button", { name: "Confirm logging for this invoice" }).click();
  await expect(page.getByText(/Log operation status: committed/)).toBeVisible();
  expect(confirmations).toBe(1);
});
