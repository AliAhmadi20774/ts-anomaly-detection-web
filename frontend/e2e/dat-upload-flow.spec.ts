import { expect, test } from '@playwright/test';

test('keeps each DAT selection and import batch separate', async ({ page }) => {
  const sent: { action: string; names: string[] }[] = [];
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const names = [...(route.request().postData() || '').matchAll(/filename="([^"]+)"/g)].map((match) => match[1]);
    const respond = (data: object) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) });

    if (path.endsWith('/auth/me/')) {
      return respond({ id: 1, username: 'tester', name: 'Tester', is_superuser: true, permissions: [] });
    }
    if (path.endsWith('/device-types/')) {
      return respond({ count: 1, next: null, previous: null, results: [
        { id: '11111111-1111-4111-8111-111111111111', name: 'device1' },
      ] });
    }
    if (path.endsWith('/auth/csrf/')) return respond({ csrfToken: 'test' });
    if (path.endsWith('/dat/preview/')) {
      sent.push({ action: 'preview', names });
      return respond({ previewed_by_code: 'tester',
        summary: { files: names.length, readable: names.length, errors: 0, devices: 1, tests: names.length, signals: names.length },
        files: names.map((name, index) => ({ index, name, size: 4, status: 'ready', format: 'current', warnings: [], devices: [] })),
      });
    }
    if (path.endsWith('/dat/import/')) {
      sent.push({ action: 'import', names });
      return respond({ batch: null,
        summary: { files: names.length, imported: names.length, skipped: 0, errors: 0, test_runs: names.length },
        files: names.map((name) => ({ name, status: 'imported', test_runs: 1 })),
      });
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: '{}' });
  });

  await page.goto('/dat-preview');
  const input = page.locator('input[type="file"]');
  await expect(input).toBeDisabled();
  await page.getByRole('combobox', { name: 'Device type' }).click();
  await page.locator('.ant-select-item-option').filter({ hasText: 'device1' }).click();
  await expect(input).toBeEnabled();

  const file = (name: string) => ({ name, mimeType: 'application/octet-stream', buffer: Buffer.from('test') });
  await input.setInputFiles([file('previous.dat')]);
  await expect(page.getByText('1 file selected', { exact: true })).toBeVisible();
  await input.setInputFiles([file('first.dat'), file('second.dat')]);
  await expect(page.getByText('2 files selected', { exact: true })).toBeVisible();
  await expect(page.getByText('previous.dat', { exact: true })).toHaveCount(0);

  await page.getByRole('button', { name: 'Preview files' }).click();
  await expect(page.getByText('Selection summary')).toBeVisible();
  expect(sent.at(-1)).toEqual({ action: 'preview', names: ['first.dat', 'second.dat'] });

  await page.locator('.ant-upload-list-item').filter({ hasText: 'first.dat' }).locator('button').click();
  await expect(page.getByText('1 file selected', { exact: true })).toBeVisible();
  await expect(page.getByText('Selection summary')).toHaveCount(0);
  await page.getByRole('button', { name: 'Preview files' }).click();
  await expect(page.getByText('Selection summary')).toBeVisible();
  expect(sent.at(-1)).toEqual({ action: 'preview', names: ['second.dat'] });

  await page.getByRole('button', { name: 'Import 1 ready file' }).click();
  await expect(page.getByText('Imported 1 files and 1 test runs')).toBeVisible();
  await expect(page.getByText('0 files selected', { exact: true })).toBeVisible();
  expect(sent.at(-1)).toEqual({ action: 'import', names: ['second.dat'] });

  await input.setInputFiles([file('second.dat')]);
  await expect(page.getByText('1 file selected', { exact: true })).toBeVisible();
  await expect(page.getByText('Imported 1 files and 1 test runs')).toHaveCount(0);
});
