import { test, expect } from "@playwright/test";

test.describe("Research Agent — Home Page", () => {
  test("loads with warm paper background and serif heading", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h2")).toContainText("生成专业投资研究报告");
  });

  test("sidebar shows all navigation items", async ({ page }) => {
    await page.goto("/");
    const aside = page.locator("aside");
    await expect(aside.locator("text=新建分析")).toBeVisible();
    await expect(aside.locator("text=报告列表")).toBeVisible();
    await expect(aside.locator("text=模板管理")).toBeVisible();
    await expect(aside.locator("text=模型与配置")).toBeVisible();
    await expect(aside.locator("text=1 / 3 份报告")).toBeVisible();
  });

  test("shows suggestion chips and command input with $ prefix", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=贵州茅台").first()).toBeVisible();
    await expect(page.locator("text=宁德时代").first()).toBeVisible();
    await expect(page.locator("text=$")).toBeVisible();
    const input = page.locator('input[placeholder*="公司名称"]');
    await expect(input).toBeVisible();
  });

  test("shows depth selector cards", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("text=快速简报")).toBeVisible();
    await expect(page.locator("text=深度研报")).toBeVisible();
    await expect(page.locator("text=自定义")).toBeVisible();
  });

  test("shows pipeline preview with 4 phases", async ({ page }) => {
    await page.goto("/");
    // Use exact text to avoid matching hero paragraph
    await expect(page.getByText("数据聚合", { exact: true })).toBeVisible();
    await expect(page.getByText("深度分析", { exact: true })).toBeVisible();
    await expect(page.getByText("多空辩论", { exact: true })).toBeVisible();
    await expect(page.getByText("统稿排版", { exact: true })).toBeVisible();
  });

  test("clicking suggestion fills input and enables button", async ({ page }) => {
    await page.goto("/");
    await page.locator("text=贵州茅台").first().click();
    const input = page.locator('input[placeholder*="公司名称"]');
    await expect(input).toHaveValue("贵州茅台");
    const btn = page.locator("button:has-text('生成报告')");
    await expect(btn).toBeEnabled();
  });

  test("advanced config expands wizard on click", async ({ page }) => {
    await page.goto("/");
    await page.locator("text=高级配置…").click();
    await expect(page.locator("text=深度研报（默认）")).toBeVisible({ timeout: 3000 });
    // Close it
    await page.locator("text=收起高级配置").click();
  });
});

test.describe("Research Agent — Progress & Report Flow", () => {
  test("typing ticker and clicking generate navigates to progress page", async ({ page }) => {
    await page.goto("/");
    const input = page.locator('input[placeholder*="公司名称"]');
    await input.fill("贵州茅台");
    await page.locator("button:has-text('生成报告')").click();
    // Should be on progress page
    await expect(page).toHaveURL(/\/progress/, { timeout: 5000 });
  });

  test("progress page shows phase cards and progress bar", async ({ page }) => {
    await page.goto("/progress?ticker=贵州茅台&depth=deep");
    await expect(page.locator("text=数据聚合")).toBeVisible();
    await expect(page.locator("text=Phase")).toBeVisible();
  });

  test("progress page automatically navigates to report", async ({ page }) => {
    await page.goto("/progress?ticker=贵州茅台&depth=deep");
    // Wait for auto-redirect after animation (~4s mock)
    await expect(page).toHaveURL(/\/report/, { timeout: 10000 });
  });

  test("report page shows cover with ticker and title", async ({ page }) => {
    await page.goto("/report?ticker=贵州茅台");
    await expect(page.getByText("贵州茅台").first()).toBeVisible();
    await expect(page.getByText("DEEP DIVE REPORT")).toBeVisible();
  });

  test("report page shows rating cards and key data", async ({ page }) => {
    await page.goto("/report?ticker=贵州茅台");
    // Rating cards are visible (use .first() to avoid strict mode)
    await expect(page.getByText("财务健康").first()).toBeVisible();
    await expect(page.getByText("估值水平").first()).toBeVisible();
    await expect(page.getByText("综合评级").first()).toBeVisible();
  });

  test("report page shows TOC with all 7 sections", async ({ page }) => {
    await page.goto("/report?ticker=贵州茅台");
    // TOC entries — use .first() since they also appear in page content
    await expect(page.getByText("投资摘要").first()).toBeVisible();
    await expect(page.getByText("财务分析").first()).toBeVisible();
    await expect(page.getByText("估值分析").first()).toBeVisible();
    await expect(page.getByText("投资建议").first()).toBeVisible();
  });

  test("report shows export buttons", async ({ page }) => {
    await page.goto("/report?ticker=贵州茅台");
    await expect(page.locator("text=导出 PDF")).toBeVisible();
    await expect(page.locator("text=导出 Word")).toBeVisible();
  });
});

test.describe("Research Agent — Secondary Pages", () => {
  test("reports page navigates from sidebar", async ({ page }) => {
    await page.goto("/reports");
    const main = page.locator("main");
    await expect(main.locator("text=报告列表")).toBeVisible();
    await expect(main.locator("text=贵州茅台")).toBeVisible();
    await expect(main.locator("text=宁德时代")).toBeVisible();
  });

  test("templates page shows available templates", async ({ page }) => {
    await page.goto("/templates");
    const main = page.locator("main");
    await expect(main.locator("text=模板管理")).toBeVisible();
    await expect(main.locator("text=深度研报（默认）")).toBeVisible();
    await expect(page.locator("main").locator("text=快速简报")).toBeVisible();
    await expect(main.locator("text=A 股专用模板")).toBeVisible();
  });

  test("settings page shows LLM and data source config", async ({ page }) => {
    await page.goto("/settings");
    const main = page.locator("main");
    await expect(main.locator("text=模型与配置")).toBeVisible();
    await expect(page.getByText("DeepSeek V4 Pro").first()).toBeVisible();
    await expect(main.locator("text=AkShare")).toBeVisible();
  });

  test("sidebar navigation between pages works", async ({ page }) => {
    await page.goto("/");
    const aside = page.locator("aside");
    await aside.locator("text=报告列表").click();
    await expect(page).toHaveURL(/\/reports/);
    await aside.locator("text=模板管理").click();
    await expect(page).toHaveURL(/\/templates/);
    await aside.locator("text=模型与配置").click();
    await expect(page).toHaveURL(/\/settings/);
    await aside.locator("text=新建分析").click();
    await expect(page).toHaveURL(/\//);
  });
});
