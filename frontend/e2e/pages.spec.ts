import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

const SAMPLES_DIR = path.resolve(process.cwd(), '../docs/api_samples');

function loadSample(fileName: string) {
  return JSON.parse(fs.readFileSync(path.join(SAMPLES_DIR, fileName), 'utf-8'));
}

test.describe('RepoBrain E2E Suite', () => {
  test.beforeEach(async ({ page }) => {
    // Mock health, stats, and eval results for deterministic e2e runs
    await page.route('**/api/health', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadSample('get_api_health.json')),
      });
    });

    await page.route('**/api/stats', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadSample('get_api_stats.json')),
      });
    });

    await page.route('**/api/eval/results', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadSample('get_api_eval_results.json')),
      });
    });

    await page.route('**/api/graph/neighborhood*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadSample('get_api_graph_neighborhood.json')),
      });
    });
  });

  test('/ask submits a question and shows an answer', async ({ page }) => {
    await page.route('**/api/ask', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadSample('post_api_ask_graph_on.json')),
      });
    });

    await page.goto('/ask');

    // Check header branding without ambiguity
    await expect(page.locator('header').getByText('RepoBrain')).toBeVisible();

    // Verify input is visible and filled
    const input = page.locator('#ask-input');
    await expect(input).toBeVisible();

    // Click Ask button
    const submitBtn = page.locator('#ask-submit-btn');
    await expect(submitBtn).toBeVisible();
    await submitBtn.click();

    // Verify answer card with VERIFIED badge
    await expect(page.getByText('VERIFIED')).toBeVisible();

    // Verify claims audit details button
    await expect(page.locator('#toggle-details-btn')).toBeVisible();
  });

  test('/compare shows two columns', async ({ page }) => {
    await page.route('**/api/compare', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(loadSample('post_api_compare.json')),
      });
    });

    await page.goto('/compare');

    const runBtn = page.locator('#run-compare-btn');
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    // Verify two columns appear: Graph Off left, Graph On right
    await expect(page.getByText('Graph Off', { exact: true })).toBeVisible();
    await expect(page.getByText('Graph On', { exact: true })).toBeVisible();

    // Verify difference sections appear
    await expect(page.getByText('Question Status')).toBeVisible();
    await expect(page.getByText('Benchmark Differential')).toBeVisible();
  });

  test('/graph renders canvas and controls', async ({ page }) => {
    await page.goto('/graph');

    // Controls
    await expect(page.locator('#graph-search-input')).toBeVisible();
    await expect(page.locator('#graph-search-btn')).toBeVisible();

    // Canvas SVG
    await expect(page.locator('#neighborhood-canvas-svg')).toBeVisible();
  });

  test('/evaluation renders benchmark stats, table, and disclaimer', async ({ page }) => {
    await page.goto('/evaluation');

    // Check exact required disclaimer
    await expect(
      page.getByText('Dev set used during debugging. Not validation.'),
    ).toBeVisible();

    // Four stat cards
    await expect(page.getByText('Graph On Accuracy')).toBeVisible();
    await expect(page.getByText('Citation Support')).toBeVisible();
    await expect(page.getByText('Unsupported Claims')).toBeVisible();
    await expect(page.getByText('Mean Turn Latency')).toBeVisible();

    // Table
    await expect(page.getByText(/Evaluation Question Breakdown/i)).toBeVisible();
  });
});
