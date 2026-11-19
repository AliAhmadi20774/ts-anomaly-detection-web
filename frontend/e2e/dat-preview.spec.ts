import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, test } from '@playwright/test';

test.use({ actionTimeout: 15_000 });

test('previews a mixed batch with legacy files, current metadata, duplicates and errors', async ({ page }) => {
  test.skip(!process.env.E2E_PERSONNEL_CODE || !process.env.E2E_PASSWORD || !process.env.DAT_CURRENT_SAMPLE, 'Supply login credentials and a current-format sample.');
  await page.goto('/user/login');
  await page.getByLabel('Personnel code', { exact: true }).fill(process.env.E2E_PERSONNEL_CODE || '');
  await page.getByLabel('Password', { exact: true }).fill(process.env.E2E_PASSWORD || '');
  await page.getByRole('button', { name: 'Sign in', exact: true }).click();
  await expect(page).toHaveURL(/\/backend-status/, { timeout: 30_000 });
  await page.goto('/dat-preview');

  const sample = resolve(__dirname, '../../legacy/data/sample_dat_files/sample_001.dat');
  await page.locator('input[type="file"]').setInputFiles([
    { name: 'sample_001.dat', mimeType: 'application/octet-stream', buffer: readFileSync(sample) },
    { name: 'current.dat', mimeType: 'application/octet-stream', buffer: readFileSync(process.env.DAT_CURRENT_SAMPLE || '') },
    { name: 'duplicate.dat', mimeType: 'application/octet-stream', buffer: readFileSync(sample) },
    { name: 'broken.dat', mimeType: 'application/octet-stream', buffer: Buffer.from('invalid-file') },
  ]);
  await expect(page.getByText('4 files selected', { exact: true })).toBeVisible();
  const responsePromise = page.waitForResponse((response) => response.url().endsWith('/api/dat/preview/') && response.request().method() === 'POST');
  await page.getByRole('button', { name: 'Preview files', exact: true }).click();
  const response = await responsePromise;
  expect(response.status()).toBe(200);
  const data = await response.json();
  expect(data.summary).toMatchObject({ files: 4, readable: 2, duplicates: 1, errors: 1 });
  expect(data.files[0].format).toBe('legacy');
  expect(data.files[1].format).toBe('current');
  await expect(page.getByText('Preview only · no records are saved yet', { exact: true })).toBeVisible();

  const currentRow = page.getByRole('row').filter({ hasText: 'current.dat' });
  await currentRow.getByRole('button', { name: 'Expand row', exact: true }).click();
  await page.getByText('Vibration · 2 signals', { exact: true }).click();
  await expect(page.getByText('Operator 007', { exact: true })).toBeVisible();
  await expect(page.getByText('1405/08/28 10:30', { exact: true })).toBeVisible();
  await expect(page.getByText('RMS', { exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: 'temperature', exact: true })).toBeVisible();
});
