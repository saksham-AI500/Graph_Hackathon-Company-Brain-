import { test } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SCREENSHOTS_DIR = path.resolve(process.cwd(), '../docs/screenshots');

test.describe('Capture Screenshots', () => {
  test('Capture dark and light screenshots for all pages', async ({ page }) => {
    if (!fs.existsSync(SCREENSHOTS_DIR)) {
      fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
    }

    await page.setViewportSize({ width: 1440, height: 900 });

    const pages = [
      { name: 'ask', url: '/ask' },
      { name: 'compare', url: '/compare' },
      { name: 'graph', url: '/graph' },
      { name: 'evaluation', url: '/evaluation' },
    ];

    for (const p of pages) {
      // 1. Dark theme screenshot
      await page.addInitScript(() => {
        localStorage.setItem('repobrain-theme', 'dark');
        localStorage.setItem('repobrain-reduced-motion', 'true');
      });
      await page.goto(p.url, { waitUntil: 'networkidle' });
      await page.waitForTimeout(1200);

      const darkPath = path.join(SCREENSHOTS_DIR, `${p.name}-dark.png`);
      await page.screenshot({ path: darkPath, fullPage: true });
      console.log(`Saved screenshot: ${darkPath}`);

      // 2. Light theme screenshot
      await page.evaluate(() => {
        localStorage.setItem('repobrain-theme', 'light');
        document.documentElement.classList.remove('dark');
      });
      await page.reload({ waitUntil: 'networkidle' });
      await page.waitForTimeout(1200);

      const lightPath = path.join(SCREENSHOTS_DIR, `${p.name}-light.png`);
      await page.screenshot({ path: lightPath, fullPage: true });
      console.log(`Saved screenshot: ${lightPath}`);
    }
  });
});
