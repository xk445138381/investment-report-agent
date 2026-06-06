import { expect, test } from "@playwright/test";

test.describe("Trustworthy report MVP smoke checks", () => {
  test("home page exposes the core analysis entry", async ({ page }) => {
    await page.goto("/");

    await expect(page.getByText("新建分析").first()).toBeVisible();
    await expect(page.getByRole("button", { name: /开始分析|生成报告/ })).toBeVisible();
  });

  test("demo report is explicitly labeled", async ({ page }) => {
    await page.goto("/report");

    await expect(page.getByText("Demo 数据").first()).toBeVisible();
    await expect(page.getByText("贵州茅台").first()).toBeVisible();
  });

  test("invalid real task shows an error instead of demo fallback", async ({ page }) => {
    await page.goto("/report?task=not-a-real-task-id");

    await expect(page.getByText("真实报告读取失败")).toBeVisible();
    await expect(page.getByText("不会用 Demo 报告替代真实结果")).toBeVisible();
  });

  test("progress failure stays on a real-report error state", async ({ page }) => {
    await page.goto("/progress?ticker=bad-input-for-test-no-demo&depth=scan&template=quick_scan_default");

    await expect(page.getByText("真实报告未生成")).toBeVisible({ timeout: 15000 });
    await expect(page).not.toHaveURL(/\/report/);
  });

  test("implemented secondary pages render", async ({ page }) => {
    const checks = [
      ["/reports", "报告列表"],
      ["/portfolio", "模拟组合"],
      ["/archive", "投研档案"],
      ["/settings", "模型与配置"],
    ] as const;

    for (const [path, label] of checks) {
      await page.goto(path);
      await expect(page.getByText(label).first()).toBeVisible();
    }
  });
});
