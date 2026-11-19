import { expect, test } from '@playwright/test';

test.use({ actionTimeout: 15_000 });

test('records and edits a test execution with server-assigned metadata', async ({ page, context }) => {
  test.skip(!process.env.E2E_PERSONNEL_CODE || !process.env.E2E_PASSWORD, 'Supply test login credentials.');
  const marker = `run-ui-${Date.now()}`;
  const created: string[] = [];
  let csrfToken = '';
  const csrfHeaders = async () => ({
    'X-CSRFToken': csrfToken,
  });

  try {
    await page.goto('/user/login');
    await page.getByLabel('Personnel code', { exact: true }).fill(process.env.E2E_PERSONNEL_CODE || '');
    await page.getByLabel('Password', { exact: true }).fill(process.env.E2E_PASSWORD || '');
    await page.getByRole('button', { name: 'Sign in', exact: true }).click();
    await expect(page).toHaveURL(/\/backend-status/, { timeout: 30_000 });
    csrfToken = (await context.cookies()).find((cookie) => cookie.name === 'csrftoken')?.value || '';

    let response = await context.request.post('/backend/api/device-types/', {
      data: { name: marker }, headers: await csrfHeaders(),
    });
    expect(response.status()).toBe(201);
    const device = await response.json();
    created.push(`/backend/api/device-types/${device.id}/`);
    response = await context.request.post('/backend/api/test-definitions/', {
      data: { name: marker, device_type: device.id, sample_rate_hz: 1000 },
      headers: await csrfHeaders(),
    });
    expect(response.status()).toBe(201);
    const definition = await response.json();
    created.push(`/backend/api/test-definitions/${definition.id}/`);

    await page.goto('/test-runs');
    await page.getByRole('button', { name: /New test run/ }).click();
    let dialog = page.getByRole('dialog');
    await dialog.getByRole('combobox', { name: 'Test', exact: true }).fill(marker);
    await page.locator('.ant-select-dropdown').getByText(`${marker} / ${marker}`, { exact: true }).click();
    await dialog.getByLabel('Serial number', { exact: true }).fill(marker);
    await dialog.getByLabel('Notes', { exact: true }).fill('Baseline execution');
    const saved = page.waitForResponse((item) =>
      item.url().endsWith('/api/test-runs/') && item.request().method() === 'POST');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    response = await saved;
    expect(response.status()).toBe(201);
    const run = await response.json();
    created.push(`/backend/api/test-runs/${run.id}/`);
    expect(run.sample_rate_hz).toBe(1000);
    expect(run.recorded_by_code).toBe(process.env.E2E_PERSONNEL_CODE);

    const row = page.getByRole('row').filter({ hasText: marker });
    await expect(row).toBeVisible();
    await row.getByRole('button', { name: 'Edit', exact: true }).click();
    dialog = page.getByRole('dialog');
    await expect(dialog.getByRole('combobox', { name: 'Test', exact: true })).toBeDisabled();
    await expect(dialog.getByLabel('Notes', { exact: true })).toHaveValue('Baseline execution');
    await dialog.getByLabel('Notes', { exact: true }).fill('Corrected execution');
    const updated = page.waitForResponse((item) =>
      item.url().endsWith(`/api/test-runs/${run.id}/`) && item.request().method() === 'PATCH');
    await dialog.getByRole('button', { name: 'Save', exact: true }).click();
    response = await updated;
    expect(response.status()).toBe(200);
    expect((await response.json()).notes).toBe('Corrected execution');
    await expect(page.getByRole('dialog')).not.toBeVisible();

    let documentLoads = 0;
    page.on('load', () => { documentLoads += 1; });
    await page.waitForTimeout(5000);
    expect(documentLoads).toBe(0);
    await expect(row).toBeVisible();
  } finally {
    for (const path of created.reverse()) {
      const response = await context.request.delete(path, { headers: await csrfHeaders() });
      expect([204, 404]).toContain(response.status());
    }
  }
});
