import { expect, test } from '@playwright/test';
import { Workbook } from 'exceljs';

test('shows complete result tables beside the tests and switches between them', async ({ page }) => {
  const signalRequests: string[] = [];
  const apiRequests: string[] = [];
  page.on('request', (request) => {
    if (request.url().includes('/signals/')) signalRequests.push(request.url());
    if (request.url().includes('/backend/api/')) apiRequests.push(request.url());
  });
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (path.endsWith('/auth/me/')) {
      return respond({ id: 1, username: 'tester', name: 'Tester', is_superuser: true, permissions: [] });
    }
    if (path.endsWith('/measurement-batches/batch/')) {
      return respond({ id: 'batch', created_at: '2026-11-22T07:00:00Z', recorded_by_code: 'tester', devices: [{
        id: 'serial', device_type: 'device', device_type_name: 'device1', serial_number: 'SN-001',
        tests: ['first', 'second', 'empty'].map((id) => ({
          id, test: id, test_name: id, executed_at: '2026-11-20T07:00:00Z', sample_rate_hz: 1000,
        })),
      }] });
    }
    if (path.endsWith('/test-runs/first/')) {
      const baseRows = [['RMS', '001.20'], ['Peak', ''], ['Label', 'نتیجه'], ['Formula', '=1+1'], ['B', '5'], ['Last row', '6']];
      return respond({ id: 'first', source_operator_name: 'sample-operator', source_file_name: 'reference.dat',
        flat_result_data: { columns: ['Name', 'Value', ...Array.from({ length: 10 }, (_, i) => `Column ${i + 3}`)], column_count: 12,
          flattened_rows: Array.from({ length: 20 }, (_, i) => [
            ...(baseRows[i] || [`Row ${i + 1}`, String(i + 1)]), ...Array.from({ length: 10 }, (_, column) => `${i}.${column}`),
          ]).flat() },
      });
    }
    if (path.endsWith('/test-runs/second/')) {
      return respond({ id: 'second', source_operator_name: '', source_file_name: '',
        flat_result_data: { columns: ['Metric', 'Reading', 'Unit'], column_count: 3,
          flattened_rows: ['Humidity', '60.000000', '%'] },
      });
    }
    if (path.endsWith('/test-runs/empty/')) return respond({ id: 'empty', flat_result_data: null });
    return route.fulfill({ status: 404, json: {} });
  });

  await page.goto('/serial-batches/batch/serials/serial');
  const tests = page.getByRole('region', { name: 'Tests for SN-001', exact: true });
  const first = page.getByRole('region', { name: 'Results for first', exact: true });
  await expect(first.getByRole('cell', { name: '001.20', exact: true })).toBeVisible({ timeout: 30_000 });
  await expect(first.getByRole('cell', { name: 'نتیجه', exact: true })).toBeVisible();
  await expect(first.getByRole('cell', { name: 'Last row', exact: true })).toBeVisible();
  const left = await tests.boundingBox();
  const right = await first.boundingBox();
  expect(left && right && left.x + left.width <= right.x).toBeTruthy();
  expect(left!.height).toBeLessThan(right!.height);
  expect(left!.width).toBe(230);
  await expect(tests.getByText('1000 Hz', { exact: true })).toHaveCount(0);
  await expect(tests.getByRole('button', { name: 'first', exact: true })).toContainText('1405/08/29 10:30:00');
  expect(await first.locator('.ant-table-content').evaluate((element) =>
    element.scrollWidth <= element.clientWidth + 1 && element.scrollHeight <= element.clientHeight + 1)).toBeTruthy();
  await expect(first.locator('.ant-table-tbody > tr[data-row-key]')).toHaveCount(20);
  await expect(first.locator('.ant-pagination')).toHaveCount(0);
  const requestsBeforeFirstExport = apiRequests.length;
  const downloadPromise = page.waitForEvent('download');
  await first.getByRole('button', { name: 'Export Excel', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('first_first.xlsx');
  expect(await download.failure()).toBeNull();
  expect(apiRequests).toHaveLength(requestsBeforeFirstExport);
  const firstExcel = new Workbook();
  await firstExcel.xlsx.readFile((await download.path())!);
  const firstSheet = firstExcel.getWorksheet('Results')!;
  expect(firstSheet.rowCount).toBe(21);
  expect(firstSheet.columnCount).toBe(12);
  expect(firstSheet.getCell('B2').value).toBe('001.20');
  expect(firstSheet.getCell('B3').value).toBe('');
  expect(firstSheet.getCell('B4').value).toBe('نتیجه');
  expect(firstSheet.getCell('B5').value).toBe('=1+1');
  expect(firstSheet.getCell('A21').value).toBe('Row 20');
  expect(firstSheet.getCell('L21').value).toBe('19.9');
  for (const button of await tests.getByRole('button').all()) {
    expect((await button.boundingBox())!.height).toBe(56);
  }
  await expect(page.getByRole('combobox', { name: 'Signal', exact: true })).toHaveCount(0);
  await page.screenshot({ path: test.info().outputPath('desktop-results.png'), fullPage: true });
  await expect(first.getByRole('cell', { name: 'Row 20', exact: true })).toBeVisible();

  await page.getByRole('button', { name: 'second', exact: true }).click();
  const second = page.getByRole('region', { name: 'Results for second', exact: true });
  await expect(second.getByRole('columnheader', { name: 'Unit', exact: true })).toBeVisible();
  await expect(second.getByRole('cell', { name: '60.000000', exact: true })).toBeVisible();
  await expect(page.getByRole('cell', { name: '001.20', exact: true })).toHaveCount(0);
  const requestsBeforeSecondExport = apiRequests.length;
  const secondDownloadPromise = page.waitForEvent('download');
  await second.getByRole('button', { name: 'Export Excel', exact: true }).click();
  const secondDownload = await secondDownloadPromise;
  expect(apiRequests).toHaveLength(requestsBeforeSecondExport);
  const secondExcel = new Workbook();
  await secondExcel.xlsx.readFile((await secondDownload.path())!);
  const secondSheet = secondExcel.getWorksheet('Results')!;
  expect(secondSheet.columnCount).toBe(3);
  expect(secondSheet.rowCount).toBe(2);
  expect(secondSheet.getRow(1).values).toEqual([undefined, 'Metric', 'Reading', 'Unit']);
  expect(secondSheet.getRow(2).values).toEqual([undefined, 'Humidity', '60.000000', '%']);

  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(async () => {
    const mobileTests = await tests.boundingBox();
    const mobileResults = await second.boundingBox();
    return Boolean(mobileTests && mobileResults && mobileTests.y + mobileTests.height <= mobileResults.y);
  }).toBeTruthy();
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();

  await page.getByRole('button', { name: 'empty', exact: true }).click();
  await expect(page.getByText('No result table stored for this test')).toBeVisible();
  expect(signalRequests).toEqual([]);
});
