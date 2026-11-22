import type { FlatResultData } from '@/services/testRuns';

export async function resultExcel(table: FlatResultData): Promise<Blob> {
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

  const { default: ExcelJS } = await import('exceljs');
  const workbook = new ExcelJS.Workbook();
  const sheet = workbook.addWorksheet('Results', {
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
  return new Blob([new Uint8Array(await workbook.xlsx.writeBuffer())], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  });
}
