import { test } from '@playwright/test';
import path from 'path';

test('capture before screenshots from public url', async ({ page }) => {
  const targetBase = 'https://bidder-architectural-stopping-thats.trycloudflare.com';
  const beforeDir = path.resolve('../docs/screenshots/before');

  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  await page.setViewportSize({ width: 1440, height: 900 });

  // 1. /ask
  console.log('Navigating to /ask...');
  await page.goto(`${targetBase}/ask`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(beforeDir, 'ask.png') });

  // 2. /compare
  console.log('Navigating to /compare...');
  await page.goto(`${targetBase}/compare`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(beforeDir, 'compare.png') });

  // 3. /graph
  console.log('Navigating to /graph...');
  await page.goto(`${targetBase}/graph`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(beforeDir, 'graph.png') });

  // 4. /evaluation
  console.log('Navigating to /evaluation...');
  await page.goto(`${targetBase}/evaluation`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(beforeDir, 'evaluation.png') });
});
