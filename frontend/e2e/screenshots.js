/* eslint-disable @typescript-eslint/no-require-imports */
const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  // 1. Homepage
  console.log('Taking homepage screenshot...');
  await page.goto('http://localhost:3000', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'shot_homepage.png', fullPage: true });
  console.log('Homepage done');

  // 2. Progress page for value template
  console.log('Taking progress screenshot...');
  await page.goto('http://localhost:3000/progress?ticker=600519.SH&depth=value&template=value_investor', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'shot_progress.png', fullPage: true });
  console.log('Progress done');

  // 3. Report page with completed report
  console.log('Taking report screenshot...');
  await page.goto('http://localhost:3000/report?ticker=600519.SH&task=ccd23d1a-b57c-4774-af35-cc673c00f8e2', { waitUntil: 'networkidle' });
  await page.screenshot({ path: 'shot_report.png', fullPage: true });
  console.log('Report done');

  await browser.close();
  console.log('All done!');
})();
