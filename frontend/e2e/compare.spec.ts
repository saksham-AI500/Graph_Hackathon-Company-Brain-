import { test, expect } from '@playwright/test';
import path from 'node:path';

const SCREENSHOT_PATH = path.resolve(process.cwd(), '../docs/screenshots/compare-screen-3-app.png');

test.describe('Compare Page Playwright Verification', () => {
  test('run a comparison with the backend running; both columns show content; aggregate strip shows saved values; capture screenshot', async ({ page }) => {
    // 1440x900 desktop viewport
    await page.setViewportSize({ width: 1440, height: 900 });

    // Open Compare page
    await page.goto('/compare', { waitUntil: 'domcontentloaded' });

    // Verify Header and Active Compare Tab
    const header = page.locator('header');
    await expect(header).toBeVisible();
    await expect(header.getByText('RepoBrain')).toBeVisible();

    const compareTab = header.getByRole('link', { name: 'Compare' });
    await expect(compareTab).toBeVisible();
    await expect(compareTab).toHaveClass(/text-primary/);

    // Verify Query Input is prefilled with exact question
    const queryInput = page.locator('#query-input');
    await expect(queryInput).toBeVisible();
    await expect(queryInput).toHaveValue('Who should review changes to auth and payments?');

    // Click Run button
    const runBtn = page.locator('#run-compare-btn');
    await expect(runBtn).toBeVisible();
    await runBtn.click();

    // Wait for comparison response
    // Both columns must appear and show content
    await expect(page.getByText('Graph Off', { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Graph On', { exact: true })).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('Model only, no tools')).toBeVisible();
    await expect(page.getByText('Graph tools and verifier')).toBeVisible();

    // Verify single-question difference strip shows Question Status and not available text
    await expect(page.getByText('Question Status')).toBeVisible();
    await expect(page.getByText('Not available for a single question')).toBeVisible();

    // Verify aggregate strip shows saved values or 'Not available'
    await expect(page.getByText('Benchmark Differential')).toBeVisible();
    await expect(page.getByText('Saved dev run, not validation')).toBeVisible();
    await expect(page.getByText('Correct only with Graph On')).toBeVisible();
    await expect(page.getByText('Correct only with Graph Off')).toBeVisible();
    await expect(page.getByText('Both correct')).toBeVisible();
    await expect(page.getByText('Both wrong')).toBeVisible();

    // Click on a source button [S1] if present to test drawer
    const s1Btn = page.locator('button:has-text("[S1]")').first();
    if (await s1Btn.isVisible()) {
      await s1Btn.click();
      const drawer = page.locator('#source-drawer');
      await expect(drawer).toBeVisible();
      await expect(drawer.getByText('[S1]')).toBeVisible();

      // Press Escape and see it close
      await page.keyboard.press('Escape');
      await expect(drawer).not.toBeVisible();
    }

    // Wait for any animations to settle
    await page.waitForTimeout(600);

    // Capture screenshot at 1440x900 and save as docs/screenshots/compare-screen-3-app.png
    await page.screenshot({ path: SCREENSHOT_PATH, fullPage: false });
    console.log(`Saved screenshot to ${SCREENSHOT_PATH}`);
  });
});
