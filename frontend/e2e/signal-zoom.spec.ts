import { expect, test } from '@playwright/test';

test('wheel zoom is gradual, reversible and restores both axes after box zoom', async ({ page }) => {
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (path.endsWith('/auth/me/')) return respond({ id: 1, username: 'tester', is_superuser: true, permissions: [] });
    if (path.endsWith('/measurement-batches/batch/')) return respond({ id: 'batch', devices: [{
      id: 'serial', serial_number: 'SN-001', device_type_name: 'Device', tests: [{
        id: 'run', test_name: 'Zoom test', executed_at: '2026-11-20T07:00:00Z', sample_rate_hz: 100,
      }],
    }] });
    if (path.endsWith('/test-runs/run/')) return respond({ id: 'run', flat_result_data: null });
    if (path.endsWith('/test-runs/run/signals/')) return respond([{ id: 'signal', name: 'Signal', sample_count: 101 }]);
    if (path.endsWith('/signals/signal/')) return respond({ id: 'signal', name: 'Signal', samples: Array.from({ length: 101 }, (_, i) => i / 10) });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/serial-batches/batch/serials/serial');
  await page.getByRole('button', { name: 'Plot signals', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Signals for Zoom test' });
  const plot = dialog.getByRole('img', { name: 'Signal chart', exact: true });
  await expect(plot.locator('canvas')).toBeVisible({ timeout: 30_000 });
  const bounds = (await plot.boundingBox())!;
  const width = bounds.width - 108;
  const height = bounds.height - 116;
  const x = (fraction: number) => bounds.x + 84 + width * fraction;
  const y = (fraction: number) => bounds.y + 60 + height * fraction;
  const visibleTime = dialog.getByLabel('Visible time range');
  const range = async () => (await visibleTime.innerText()).match(/Time: ([\d.e+-]+)–([\d.e+-]+) s/)!.slice(1).map(Number);
  const point = dialog.getByRole('slider', { name: 'Measurement point A', exact: true });
  const position = async () => [Number(await point.getAttribute('cx')), Number(await point.getAttribute('cy'))];
  await page.mouse.move(x(0.4), y((10.6 - 4) / 11.2));
  await expect(dialog.getByRole('tooltip', { name: 'Signal coordinates' })).toBeVisible();
  await page.keyboard.down('Shift');
  await page.mouse.click(x(0.4), y((10.6 - 4) / 11.2));
  await page.keyboard.up('Shift');
  const original = await position();

  // Off-centre zoom keeps the data under the cursor fixed on both axes.
  const anchor = [84 + width * 0.3, 60 + height * 0.7];
  await page.mouse.move(x(0.3), y(0.7));
  await page.mouse.wheel(0, -100);
  await expect.poll(async () => (await range())[1] - (await range())[0]).toBeLessThan(0.9);
  const zoomed = await position();
  // Native wheel coordinates may round to physical pixels.
  zoomed.forEach((value, i) => expect(Math.abs(value - anchor[i] - (original[i] - anchor[i]) * Math.exp(0.15))).toBeLessThan(0.5));
  await page.mouse.wheel(0, 100);
  await expect(visibleTime).toHaveText('Time: 0–1 s');
  (await position()).forEach((value, i) => expect(value).toBeCloseTo(original[i], 3));

  // A large wheel event is bounded instead of jumping straight to a tiny range.
  await page.mouse.wheel(0, -10000);
  await expect.poll(async () => (await range())[1] - (await range())[0]).toBeLessThan(0.9);
  expect((await range())[1] - (await range())[0]).toBeGreaterThan(0.8);
  await page.mouse.wheel(0, 10000);
  await expect(visibleTime).toHaveText('Time: 0–1 s');

  // Box zoom narrows Y too; wheel-out must recover Y as well as time.
  await page.mouse.move(x(0.2), y(0.2));
  await page.mouse.down();
  await page.mouse.move(x(0.8), y(0.8), { steps: 5 });
  await page.mouse.up();
  await expect(visibleTime).not.toHaveText('Time: 0–1 s');
  const boxed = await position();
  expect(Math.abs(boxed[1] - original[1])).toBeGreaterThan(10);
  await page.mouse.move(x(0.5), y(0.5));
  for (let i = 0; i < 8; i += 1) await page.mouse.wheel(0, 120);
  await expect(visibleTime).toHaveText('Time: 0–1 s');
  await expect.poll(async () => (await position())[1]).toBeCloseTo(original[1], 3);
  (await position()).forEach((value, i) => expect(value).toBeCloseTo(original[i], 3));
  await page.mouse.wheel(0, 120);
  await expect(visibleTime).toHaveText('Time: 0–1 s');
  await expect(point).toHaveAttribute('aria-valuenow', '40');

  // Line-mode wheel events use the same scale as their pixel-mode equivalent.
  await plot.evaluate((element, coordinates) => {
    element.dispatchEvent(new WheelEvent('wheel', { bubbles: true, cancelable: true, deltaY: -3, deltaMode: 1, clientX: coordinates.x, clientY: coordinates.y }));
  }, { x: x(0.5), y: y(0.5) });
  await expect.poll(async () => (await range())[1] - (await range())[0]).toBeCloseTo(Math.exp(-48 * 0.0015), 6);
});
