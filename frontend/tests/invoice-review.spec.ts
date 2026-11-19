import { expect, test } from "@playwright/test";

test("invoice review exposes an empty state until a real invoice is uploaded", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Upload an invoice to begin" })).toBeVisible();
  await expect(page.getByText("No invoice selected")).toBeVisible();
  const invoiceNumber = page.getByRole("textbox", { name: "Invoice number" });
  await expect(invoiceNumber).toHaveValue("");
  await expect(invoiceNumber).toBeDisabled();
  await expect(page.getByRole("heading", { name: "Extracted details" })).toBeVisible();
  await expect(page.getByText("Logging records invoice data only. It does not approve the invoice or authorize payment.")).toBeVisible();
});
