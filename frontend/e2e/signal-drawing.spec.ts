import { expect, test } from '@playwright/test';
import { readFile } from 'node:fs/promises';

test.use({ actionTimeout: 15_000 });

test('draws and erases annotations, preserves chart navigation and saves a composed PNG', async ({ page }) => {
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (path.endsWith('/auth/me/')) return respond({ id: 1, username: 'tester', is_superuser: true, permissions: [] });
    if (path.endsWith('/measurement-batches/batch/')) return respond({ id: 'batch', created_at: '2026-11-22T07:00:00Z', devices: [{
      id: 'serial', serial_number: 'SN-001', device_type: 'device', device_type_name: 'Device one',
      tests: [{ id: 'run', test: 'run', test_name: 'Drawing test', executed_at: '2026-11-20T07:00:00Z', sample_rate_hz: 10 }],
    }] });
    if (path.endsWith('/test-runs/run/')) return respond({ id: 'run', flat_result_data: null });
    if (path.endsWith('/test-runs/run/signals/')) return respond([{ id: 'signal', name: 'Signal', sample_count: 11 }]);
    if (path.endsWith('/signals/signal/')) return respond({ id: 'signal', name: 'Signal', samples: Array.from({ length: 11 }, (_, index) => index) });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/serial-batches/batch/serials/serial');
  await page.getByRole('button', { name: 'Plot signals', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Signals for Drawing test' });
  const plot = dialog.getByRole('img', { name: 'Signal chart', exact: true });
  await expect(plot.locator('canvas')).toBeVisible({ timeout: 30_000 });
  const bounds = (await plot.boundingBox())!;
  const x = (time: number) => bounds.x + 84 + (bounds.width - 108) * time;
  const y = (value: number) => bounds.y + 60 + (10.6 - value) / 11.2 * (bounds.height - 116);
  const tools = dialog.getByRole('button', { name: 'Drawing tools', exact: true });
  const selectTool = async (name: string) => {
    await tools.click();
    await page.getByRole('menuitem', { name, exact: true }).click();
  };
  const pen = dialog.locator('[data-drawing-kind="pen"]');
  const line = dialog.locator('[data-drawing-kind="line"]');
  const visibleTime = dialog.getByLabel('Visible time range');
  await expect(tools).toHaveCount(1);
  await selectTool('Pen');
  await expect(tools).toHaveAttribute('data-tool', 'pen');
  await page.mouse.move(x(0.15), y(8));
  await page.mouse.down();
  await page.mouse.move(x(0.3), y(8.7), { steps: 8 });
  await page.mouse.move(x(0.4), y(8), { steps: 8 });
  await page.mouse.up();
  await expect(pen).toHaveCount(1);
  const initialPen = await pen.getAttribute('d');
  await expect(visibleTime).toHaveText('Time: 0–1 s');
  await selectTool('Line');
  await page.mouse.move(x(0.55), y(8));
  await page.mouse.down();
  await page.mouse.move(x(0.85), y(6), { steps: 8 });
  await page.mouse.up();
  await expect(line).toHaveCount(1);
  expect((await line.getAttribute('d'))!.match(/L/g)).toHaveLength(1);
  await expect(visibleTime).toHaveText('Time: 0–1 s');

  await selectTool('Pointer');
  // Two real-sample measurement points must also appear in the saved image.
  for (const time of [0.2, 0.8]) {
    await page.mouse.move(x(time), y(time * 10));
    await expect(dialog.getByRole('tooltip', { name: 'Signal coordinates' })).toBeVisible();
    await page.keyboard.down('Shift');
    await page.mouse.click(x(time), y(time * 10));
    await page.keyboard.up('Shift');
  }
  await expect(dialog.getByLabel('Average slope', { exact: true })).toHaveText('10 value/s');
  await tools.click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'Screenshot', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('Drawing test_signals.png');
  expect(await download.failure()).toBeNull();
  const imagePath = test.info().outputPath('chart-with-drawings.png');
  await download.saveAs(imagePath);
  const png = await readFile(imagePath);
  expect(png.subarray(1, 4).toString()).toBe('PNG');
  expect(png.readUInt32BE(16)).toBe(bounds.width * 2);
  expect(png.readUInt32BE(20)).toBe(bounds.height * 2);
  const pixel = await page.evaluate(async ({ base64, px, py }) => {
    const image = new Image();
    image.src = `data:image/png;base64,${base64}`;
    await image.decode();
    const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
    const context = canvas.getContext('2d')!; context.drawImage(image, 0, 0);
    const pixels = context.getImageData(Math.round(px * 2) - 2, Math.round(py * 2) - 2, 5, 5).data;
    for (let index = 0; index < pixels.length; index += 4) {
      if (pixels[index] > 150 && pixels[index + 1] < 140 && pixels[index] > pixels[index + 2] + 40) return [...pixels.slice(index, index + 4)];
    }
    return [...pixels.slice(0, 4)];
  }, { base64: png.toString('base64'), px: x(0.65) - bounds.x, py: y(8 - 0.1 * 2 / 0.3) - bounds.y });
  expect(pixel[0]).toBeGreaterThan(150);
  expect(pixel[1]).toBeLessThan(140);
  await page.screenshot({ path: test.info().outputPath('drawing-workspace.png') });

  // Data-anchored drawings follow zoom, pan and reset without changing the signals.
  await page.mouse.move(x(0.5), y(5));
  await page.mouse.wheel(0, -100);
  await expect(visibleTime).not.toHaveText('Time: 0–1 s');
  await expect(pen).not.toHaveAttribute('d', initialPen!);
  const range = async () => (await visibleTime.innerText()).match(/Time: ([\d.e+-]+)–([\d.e+-]+) s/)!.slice(1).map(Number);
  const beforeAuto = await range();
  const beforeY = (await line.getAttribute('d'))!.match(/[ML][^ML]+/g)!.map((point) => Number(point.slice(1).split(',')[1]));
  const autoScroll = dialog.getByRole('img', { name: 'Horizontal scrolling', exact: true });
  await page.mouse.click(x(0.5), y(5), { button: 'middle' });
  await expect(autoScroll).toBeVisible();
  await page.mouse.move(x(0.5) + 120, y(5) - 80);
  await expect.poll(async () => (await range())[0]).toBeGreaterThan(beforeAuto[0] + 0.001);
  const afterAuto = await range();
  expect(afterAuto[1] - afterAuto[0]).toBeCloseTo(beforeAuto[1] - beforeAuto[0], 5);
  const afterY = (await line.getAttribute('d'))!.match(/[ML][^ML]+/g)!.map((point) => Number(point.slice(1).split(',')[1]));
  afterY.forEach((value, index) => expect(value).toBeCloseTo(beforeY[index], 5));
  await page.mouse.click(x(0.5) + 120, y(5), { button: 'middle' });
  await expect(autoScroll).toHaveCount(0);
  const stopped = await visibleTime.innerText();
  await page.mouse.move(x(0.5) - 120, y(5));
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))));
  await expect(visibleTime).toHaveText(stopped);
  const beforeLeft = await range();
  await page.mouse.click(x(0.5), y(5), { button: 'middle' });
  await page.mouse.move(x(0.5) - 120, y(5));
  await expect.poll(async () => (await range())[0]).toBeLessThan(beforeLeft[0] - 0.001);
  await page.keyboard.press('Escape');
  await expect(autoScroll).toHaveCount(0);
  await expect(dialog.getByRole('region', { name: 'Signal measurement' })).toBeVisible();
  await expect(visibleTime).not.toHaveText('Time: 0–1 s');
  await page.mouse.move(x(0.5), y(5));
  const beforePan = await line.getAttribute('d');
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(x(0.5) + 25, y(5), { steps: 5 });
  await page.mouse.up({ button: 'right' });
  await expect(line).not.toHaveAttribute('d', beforePan!);
  await plot.dblclick({ position: { x: bounds.width / 2, y: 100 } });
  await expect(visibleTime).toHaveText('Time: 0–1 s');
  await expect(pen).toHaveAttribute('d', initialPen!);
  await selectTool('Eraser');
  await page.mouse.move(x(0.7), y(8));
  await page.mouse.down();
  await page.mouse.move(x(0.7), y(6), { steps: 5 });
  await page.mouse.up();
  await expect(line).toHaveCount(0);
  await expect(pen).toHaveCount(1);
  await expect(dialog.getByRole('region', { name: 'Signal measurement' })).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(tools).toHaveAttribute('data-tool', 'pointer');
  await expect(dialog).toBeVisible();
  await page.keyboard.press('Escape');
  await expect(dialog.getByRole('region', { name: 'Signal measurement' })).toHaveCount(0);
  await expect(pen).toHaveCount(1);
  // Cancel a pending stroke with Esc without committing it or closing the chart.
  await selectTool('Pen');
  await page.mouse.move(x(0.2), y(6));
  await page.mouse.down();
  await page.mouse.move(x(0.3), y(6.5));
  await page.keyboard.press('Escape');
  await page.mouse.up();
  await expect(pen).toHaveCount(1);
  await expect(tools).toHaveAttribute('data-tool', 'pointer');
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
});
