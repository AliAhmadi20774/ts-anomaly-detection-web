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
  await first.getByRole('button', { name: 'Table Excel', exact: true }).click();
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
  await second.getByRole('button', { name: 'Table Excel', exact: true }).click();
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

test('plots on demand and exports selected or all tests with complete raw samples', async ({ page }) => {
  // Native print dialogs are replaced by Playwright's PDF renderer below.
  await page.context().addInitScript(() => { window.print = () => {}; });
  const samples = Array.from({ length: 5001 }, (_, index) => index === 257 ? 100 : index === 5000 ? -2 : 0);
  let failFirstSampleRequest = true;
  const apiRequests: string[] = [];
  page.on('request', (request) => { if (request.url().includes('/backend/api/')) apiRequests.push(request.url()); });
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (path.endsWith('/auth/me/')) return respond({ id: 1, username: 'tester', is_superuser: true, permissions: [] });
    if (path.endsWith('/measurement-batches/batch/')) return respond({
      id: 'batch', created_at: '2026-11-22T07:00:00Z', recorded_by_code: 'tester', devices: [{
        id: 'serial', serial_number: 'SN-001', device_type: 'device', device_type_name: 'Device one',
        tests: ['alpha', 'beta'].map((id) => ({ id, test: id, test_name: id, executed_at: '2026-11-20T07:00:00Z', sample_rate_hz: 1000 })),
      }],
    });
    if (path.endsWith('/test-runs/alpha/')) return respond({ id: 'alpha', source_file_name: 'reference.dat', source_operator_name: 'اپراتور',
      flat_result_data: { columns: ['Metric', 'Reading'], column_count: 2, flattened_rows: ['Leading zero', '001.20', 'Formula text', '=1+1', '<script>test</script>', 'نتیجه'] } });
    if (path.endsWith('/test-runs/beta/')) return respond({ id: 'beta', source_file_name: 'second.dat', source_operator_name: 'Operator B',
      flat_result_data: { columns: ['Different', 'Columns', 'Unit'], column_count: 3, flattened_rows: ['Beta result', '42', '%'] } });
    if (path.endsWith('/test-runs/alpha/signals/')) return respond([
      { id: 'pressure', name: 'pressure', sample_count: samples.length }, { id: 'temperature', name: 'temperature', sample_count: 3 },
    ]);
    if (path.endsWith('/test-runs/alpha/signals/pressure/')) {
      if (failFirstSampleRequest) {
        failFirstSampleRequest = false;
        return route.fulfill({ status: 500, json: { detail: 'Temporary sample failure.' } });
      }
      return respond({ id: 'pressure', name: 'pressure', samples });
    }
    if (path.endsWith('/test-runs/alpha/signals/temperature/')) return respond({ id: 'temperature', name: 'temperature', samples: [11, 12, 13] });
    if (path.endsWith('/test-runs/beta/signals/')) return respond([{ id: 'beta-signal', name: 'beta-signal', sample_count: 2 }]);
    if (path.endsWith('/test-runs/beta/signals/beta-signal/')) return respond({ id: 'beta-signal', name: 'beta-signal', samples: [7, 8] });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/serial-batches/batch/serials/serial');
  await expect(page.getByRole('cell', { name: '001.20', exact: true })).toBeVisible({ timeout: 30000 });
  expect(apiRequests.filter((url) => url.includes('/signals/'))).toHaveLength(0);
  await page.getByRole('button', { name: 'Plot signals', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Signals for alpha' });
  await expect(dialog.getByRole('alert')).toContainText('Temporary sample failure.');
  await dialog.getByRole('button', { name: 'Retry', exact: true }).click();
  await expect(dialog.getByRole('img', { name: 'pressure signal chart', exact: true })).toBeVisible();
  await expect(dialog.locator('polyline')).toHaveAttribute('points', /133\.75,/);
  await page.screenshot({ path: test.info().outputPath('signal-graph.png') });
  await dialog.getByRole('combobox', { name: 'Signal', exact: true }).click();
  await page.getByText('temperature (3 samples)', { exact: true }).last().click();
  await expect(dialog.getByRole('img', { name: 'temperature signal chart', exact: true })).toBeVisible();
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  const beforeExport = apiRequests.length;
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Full Excel', exact: true }).click();
  const download = await downloadPromise;
  expect(apiRequests).toHaveLength(beforeExport);
  const workbook = new Workbook();
  await workbook.xlsx.readFile((await download.path())!);
  expect(workbook.worksheets.map((sheet) => sheet.name)).toEqual(['Overview', '1 Parameters', '1 Signals']);
  const raw = workbook.getWorksheet('1 Signals')!;
  expect(raw.rowCount).toBe(5002);
  expect(raw.getCell('B259').value).toBe(100);
  expect(raw.getCell('A5002').value).toBe(5000);
  expect(raw.getCell('B5002').value).toBe(-2);
  expect(raw.getCell('C2').value).toBe(11);
  expect(raw.getCell('C5').value).toBeNull();
  expect(Array.from({ length: samples.length }, (_, index) => raw.getCell(index + 2, 2).value)).toEqual(samples);
  expect(workbook.getWorksheet('1 Parameters')!.getCell('B3').value).toBe('=1+1');

  await page.getByRole('button', { name: 'Excel export options', exact: true }).click();
  const allDownloadPromise = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'Excel: all tests in this serial', exact: true }).click();
  const allDownload = await allDownloadPromise;
  const allWorkbook = new Workbook();
  await allWorkbook.xlsx.readFile((await allDownload.path())!);
  expect(allWorkbook.getWorksheet('2 Parameters')!.columnCount).toBe(3);
  expect(allWorkbook.getWorksheet('2 Signals')!.getCell('B3').value).toBe(8);

  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'PDF report', exact: true }).click();
  const report = await popupPromise;
  await expect(report.getByRole('heading', { name: 'Test report', exact: true })).toBeVisible();
  await expect(report.getByRole('heading', { name: 'alpha', exact: true })).toBeVisible();
  await expect(report.getByRole('heading', { name: 'beta', exact: true })).toHaveCount(0);
  await expect(report.getByRole('cell', { name: '<script>test</script>', exact: true })).toBeVisible();
  expect(await report.locator('script').count()).toBe(0);
  await expect(report.locator('svg')).toHaveCount(2);
  await report.pdf({ path: test.info().outputPath('selected-test-report.pdf'), preferCSSPageSize: true, printBackground: true });
  await report.close();

  await page.getByRole('button', { name: 'PDF report options', exact: true }).click();
  const allPopupPromise = page.waitForEvent('popup');
  await page.getByRole('menuitem', { name: 'PDF: all tests in this serial', exact: true }).click();
  const allReport = await allPopupPromise;
  await expect(allReport.getByRole('heading', { name: 'beta', exact: true })).toBeVisible();
  await expect(allReport.locator('svg')).toHaveCount(3);
  await allReport.pdf({ path: test.info().outputPath('all-tests-report.pdf'), preferCSSPageSize: true, printBackground: true });
  await allReport.close();
  await page.screenshot({ path: test.info().outputPath('toolbar-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: test.info().outputPath('toolbar-mobile.png'), fullPage: true });
});
