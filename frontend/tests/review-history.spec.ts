import { expect, test } from "@playwright/test";

test("review note and audit history retain data-review-only semantics", async ({ page }) => {
  await page.route("**/api/v1/session", async (route) => route.fulfill({ json: { user_id: "reviewer-1", tenant_id: "tenant-1", roles: ["reviewer"] } }));
  await page.route("**/api/v1/invoices", async (route) => route.fulfill({ status: 202, json: { invoice_id: "invoice-1", job_id: "job-1", status: "received" } }));
  await page.route("**/api/v1/invoices/invoice-1", async (route) => route.fulfill({ json: { id: "invoice-1", processing_status: "ready_for_review", review_status: "needs_review", revision: 1, fields: {}, evidence: [] } }));
  await page.route("**/api/v1/invoices/invoice-1/audit", async (route) => route.fulfill({ json: { items: [{ id: "event-1", timestamp: "2026-11-19T10:00:00Z", actor_id: "reviewer-1", actor_type: "user", action: "invoice.review_recorded", outcome: "success" }], next_cursor: null } }));
  await page.route("**/api/v1/invoices/invoice-1/review", async (route) => route.fulfill({ json: { status: "reviewed", meaning: "data_review_only_not_payment_approval" } }));

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Upload invoice" })).toBeVisible();
  await page.getByLabel("Upload invoice").setInputFiles({ name: "invoice.pdf", mimeType: "application/pdf", buffer: Buffer.from("%PDF-fixture") });
  await page.getByRole("button", { name: "Review history" }).click();
  await expect(page.getByRole("heading", { name: "Record data review" })).toBeVisible();
  await expect(page.getByText("This does not authorize payment.")).toBeVisible();
  await page.getByRole("button", { name: "Save review note" }).click();
  await expect(page.locator(".history-list").getByText("reviewer-1", { exact: false })).toBeVisible();
  await expect(page.getByText("invoice review_recorded", { exact: false })).toBeVisible();
  await expect(page.getByText("Review and logging history records data handling only—not invoice or payment approval.")).toBeVisible();
});
