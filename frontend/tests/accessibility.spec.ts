import { expect, test } from "@playwright/test";

test("invoice review controls are keyboard reachable and labeled", async ({ page }) => {
  await page.route("**/api/v1/session", (route) => route.fulfill({ status: 401, json: { message: "Authentication required." } }));
  await page.route("**/api/v1/auth/status", (route) => route.fulfill({ json: { configured: false } }));
  await page.goto("/");
  await expect(page.getByText(/Uploads are unavailable until organization sign-in is configured/)).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Main navigation" })).toBeVisible();
  await expect(page.getByRole("textbox", { name: "Invoice number" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Choose destination" })).toBeVisible();
  await page.keyboard.press("Tab");
  await expect(page.locator(":focus")).toBeVisible();
  await expect(page.getByText("Logging records invoice data only. It does not approve the invoice or authorize payment.")).toBeVisible();
});
