/**
 * tests/e2e/landing.spec.ts
 *
 * Playwright E2E tests for the landing page.
 * Covers: page loads, no horizontal overflow, key UI elements present.
 * Mobile viewport included to enforce 320px quality gate.
 */

import { test, expect } from "@playwright/test";

test.describe("Landing page", () => {
  test("loads without console errors", async ({ page }) => {
    const errors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    expect(errors).toHaveLength(0);
  });

  test("has correct title", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/en$/);
    await expect(page).toHaveTitle(/Tarot/);
  });

  test("hero section renders with main heading", async ({ page }) => {
    await page.goto("/");
    const heading = page.locator("h1");
    await expect(heading).toBeVisible();
    await expect(heading).toContainText("Tarot");
  });

  test("Enter the Reading link is present", async ({ page }) => {
    await page.goto("/");
    const link = page.getByRole("link", { name: /Enter the Reading/i });
    await expect(link).toBeVisible();
  });

  test("ritual explanation steps are visible", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByText("How the Ritual Works")).toBeVisible();
    // Use listitem context to avoid ambiguity with hero copy that also mentions "The gate opens"
    const steps = page.getByRole("listitem");
    await expect(steps.getByText("The gate opens")).toBeVisible();
    await expect(steps.getByText("Draw three cards")).toBeVisible();
    await expect(steps.getByText("Receive your reading")).toBeVisible();
  });

  test("no horizontal overflow at 320px", async ({ page }) => {
    await page.setViewportSize({ width: 320, height: 568 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const windowWidth = await page.evaluate(() => window.innerWidth);
    expect(bodyWidth).toBeLessThanOrEqual(windowWidth);
  });

  test("no horizontal overflow at 375px (iPhone 12)", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.goto("/");
    await page.waitForLoadState("networkidle");
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    const windowWidth = await page.evaluate(() => window.innerWidth);
    expect(bodyWidth).toBeLessThanOrEqual(windowWidth);
  });

  test("touch target size on CTA button", async ({ page }) => {
    await page.goto("/");
    const btn = page.getByRole("link", { name: /Enter the Reading/i });
    const box = await btn.boundingBox();
    expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
  });

  test("renders spanish route with localized copy", async ({ page }) => {
    await page.goto("/es");
    await expect(page.getByRole("link", { name: /Entrar a la lectura/i })).toBeVisible();
    await expect(page.getByText("Cómo funciona el ritual")).toBeVisible();
  });
});
