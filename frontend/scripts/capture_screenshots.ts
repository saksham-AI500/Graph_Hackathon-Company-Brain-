import { chromium } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SCREENSHOTS_DIR = path.resolve(process.cwd(), '../docs/screenshots');

async function main() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) {
    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
  }

  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });
  const page = await context.newPage();

  const pages = [
    { name: 'ask', path: '/ask' },
    { name: 'compare', path: '/compare' },
    { name: 'graph', path: '/graph' },
    { name: 'evaluation', path: '/evaluation' },
  ];

  for (const p of pages) {
    // 1. Dark Theme
    await page.addInitScript(() => {
      localStorage.setItem('repobrain-theme', 'dark');
      localStorage.setItem('repobrain-reduced-motion', 'true');
    });
    await page.goto(`http://localhost:5173${p.path}`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const darkPath = path.join(SCREENSHOTS_DIR, `${p.name}-dark.png`);
    await page.screenshot({ path: darkPath, fullPage: true });
    console.log(`Saved ${darkPath}`);

    // 2. Light Theme
    await page.evaluate(() => {
      localStorage.setItem('repobrain-theme', 'light');
      document.documentElement.classList.remove('dark');
    });
    await page.reload({ waitUntil: 'networkidle' });
    await page.waitForTimeout(1000);
    const lightPath = path.join(SCREENSHOTS_DIR, `${p.name}-light.png`);
    await page.screenshot({ path: lightPath, fullPage: true });
    console.log(`Saved ${lightPath}`);
  }

  await browser.close();
  console.log('All screenshots captured successfully!');
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
