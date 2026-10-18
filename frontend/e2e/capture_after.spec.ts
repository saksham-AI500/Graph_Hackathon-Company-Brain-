import { test } from '@playwright/test';
import path from 'path';
import fs from 'fs';

test('capture after screenshots from public url', async ({ page }) => {
  const targetBase = 'https://bidder-architectural-stopping-thats.trycloudflare.com';
  const afterDir = path.resolve('../docs/screenshots/after');
  if (!fs.existsSync(afterDir)) {
    fs.mkdirSync(afterDir, { recursive: true });
  }

  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', err => console.log('PAGE ERROR:', err.message));

  await page.setViewportSize({ width: 1440, height: 900 });

  // 1. /ask (empty)
  console.log('Capturing /ask (empty)...');
  await page.goto(`${targetBase}/ask`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(afterDir, 'ask_empty.png') });

  // 2. /ask (answered)
  console.log('Capturing /ask (answered)...');
  // Click the submit button or prompt card
  const submitBtn = page.locator('#ask-submit-btn');
  await submitBtn.click();
  // Wait for the response (answer card or refusal card)
  await page.waitForSelector('.answer-fade-in', { timeout: 45000 });
  await page.waitForTimeout(1500);
  await page.screenshot({ path: path.join(afterDir, 'ask_answered.png') });

  // 3. /compare
  console.log('Capturing /compare...');
  await page.goto(`${targetBase}/compare`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(afterDir, 'compare.png') });

  // 4. /graph (node selected)
  console.log('Capturing /graph (node selected)...');
  await page.goto(`${targetBase}/graph`, { waitUntil: 'networkidle', timeout: 30000 });
  // Wait for svg nodes to appear
  await page.waitForSelector('.interactive-node', { timeout: 30000 });
  await page.waitForTimeout(2000);
  // Click on the first node
  const firstNode = page.locator('.interactive-node').first();
  await firstNode.click();
  await page.waitForSelector('#node-inspector-card', { timeout: 5000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(afterDir, 'graph_node_selected.png') });

  // 5. /evaluation
  console.log('Capturing /evaluation...');
  await page.goto(`${targetBase}/evaluation`, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(afterDir, 'evaluation.png') });
});
