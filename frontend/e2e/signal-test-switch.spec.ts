import { expect, test } from '@playwright/test';

test('switches tests inside the chart, ignores stale loads and allows recovery', async ({ page }) => {
  let finishBeta: (() => Promise<void>) | undefined;
  let failBroken = true;
  const sampleRequests: string[] = [];
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (path.endsWith('/auth/me/')) return respond({ id: 1, username: 'tester', is_superuser: true, permissions: [] });
    if (path.endsWith('/measurement-batches/batch/')) return respond({ id: 'batch', devices: [{
      id: 'serial', serial_number: 'SN-001', device_type_name: 'Device',
      tests: ['alpha', 'beta', 'empty', 'broken'].map((id) => ({ id, test_name: id, sample_rate_hz: id === 'beta' ? 2 : 10 })),
    }] });
    if (/\/test-runs\/[^/]+\/$/.test(path)) return respond({ flat_result_data: null });
    const samples = path.match(/\/test-runs\/([^/]+)\/signals\/signal\/$/);
    if (samples) {
      const id = samples[1];
      sampleRequests.push(id);
      if (id === 'beta') return new Promise<void>((resolve) => {
        finishBeta = async () => { await respond({ id: 'signal', name: 'beta signal', samples: Array.from({ length: 11 }, (_, i) => i * 2) }); resolve(); };
      });
      if (id === 'broken' && failBroken) {
        failBroken = false;
        return route.fulfill({ status: 500, json: { detail: 'Temporary signal failure' } });
      }
      return respond({ id: 'signal', name: `${id} signal`, samples: Array.from({ length: 11 }, (_, i) => i) });
    }
    const signals = path.match(/\/test-runs\/([^/]+)\/signals\/$/);
    if (signals) return respond(signals[1] === 'empty' ? [] : [{ id: 'signal', name: `${signals[1]} signal`, sample_count: 11 }]);
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/serial-batches/batch/serials/serial');
  await page.getByRole('button', { name: 'Plot signals', exact: true }).click();
  const dialog = page.getByRole('dialog');
  const selector = dialog.getByRole('button', { name: 'Change test', exact: true });
  const choose = async (name: string) => {
    await selector.click();
    await page.getByRole('menuitem', { name, exact: true }).click();
  };
  const chart = dialog.getByRole('img', { name: 'Signal chart', exact: true });
  await expect(chart.locator('canvas')).toBeVisible({ timeout: 30_000 });
  await expect(selector).toHaveText('alpha');
  const size = (await selector.boundingBox())!;
  expect(size.height).toBeLessThanOrEqual(28);
  expect(size.width).toBeLessThan(100);
  expect(sampleRequests).toEqual(['alpha']);
  const bounds = (await chart.boundingBox())!;
  await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + bounds.height / 2);
  await page.mouse.wheel(0, -100);
  await expect(dialog.getByLabel('Visible time range')).not.toHaveText('Time: 0–1 s');

  await choose('beta');
  await expect.poll(() => Boolean(finishBeta)).toBe(true);
  await expect(selector).toHaveText('beta');
  await expect(dialog.getByLabel('Loading signals')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'alpha signal', exact: true })).toHaveCount(0);
  // Switching remains available during loading, including tests with no signals.
  await choose('empty');
  await expect(dialog.getByText('No signals stored for this test', { exact: true })).toBeVisible();
  await finishBeta!();
  await expect(selector).toHaveText('empty');
  await expect(chart).toHaveCount(0);
  await choose('beta');
  await expect(chart.locator('canvas')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'beta signal', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(dialog.getByLabel('Visible time range')).toHaveText('Time: 0–5 s');
  expect(sampleRequests.filter((id) => id === 'beta')).toHaveLength(1);

  await choose('broken');
  await expect(dialog.getByRole('alert')).toContainText('Temporary signal failure');
  await expect(selector).toHaveText('broken');
  await dialog.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(dialog.getByRole('button', { name: 'broken signal', exact: true })).toBeVisible();
  await expect(dialog.getByLabel('Visible time range')).toHaveText('Time: 0–1 s');
  await page.setViewportSize({ width: 390, height: 844 });
  await choose('alpha');
  await expect(dialog.getByRole('button', { name: 'alpha signal', exact: true })).toBeVisible();
  await expect(dialog.getByLabel('Visible time range')).toHaveText('Time: 0–1 s');
  await expect.poll(() => dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBe(true);
  await page.screenshot({ path: test.info().outputPath('test-selector-mobile.png') });
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Results for alpha', exact: true })).toBeVisible();
});
