import { test } from '@playwright/test';
import path from 'path';

test('capture demo screenshots for Ask, Compare, and Graph', async ({ page }) => {
  const screenshotsDir = path.resolve('../docs/screenshots');

  // 1. Ask Page
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/ask');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(screenshotsDir, 'ask-dark.png') });

  // 2. Compare Page
  await page.goto('/compare');
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(screenshotsDir, 'compare-dark.png') });

  // 3. Graph Page
  await page.goto('/graph');
  await page.waitForSelector('.interactive-node', { timeout: 15000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(screenshotsDir, 'graph-dark.png') });
});
