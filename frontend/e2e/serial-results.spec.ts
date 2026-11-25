import { expect, test } from '@playwright/test';
import { Workbook } from 'exceljs';

test.use({ actionTimeout: 15_000 });

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
    if (path.endsWith('/signals/')) return respond([]);
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
  await expect(page.getByRole('button', { name: 'Excel', exact: true })).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Table Excel', exact: true })).toHaveCount(0);
  await expect(page.getByText('SELECTED TEST', { exact: true })).toHaveCount(0);
  await expect(page.getByText('Source:', { exact: false })).toHaveCount(0);
  expect(signalRequests).toEqual([]);
  const requestsBeforeFirstExport = apiRequests.length;
  await page.getByRole('button', { name: 'Excel', exact: true }).click();
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'This test only', exact: true }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('SN-001_first.xlsx');
  expect(await download.failure()).toBeNull();
  expect(apiRequests).toHaveLength(requestsBeforeFirstExport + 1);
  const firstExcel = new Workbook();
  await firstExcel.xlsx.readFile((await download.path())!);
  expect(firstExcel.worksheets.map((sheet) => sheet.name)).toEqual(['Summary', 'first - Results']);
  const firstSheet = firstExcel.getWorksheet('first - Results')!;
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
  await page.getByRole('button', { name: 'Excel', exact: true }).click();
  const secondDownloadPromise = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'This test only', exact: true }).click();
  const secondDownload = await secondDownloadPromise;
  expect(apiRequests).toHaveLength(requestsBeforeSecondExport + 1);
  const secondExcel = new Workbook();
  await secondExcel.xlsx.readFile((await secondDownload.path())!);
  const secondSheet = secondExcel.getWorksheet('second - Results')!;
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
  expect(signalRequests).toHaveLength(2);
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
  const plot = dialog.getByRole('img', { name: 'Signal chart', exact: true });
  await expect(plot.locator('canvas')).toBeVisible({ timeout: 30_000 });
  await expect(dialog.getByRole('button', { name: /^(Pan|Box zoom|Zoom in|Zoom out|Reset view)$/ })).toHaveCount(0);
  await expect(dialog.getByRole('checkbox')).toHaveCount(0);
  await expect(dialog.getByRole('button', { name: 'Choose signals', exact: true })).toHaveCount(0);
  const pressureToggle = dialog.getByRole('button', { name: 'pressure', exact: true });
  const temperatureToggle = dialog.getByRole('button', { name: 'temperature', exact: true });
  await expect(pressureToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(temperatureToggle).toHaveAttribute('aria-pressed', 'true');
  const allToggle = dialog.getByRole('button', { name: /^(Show all|Hide all)$/ });
  await expect(allToggle).toHaveCount(1);
  await expect(allToggle).toHaveText('Hide all');
  const visibleTime = dialog.getByLabel('Visible time range');
  await expect(visibleTime).toHaveText('Time: 0–5 s');
  const bounds = (await dialog.boundingBox())!;
  expect(bounds.width).toBeGreaterThanOrEqual(page.viewportSize()!.width - 2);
  expect(bounds.height).toBeGreaterThanOrEqual(page.viewportSize()!.height - 2);
  const plotBounds = (await plot.boundingBox())!;
  expect(plotBounds.width).toBeGreaterThanOrEqual(page.viewportSize()!.width - 2);
  expect(plotBounds.height).toBeGreaterThanOrEqual(page.viewportSize()!.height - 2);
  await allToggle.click();
  await expect(pressureToggle).toHaveAttribute('aria-pressed', 'false');
  await expect(temperatureToggle).toHaveAttribute('aria-pressed', 'false');
  await expect(dialog.getByText('No signals visible', { exact: true })).toBeVisible();
  await expect(allToggle).toHaveText('Show all');
  await allToggle.click();
  await expect(pressureToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(temperatureToggle).toHaveAttribute('aria-pressed', 'true');
  await temperatureToggle.click();
  await expect(temperatureToggle).toHaveAttribute('aria-pressed', 'false');
  await expect(allToggle).toHaveText('Show all');
  await page.mouse.move(plotBounds.x + plotBounds.width / 2, plotBounds.y + plotBounds.height / 2);
  await page.mouse.wheel(0, -180);
  await expect(visibleTime).not.toHaveText('Time: 0–5 s');
  const beforeToggle = await visibleTime.innerText();
  await allToggle.click();
  await expect(temperatureToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(pressureToggle).toHaveAttribute('aria-pressed', 'true');
  await expect(allToggle).toHaveText('Hide all');
  await expect(visibleTime).toHaveText(beforeToggle);
  await plot.dblclick({ position: { x: plotBounds.width / 2, y: plotBounds.height / 2 } });
  await expect(visibleTime).toHaveText('Time: 0–5 s');
  await page.mouse.move(plotBounds.x + 110, plotBounds.y + 90);
  await page.mouse.down();
  await page.mouse.move(plotBounds.x + plotBounds.width * 0.65, plotBounds.y + plotBounds.height * 0.6, { steps: 8 });
  await page.mouse.up();
  await expect(visibleTime).not.toHaveText('Time: 0–5 s');
  const selectionRange = (await visibleTime.innerText()).match(/Time: ([\d.e+-]+)–([\d.e+-]+) s/)!;
  const selectionSpan = Number(selectionRange[2]) - Number(selectionRange[1]);
  const beforePan = await visibleTime.innerText();
  await page.evaluate(() => {
    document.addEventListener('contextmenu', (event) => {
      document.documentElement.dataset.chartContextMenuPrevented = String(event.defaultPrevented);
    }, { once: true });
  });
  await page.mouse.move(plotBounds.x + plotBounds.width / 2, plotBounds.y + plotBounds.height / 2);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(plotBounds.x + plotBounds.width * 0.6, plotBounds.y + plotBounds.height / 2, { steps: 8 });
  await page.mouse.up({ button: 'right' });
  await expect(visibleTime).not.toHaveText(beforePan);
  await expect(page.locator('html')).toHaveAttribute('data-chart-context-menu-prevented', 'true');
  const pannedRange = (await visibleTime.innerText()).match(/Time: ([\d.e+-]+)–([\d.e+-]+) s/)!;
  expect(Number(pannedRange[2]) - Number(pannedRange[1])).toBeCloseTo(selectionSpan, 5);
  await plot.dblclick({ position: { x: plotBounds.width / 2, y: plotBounds.height / 2 } });
  await expect(visibleTime).toHaveText('Time: 0–5 s');
  const coordinates = dialog.getByRole('tooltip', { name: 'Signal coordinates', exact: true });
  const xAt = (seconds: number) => plotBounds.x + 84 + (plotBounds.width - 108) * seconds / 5;
  const yAt = (value: number) => plotBounds.y + 60 + (106.12 - value) / 114.24 * (plotBounds.height - 116);
  await page.mouse.move(xAt(2), plotBounds.y + 90);
  await expect(coordinates).toHaveCount(0);
  await page.mouse.move(xAt(2), yAt(0));
  await expect(coordinates).toBeVisible();
  await expect(coordinates.getByText('pressure', { exact: true })).toBeVisible();
  await expect(coordinates.getByText('Value: 0', { exact: true })).toBeVisible();
  await expect(coordinates.getByText('temperature', { exact: true })).toHaveCount(0);
  const seconds = Number((await coordinates.getByText(/^Time: [\d.e+-]+ s$/).innerText()).match(/^Time: ([\d.e+-]+) s$/)![1]);
  expect(Math.abs(seconds - 2)).toBeLessThan(0.005);
  await page.mouse.move(xAt(0.257), yAt(100));
  await expect(coordinates.getByText('Time: 0.257 s', { exact: true })).toBeVisible();
  await expect(coordinates.getByText('Value: 100', { exact: true })).toBeVisible();
  await page.screenshot({ path: test.info().outputPath('signal-hover.png') });
  await page.mouse.move(xAt(2), plotBounds.y + 90);
  await expect(coordinates).toHaveCount(0);
  await expect(dialog.getByRole('textbox')).toHaveCount(0);
  await expect(dialog.getByText(/Left drag:|Shift \+ click|Esc to clear/)).toHaveCount(0);
  await page.screenshot({ path: test.info().outputPath('signal-graph.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  await expect(plot.locator('canvas')).toBeVisible();
  await expect(pressureToggle).toBeVisible();
  await expect(temperatureToggle).toBeVisible();
  await temperatureToggle.click();
  await expect(temperatureToggle).toHaveAttribute('aria-pressed', 'false');
  await temperatureToggle.click();
  await page.screenshot({ path: test.info().outputPath('signal-graph-mobile.png') });
  await dialog.getByRole('button', { name: 'Close', exact: true }).click();
  await page.setViewportSize({ width: 1280, height: 720 });
  const beforeExport = apiRequests.length;
  await page.getByRole('button', { name: 'Excel', exact: true }).click();
  await expect(page.locator('.ant-dropdown:visible').getByRole('menuitem')).toHaveCount(2);
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'This test only', exact: true }).click();
  const download = await downloadPromise;
  expect(apiRequests).toHaveLength(beforeExport);
  const workbook = new Workbook();
  await workbook.xlsx.readFile((await download.path())!);
  expect(workbook.worksheets.map((sheet) => sheet.name)).toEqual(['Summary', 'alpha - Results', 'alpha - Raw Signals']);
  const raw = workbook.getWorksheet('alpha - Raw Signals')!;
  expect(raw.rowCount).toBe(5002);
  expect(raw.getCell('B259').value).toBe(100);
  expect(raw.getCell('A5002').value).toBe(5000);
  expect(raw.getCell('B5002').value).toBe(-2);
  expect(raw.getCell('C2').value).toBe(11);
  expect(raw.getCell('C5').value).toBeNull();
  expect(Array.from({ length: samples.length }, (_, index) => raw.getCell(index + 2, 2).value)).toEqual(samples);
  expect(workbook.getWorksheet('alpha - Results')!.getCell('B3').value).toBe('=1+1');
  const overview = workbook.getWorksheet('Summary')!;
  expect(overview.rowCount).toBe(2);
  expect(overview.getRow(1).values).toEqual([
    undefined, 'Test', 'Serial number', 'Device type', 'Executed at', 'Operator', 'Sample rate', 'Recorded by',
  ]);
  expect(overview.getRow(2).values).toEqual([
    undefined, 'alpha', 'SN-001', 'Device one', '1405/08/29 10:30:00', 'اپراتور', '1000', 'tester',
  ]);

  await page.getByRole('button', { name: 'Excel', exact: true }).click();
  const allDownloadPromise = page.waitForEvent('download');
  await page.getByRole('menuitem', { name: 'All tests', exact: true }).click();
  const allDownload = await allDownloadPromise;
  const allWorkbook = new Workbook();
  await allWorkbook.xlsx.readFile((await allDownload.path())!);
  expect(allWorkbook.worksheets.map((sheet) => sheet.name)).toEqual([
    'Summary', 'alpha - Results', 'alpha - Raw Signals', 'beta - Results', 'beta - Raw Signals',
  ]);
  expect(allWorkbook.getWorksheet('beta - Results')!.columnCount).toBe(3);
  expect(allWorkbook.getWorksheet('beta - Raw Signals')!.getCell('B3').value).toBe(8);
  expect(allDownload.suggestedFilename()).toBe('SN-001_all_tests.xlsx');
  const allOverview = allWorkbook.getWorksheet('Summary')!;
  expect(allOverview.rowCount).toBe(3);
  expect(allOverview.getColumn(1).values.slice(2)).toEqual(['alpha', 'beta']);
  expect(allOverview.getCell('E3').value).toBe('Operator B');

  const popupPromise = page.waitForEvent('popup');
  await page.getByRole('button', { name: 'PDF report', exact: true }).click();
  const report = await popupPromise;
  await expect(report.getByRole('heading', { name: 'Test report', exact: true })).toBeVisible();
  await expect(report.getByRole('heading', { name: 'alpha', exact: true })).toBeVisible();
  await expect(report.getByRole('heading', { name: 'beta', exact: true })).toHaveCount(0);
  await expect(report.getByRole('cell', { name: '<script>test</script>', exact: true })).toBeVisible();
  expect(await report.locator('script').count()).toBe(0);
  await expect(report.locator('svg, figure')).toHaveCount(0);
  await expect(report.getByRole('heading', { name: 'Signals', exact: true })).toHaveCount(0);
  await report.pdf({ path: test.info().outputPath('selected-test-report.pdf'), preferCSSPageSize: true, printBackground: true });
  await report.close();

  await page.getByRole('button', { name: 'PDF report options', exact: true }).click();
  const allPopupPromise = page.waitForEvent('popup');
  await page.getByRole('menuitem', { name: 'PDF: all tests in this serial', exact: true }).click();
  const allReport = await allPopupPromise;
  await expect(allReport.getByRole('heading', { name: 'beta', exact: true })).toBeVisible();
  await expect(allReport.locator('svg, figure')).toHaveCount(0);
  await expect(allReport.getByRole('heading', { name: 'Signals', exact: true })).toHaveCount(0);
  await allReport.pdf({ path: test.info().outputPath('all-tests-report.pdf'), preferCSSPageSize: true, printBackground: true });
  await allReport.close();
  await page.getByRole('button', { name: 'beta', exact: true }).click();
  await expect(page.getByRole('cell', { name: 'Beta result', exact: true })).toBeVisible();
  const requestsBeforeBetaPlot = apiRequests.length;
  await page.getByRole('button', { name: 'Plot signals', exact: true }).click();
  const betaDialog = page.getByRole('dialog', { name: 'Signals for beta' });
  await expect(betaDialog.getByRole('button', { name: 'beta-signal', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(betaDialog.getByLabel('Visible time range')).toHaveText('Time: 0–0.001 s');
  await expect(betaDialog.getByRole('button', { name: 'pressure', exact: true })).toHaveCount(0);
  expect(apiRequests).toHaveLength(requestsBeforeBetaPlot);
  await betaDialog.getByRole('button', { name: 'Close', exact: true }).click();
  await page.screenshot({ path: test.info().outputPath('toolbar-desktop.png'), fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  await page.screenshot({ path: test.info().outputPath('toolbar-mobile.png'), fullPage: true });
});

test('measures two samples on one signal and keeps movable points aligned with the chart', async ({ page }) => {
  const curve = Array.from({ length: 11 }, (_, index) => index ** 2);
  await page.route('**/backend/api/**', async (route) => {
    const path = new URL(route.request().url()).pathname;
    const respond = (data: unknown) => route.fulfill({ status: 200, json: data });
    if (path.endsWith('/auth/me/')) return respond({ id: 1, username: 'tester', is_superuser: true, permissions: [] });
    if (path.endsWith('/measurement-batches/batch/')) return respond({
      id: 'batch', created_at: '2026-11-22T07:00:00Z', devices: [{
        id: 'serial', serial_number: 'SN-001', device_type: 'device', device_type_name: 'Device one',
        tests: [{ id: 'curve-test', test: 'curve-test', test_name: 'Curve test', executed_at: '2026-11-20T07:00:00Z', sample_rate_hz: 10 }],
      }],
    });
    if (path.endsWith('/test-runs/curve-test/')) return respond({ id: 'curve-test', flat_result_data: null });
    if (path.endsWith('/test-runs/curve-test/signals/')) return respond([
      { id: 'curve', name: 'Curve', sample_count: 11 }, { id: 'other', name: 'Other', sample_count: 11 },
      { id: 'voltage', name: 'voltage_v', sample_count: 11 }, { id: 'temperature', name: 'temperature_c', sample_count: 11 },
    ]);
    if (path.endsWith('/signals/curve/')) return respond({ id: 'curve', name: 'Curve', samples: curve });
    if (path.endsWith('/signals/other/')) return respond({ id: 'other', name: 'Other', samples: curve.map(() => 120) });
    if (path.endsWith('/signals/voltage/')) return respond({ id: 'voltage', name: 'voltage_v', samples: curve.map(() => 110) });
    if (path.endsWith('/signals/temperature/')) return respond({ id: 'temperature', name: 'temperature_c', samples: curve.map(() => 100) });
    return route.fulfill({ status: 404, json: {} });
  });
  await page.goto('/serial-batches/batch/serials/serial');
  await page.getByRole('button', { name: 'Plot signals', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: 'Signals for Curve test' });
  const plot = dialog.getByRole('img', { name: 'Signal chart', exact: true });
  await expect(plot.locator('canvas')).toBeVisible({ timeout: 30_000 });
  let bounds = (await plot.boundingBox())!;
  const xAt = (time: number) => bounds.x + 84 + (bounds.width - 108) * time;
  const yAt = (value: number) => bounds.y + 60 + (127.2 - value) / 134.4 * (bounds.height - 116);
  const measure = dialog.getByRole('region', { name: 'Signal measurement', exact: true });
  const pointA = dialog.getByRole('slider', { name: 'Measurement point A', exact: true });
  const pointB = dialog.getByRole('slider', { name: 'Measurement point B', exact: true });
  const shiftClick = async (time: number, value: number, signal = 'Curve') => {
    await page.mouse.move(xAt(time), yAt(value));
    await expect(dialog.getByRole('tooltip', { name: 'Signal coordinates' }).getByText(signal, { exact: true })).toBeVisible();
    await page.keyboard.down('Shift');
    await page.mouse.click(xAt(time), yAt(value));
    await page.keyboard.up('Shift');
  };

  // Empty space does not start an accidental zoom or measurement with Shift held.
  await page.keyboard.down('Shift');
  await page.mouse.click(xAt(0.5), yAt(80));
  await page.keyboard.up('Shift');
  await expect(measure).toHaveCount(0);
  await shiftClick(0.2, 4);
  await expect(measure.getByLabel('Point A', { exact: true })).toHaveText('A: 0.2 s · 4');
  await expect(pointB).toHaveCount(0);
  await shiftClick(0.8, 120, 'Other');
  await expect(pointB).toHaveCount(0);
  await expect(measure.getByText(/Shift|Drag|Esc/)).toHaveCount(0);
  await shiftClick(0.8, 64);
  await expect(measure.getByLabel('Point B', { exact: true })).toHaveText('B: 0.8 s · 64');
  await expect(measure.getByLabel('Time difference', { exact: true })).toHaveText('0.6 s');
  await expect(measure.getByLabel('Value difference', { exact: true })).toHaveText('60');
  await expect(measure.getByLabel('Average slope', { exact: true })).toHaveText('100 value/s');
  await expect(dialog.getByLabel('Visible time range')).toHaveText('Time: 0–1 s');

  // Dragging an endpoint snaps to original samples and updates the average slope.
  const handleB = (await pointB.boundingBox())!;
  await page.mouse.move(handleB.x + handleB.width / 2, handleB.y + handleB.height / 2);
  await page.mouse.down();
  await page.mouse.move(xAt(0.6), yAt(36), { steps: 8 });
  await page.mouse.up();
  await expect(measure.getByLabel('Point B', { exact: true })).toHaveText('B: 0.6 s · 36');
  await expect(measure.getByLabel('Time difference', { exact: true })).toHaveText('0.4 s');
  await expect(measure.getByLabel('Value difference', { exact: true })).toHaveText('32');
  await expect(measure.getByLabel('Average slope', { exact: true })).toHaveText('80 value/s');
  await expect(dialog.getByLabel('Visible time range')).toHaveText('Time: 0–1 s');

  // Zooming, panning and resetting move the markers without changing measured samples.
  const beforeZoom = (await pointA.boundingBox())!;
  await page.mouse.move(xAt(0.5), yAt(70));
  await page.mouse.wheel(0, -100);
  await expect(dialog.getByLabel('Visible time range')).not.toHaveText('Time: 0–1 s');
  await expect.poll(async () => (await pointA.boundingBox())?.x).not.toBe(beforeZoom.x);
  await page.mouse.down({ button: 'right' });
  await page.mouse.move(xAt(0.5) + 20, yAt(70), { steps: 5 });
  await page.mouse.up({ button: 'right' });
  await expect(measure.getByLabel('Point A', { exact: true })).toHaveText('A: 0.2 s · 4');
  await expect(measure.getByLabel('Average slope', { exact: true })).toHaveText('80 value/s');
  await plot.dblclick({ position: { x: bounds.width / 2, y: bounds.height / 2 } });
  await expect(dialog.getByLabel('Visible time range')).toHaveText('Time: 0–1 s');
  await expect(pointA).toHaveAttribute('aria-valuenow', '2');
  await expect(pointB).toHaveAttribute('aria-valuenow', '6');
  await page.screenshot({ path: test.info().outputPath('signal-measurement.png') });
  await page.setViewportSize({ width: 390, height: 844 });
  bounds = (await plot.boundingBox())!;
  await expect.poll(async () => {
    const point = (await pointB.boundingBox())!;
    return Math.abs(point.x + point.width / 2 - xAt(0.6));
  }).toBeLessThan(1);
  const legendBounds = (await dialog.getByRole('group', { name: 'Signals', exact: true }).boundingBox())!;
  expect(legendBounds.height).toBeGreaterThan(28);
  await expect(dialog.getByRole('button', { name: 'voltage_v', exact: true })).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'temperature_c', exact: true })).toBeVisible();
  await expect.poll(async () => {
    const point = (await pointB.boundingBox())!;
    const top = Math.max(60, legendBounds.height + 24);
    const expected = bounds.y + top + (127.2 - 36) / 134.4 * (bounds.height - top - 56);
    return Math.abs(point.y + point.height / 2 - expected);
  }).toBeLessThan(1);
  await expect.poll(() => dialog.evaluate((element) => element.scrollWidth <= element.clientWidth)).toBeTruthy();
  await page.screenshot({ path: test.info().outputPath('signal-measurement-mobile.png') });

  // Both points may coincide: a zero time difference must never yield Infinity/NaN.
  await pointB.focus();
  for (let step = 0; step < 4; step += 1) await page.keyboard.press('ArrowLeft');
  await expect(measure.getByLabel('Time difference', { exact: true })).toHaveText('0 s');
  await expect(measure.getByLabel('Value difference', { exact: true })).toHaveText('0');
  await expect(measure.getByLabel('Average slope', { exact: true })).toHaveText('Undefined (Δt = 0)');
  await page.keyboard.press('Escape');
  await expect(measure).toHaveCount(0);
  await expect(dialog).toBeVisible();

  await page.setViewportSize({ width: 1280, height: 720 });
  bounds = (await plot.boundingBox())!;
  await expect(plot.locator('canvas')).toHaveCSS('width', `${bounds.width}px`);
  await shiftClick(0.8, 64);
  await shiftClick(0.2, 4);
  await expect(measure.getByLabel('Time difference', { exact: true })).toHaveText('-0.6 s');
  await expect(measure.getByLabel('Value difference', { exact: true })).toHaveText('-60');
  await expect(measure.getByLabel('Average slope', { exact: true })).toHaveText('100 value/s');
  await dialog.getByRole('button', { name: 'Curve', exact: true }).click();
  await expect(measure).toHaveCount(0);
  await page.keyboard.press('Escape');
  await expect(dialog).toBeHidden();
});
