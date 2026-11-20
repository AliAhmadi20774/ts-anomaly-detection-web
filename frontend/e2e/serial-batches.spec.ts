import { expect, test } from '@playwright/test';

test.use({ actionTimeout: 15_000 });

test('opens a batch, then its serial, test, and signals', async ({ page, context }) => {
  test.skip(!process.env.E2E_PERSONNEL_CODE || !process.env.E2E_PASSWORD, 'Supply test login credentials.');
  const marker = `batch-ui-${Date.now()}`;
  const created: string[] = [];
  let csrfToken = '';
  const csrfHeaders = async () => ({ 'X-CSRFToken': csrfToken });

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

    response = await context.request.post('/backend/api/test-runs/', {
      data: { test: definition.id, device_serial_number: marker, executed_at: new Date().toISOString() },
      headers: await csrfHeaders(),
    });
    expect(response.status()).toBe(201);
    const run = await response.json();
    created.push(`/backend/api/test-runs/${run.id}/`);

    await page.goto('/serial-batches');
    await expect(page.getByText('Serial batches', { exact: true }).last()).toBeVisible();
    await expect(page.getByRole('button', { name: 'New test run' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Edit' })).toHaveCount(0);
    await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(0);
    await expect(page.getByRole('columnheader', { name: 'Device type' })).toBeVisible();
    await expect(page.getByRole('columnheader', { name: 'Tests' })).toHaveCount(0);
    await expect(page.getByRole('columnheader', { name: 'Batch ID' })).toHaveCount(0);

    const batchRow = page.getByRole('row').filter({ hasText: marker });
    await expect(batchRow).toBeVisible();
    await expect(batchRow).not.toContainText(run.measurement_batch.slice(0, 8));
    await batchRow.getByRole('link').click();
    await expect(page).toHaveURL(new RegExp(`/serial-batches/${run.measurement_batch}$`));
    await expect(page.getByText('Batch details', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(run.measurement_batch.slice(0, 8), { exact: true })).toHaveCount(0);
    await expect(page.getByText(`Tests for ${marker}`)).toHaveCount(0);
    await page.getByRole('link', { name: `${marker} / ${marker} · 1 tests` }).click();
    await expect(page).toHaveURL(new RegExp(`/serial-batches/${run.measurement_batch}/serials/[^/]+$`));
    await expect(page.getByText('Serial details', { exact: true }).first()).toBeVisible();
    await expect(page.getByText(`Tests for ${marker}`)).toBeVisible();
    await page.getByRole('button', { name: marker, exact: true }).click();
    await expect(page.getByText(`Signals for ${marker}`)).toBeVisible();
    await expect(page.getByText('No stored signals for this test')).toBeVisible();
    await page.getByRole('link', { name: 'Back to batch' }).click();
    await expect(page.getByRole('link', { name: `${marker} / ${marker} · 1 tests` })).toBeVisible();
  } finally {
    for (const path of created.reverse()) {
      const response = await context.request.delete(path, { headers: await csrfHeaders() });
      expect([204, 404]).toContain(response.status());
    }
  }
});
