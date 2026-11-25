import { expect, test } from '@playwright/test';

test.use({ actionTimeout: 15_000 });

test('filters batches by device, resets pagination and clears the filter', async ({ page }) => {
  const requests: URL[] = [];
  await page.route('**/backend/api/**', async (route) => {
    const url = new URL(route.request().url());
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (url.pathname.endsWith('/auth/me/')) return respond({ id: 1, username: 'tester', is_superuser: true, permissions: [] });
    if (url.pathname.endsWith('/device-types/')) return respond({ count: 2, results: [{ id: 'motor', name: 'Motor' }, { id: 'sensor', name: 'Sensor' }] });
    if (url.pathname.endsWith('/measurement-batches/')) {
      requests.push(url);
      const selected = url.searchParams.get('device_type');
      const search = url.searchParams.get('search');
      const pageNumber = url.searchParams.get('page') || '1';
      return respond({ count: selected || search ? 1 : 40, results: [{ id: `${selected || 'all'}-${pageNumber}`,
        created_at: '2026-11-22T07:00:00Z', recorded_by_code: `${selected || 'all'}${search ? ` ${search}` : ''} page ${pageNumber}`,
        devices: [{ device_type_name: selected === 'sensor' ? 'Sensor' : 'Motor' }],
      }] });
    }
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/serial-batches');
  await expect(page.getByRole('cell', { name: 'all page 1', exact: true })).toBeVisible({ timeout: 30_000 });
  await page.getByTitle('2', { exact: true }).click();
  await expect(page.getByRole('cell', { name: 'all page 2', exact: true })).toBeVisible();
  const selector = page.getByRole('combobox', { name: 'Filter by device type', exact: true });
  await selector.click();
  await page.getByText('Sensor', { exact: true }).click();
  await expect(page.getByRole('cell', { name: 'sensor page 1', exact: true })).toBeVisible();
  expect(requests.at(-1)!.searchParams.get('device_type')).toBe('sensor');
  expect(requests.at(-1)!.searchParams.get('page')).toBe('1');
  const serialSearch = page.getByRole('searchbox', { name: 'Search serial number', exact: true });
  await serialSearch.fill('SN-002');
  await serialSearch.press('Enter');
  await expect(page.getByRole('cell', { name: 'sensor SN-002 page 1', exact: true })).toBeVisible();
  expect(requests.at(-1)!.searchParams.get('device_type')).toBe('sensor');
  expect(requests.at(-1)!.searchParams.get('search')).toBe('SN-002');
  await page.locator('.ant-select-clear').click();
  await expect(page.getByRole('cell', { name: 'all SN-002 page 1', exact: true })).toBeVisible();
  await page.locator('.ant-input-clear-icon').click();
  await expect(page.getByRole('cell', { name: 'all page 1', exact: true })).toBeVisible();
  expect(requests.at(-1)!.searchParams.get('device_type')).toBeNull();
  expect(requests.at(-1)!.searchParams.get('search')).toBeNull();
  await page.screenshot({ path: test.info().outputPath('batch-device-filter.png') });
});
