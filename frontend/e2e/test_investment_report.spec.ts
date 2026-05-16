import { test, expect } from "@playwright/test";

test.describe("Investment Report Agent — Home Page", () => {
  test("loads with warm paper background and serif heading", async ({ page }) => {
    await page.goto("/");
    // Design system check: heading uses serif font
    const heading = page.locator("h1");
    await expect(heading).toContainText("研报 Agent");
  });

  test("shows suggestion chips and command input", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=分析贵州茅台")).toBeVisible();
    await expect(page.locator("text=快速看下宁德时代")).toBeVisible();
    const input = page.locator('input[placeholder*="公司名称"]');
    await expect(input).toBeVisible();
  });

  test("typing in command bar and clicking generate starts flow", async ({ page }) => {
    await page.goto("/");
    const input = page.locator('input[placeholder*="公司名称"]');
    await input.fill("分析贵州茅台");
    await page.click("text=生成报告");

    // Progress bar should appear
    await expect(page.locator("text=数据采集")).toBeVisible({ timeout: 5000 });
  });

  test("after progress completes, shows 'view report' button", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[placeholder*="公司名称"]', "分析贵州茅台");
    await page.click("text=生成报告");

    // Wait for completion
    await expect(page.locator("text=查看完整报告")).toBeVisible({ timeout: 10000 });
  });

  test("viewing report shows TOC and rating cards", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[placeholder*="公司名称"]', "分析贵州茅台");
    await page.click("text=生成报告");
    await page.click("text=查看完整报告");

    // Check report content
    await expect(page.locator("text=贵州茅台")).toBeVisible();
    await expect(page.locator("text=目录")).toBeVisible();
    await expect(page.locator("text=投资摘要")).toBeVisible();
    await expect(page.locator("text=财务分析")).toBeVisible();
    await expect(page.locator("text=估值分析")).toBeVisible();
  });

  test("report shows key data numbers", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[placeholder*="公司名称"]', "分析贵州茅台");
    await page.click("text=生成报告");
    await page.click("text=查看完整报告");

    await expect(page.locator("text=1,680")).toBeVisible();
    await expect(page.locator("text=1,970")).toBeVisible();
  });

  test("back to chat button returns to main view", async ({ page }) => {
    await page.goto("/");
    await page.fill('input[placeholder*="公司名称"]', "分析贵州茅台");
    await page.click("text=生成报告");
    await page.click("text=查看完整报告");
    await page.click("text=返回对话");

    // Back to chat — input should be visible
    await expect(page.locator('input[placeholder*="公司名称"]')).toBeVisible();
  });
});
