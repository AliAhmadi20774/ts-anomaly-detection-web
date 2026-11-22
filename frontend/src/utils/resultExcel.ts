import type { FlatResultData } from '@/services/testRuns';
import type { Workbook, Worksheet } from 'exceljs';
import { type TestReport, testMetadata } from './testReport';

/** Build a workbook from the complete table already loaded by the UI. */
export async function resultExcel(table: FlatResultData): Promise<Blob> {
  const { default: ExcelJS } = await import('exceljs');
  const workbook = new ExcelJS.Workbook();
  addParameters(workbook, 'Results', table);
  return workbookBlob(workbook);
}

function addParameters(workbook: Workbook, name: string, table: FlatResultData) {
  const width = table.column_count;
  const cells = table.flattened_rows;
  if (!Number.isInteger(width) || width <= 0 || table.columns.length !== width
    || cells.length === 0 || cells.length % width !== 0) {
    throw new Error('This test has no complete result table to export.');
  }
  const rowCount = cells.length / width;
  if (width > 16384 || rowCount > 1048575) {
    throw new Error('The complete table exceeds the Excel worksheet size limit.');
  }
  if (table.columns.some((value) => value.length > 32767) || cells.some((value) => value.length > 32767)) {
    throw new Error('A table value exceeds the Excel cell text limit.');
  }

  const sheet = workbook.addWorksheet(name, {
    views: [{ state: 'frozen', ySplit: 1, showGridLines: false }],
  });
  sheet.addRow(table.columns);
  for (let index = 0; index < cells.length; index += width) {
    // Every DAT value is a string, including leading zeros and formula-like text.
    sheet.addRow(cells.slice(index, index + width));
  }
  sheet.columns.forEach((column, index) => {
    let longest = table.columns[index].length;
    for (let cell = index; cell < cells.length; cell += width) {
      longest = Math.max(longest, cells[cell].length);
    }
    column.width = Math.min(60, Math.max(12, longest + 2));
    column.alignment = { vertical: 'top', wrapText: true };
  });
  const header = sheet.getRow(1);
  header.height = 30;
  header.eachCell((cell) => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1677FF' } };
  });
  sheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: rowCount + 1, column: width } };
}

function styleSheet(sheet: Worksheet) {
  sheet.views = [{ state: 'frozen', ySplit: 1, showGridLines: false }];
  sheet.columns.forEach((column) => {
    let longest = 10;
    column.eachCell?.((cell) => {
      const length = String(cell.value ?? '').length;
      if (length > 32767) throw new Error('A value exceeds the Excel cell text limit.');
      longest = Math.max(longest, length);
    });
    column.width = Math.min(60, longest + 2);
    column.alignment = { vertical: 'top', wrapText: true };
  });
  sheet.getRow(1).height = 30;
  sheet.getRow(1).eachCell((cell) => {
    cell.font = { bold: true, color: { argb: 'FFFFFFFF' } };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1677FF' } };
  });
  sheet.autoFilter = { from: { row: 1, column: 1 }, to: { row: sheet.rowCount, column: sheet.columnCount } };
}

async function workbookBlob(workbook: Workbook) {
  return new Blob([new Uint8Array(await workbook.xlsx.writeBuffer())], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
}

/** Export original parameters and every raw sample, without chart downsampling. */
export async function completeExcel(report: TestReport): Promise<Blob> {
  const { default: ExcelJS } = await import('exceljs');
  const workbook = new ExcelJS.Workbook();
  const overview = workbook.addWorksheet('Overview');
  overview.addRow(['Test', 'Property', 'Value']);
  for (const [index, test] of report.tests.entries()) {
    testMetadata(report, test).forEach(([key, value]) => overview.addRow([test.run.test_name, key, value]));
    test.signals.forEach((signal) => overview.addRow([test.run.test_name, `Samples: ${signal.name}`, signal.samples.length]));
    const table = test.detail.flat_result_data;
    if (table && (table.columns.length || table.flattened_rows.length)) {
      if (table.flattened_rows.length) addParameters(workbook, `${index + 1} Parameters`, table);
      else if (table.column_count !== table.columns.length) throw new Error('Invalid parameter table.');
      else {
        const empty = workbook.addWorksheet(`${index + 1} Parameters`);
        empty.addRow(table.columns);
        styleSheet(empty);
      }
    }
    if (test.signals.length > 16383) throw new Error('There are too many signals for one Excel worksheet.');
    const sampleCount = Math.max(0, ...test.signals.map((signal) => signal.samples.length));
    // Split very long recordings across worksheets, keeping absolute sample indices.
    const sheetCount = Math.max(1, Math.ceil(sampleCount / 1048575));
    for (let part = 0; part < sheetCount; part += 1) {
      const sheet = workbook.addWorksheet(`${index + 1} Signals${part ? ` ${part + 1}` : ''}`);
      sheet.addRow(['Sample index', ...test.signals.map((signal) => signal.name)]);
      const start = part * 1048575;
      const end = Math.min(sampleCount, start + 1048575);
      for (let sample = start; sample < end; sample += 1) {
        sheet.addRow([sample, ...test.signals.map((signal) => signal.samples[sample] ?? null)]);
      }
      styleSheet(sheet);
    }
  }
  styleSheet(overview);
  return workbookBlob(workbook);
}
