import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';

test.use({ actionTimeout: 15_000 });

test('previews files for the selected device type', async ({ page }) => {
  test.skip(!process.env.E2E_PERSONNEL_CODE || !process.env.E2E_PASSWORD || !process.env.DAT_CURRENT_SAMPLE || !process.env.DAT_DEVICE_TYPE, 'Supply login credentials, a current-format sample and its device type.');
  await page.goto('/user/login');
  await page.getByLabel('Personnel code', { exact: true }).fill(process.env.E2E_PERSONNEL_CODE || '');
  await page.getByLabel('Password', { exact: true }).fill(process.env.E2E_PASSWORD || '');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/backend-status/, { timeout: 30_000 });
  await page.goto('/dat-preview');
  await expect(page.locator('input[type="file"]')).toBeDisabled();
  await page.getByRole('combobox', { name: 'Device type' }).click();
  await page.locator('.ant-select-item-option').filter({ hasText: process.env.DAT_DEVICE_TYPE || '' }).click();
  await expect(page.locator('input[type="file"]')).toBeEnabled();

  const sample = resolve(process.env.DAT_CURRENT_SAMPLE || '');
  await page.locator('input[type="file"]').setInputFiles([
    { name: 'previous.dat', mimeType: 'application/octet-stream', buffer: readFileSync(sample) },
  ]);
  await expect(page.getByText('1 file selected', { exact: true })).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles([
    { name: 'current.dat', mimeType: 'application/octet-stream', buffer: readFileSync(sample) },
    { name: 'repeated.dat', mimeType: 'application/octet-stream', buffer: readFileSync(sample) },
    { name: 'broken.dat', mimeType: 'application/octet-stream', buffer: Buffer.from('invalid-file') },
  ]);
  await expect(page.getByText('3 files selected', { exact: true })).toBeVisible();
  await expect(page.getByText('previous.dat', { exact: true })).toHaveCount(0);
  const responsePromise = page.waitForResponse((response) => response.url().endsWith('/api/dat/preview/') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Preview files', exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.summary).toMatchObject({ files: 3, readable: 2, errors: 1 });
  expect(data.files[0].format).toBe('current');
  expect(data.files[1].format).toBe('current');
  await expect(page.getByText('Select a device type, then preview and import DAT files', { exact: true })).toBeVisible();

  const currentRow = page.getByRole('row').filter({ hasText: 'current.dat' });
  await currentRow.getByRole('button', { name: 'Expand row', exact: true }).click();
  await page.getByText('Vibration · 2 signals', { exact: true }).click();
  await expect(page.getByText('Operator 007', { exact: true })).toBeVisible();
  await expect(page.getByText('1405/08/28 10:30', { exact: true })).toBeVisible();
  await expect(page.getByText('RMS', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'temperature', exact: true })).toBeVisible();
});
