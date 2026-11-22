import { escapeHtml, signalSvg } from './signalChart';
import { type TestReport, testMetadata } from './testReport';
import { formatTehranDateTime } from './dateTime';

/** The browser prints the same Unicode HTML report shown in the preview. */
export function reportHtml(report: TestReport) {
  const tests = report.tests.map((test) => {
    const table = test.detail.flat_result_data;
    let parameters = '<p class="muted">No parameter table stored.</p>';
    if (table && table.column_count > 0) {
      const width = table.column_count;
      if (width !== table.columns.length || table.flattened_rows.length % width) throw new Error('The result table has incomplete rows or columns.');
      const groups: number[][] = [];
      for (let start = 0; start < width; start += start === 0 ? 12 : 11) {
        const indices = Array.from({ length: Math.min(start === 0 ? 12 : 11, width - start) }, (_, i) => start + i);
        groups.push(start ? [0, ...indices] : indices);
      }
      parameters = groups.map((columns, group) => `<div class="parameter-group">${group ? '<h4>Parameters (continued)</h4>' : ''}
        <table><thead><tr>${columns.map((index) => `<th>${escapeHtml(table.columns[index])}</th>`).join('')}</tr></thead><tbody>${
          Array.from({ length: table.flattened_rows.length / width }, (_, row) => `<tr>${columns.map((column) => `<td>${escapeHtml(table.flattened_rows[row * width + column])}</td>`).join('')}</tr>`).join('')
        }</tbody></table></div>`).join('');
    } else if (table && (table.columns.length || table.flattened_rows.length)) {
      throw new Error('The result table has incomplete rows or columns.');
    }
    return `<section class="test"><div class="test-heading"><h2>${escapeHtml(test.run.test_name)}</h2><span>${escapeHtml(formatTehranDateTime(test.run.executed_at))} (Tehran)</span></div>
      <dl>${testMetadata(report, test).map(([key, value]) => `<div><dt>${escapeHtml(key)}</dt><dd>${escapeHtml(value || '-')}</dd></div>`).join('')}</dl>
      <h3>Parameters</h3>${parameters}<h3>Signals</h3>
      ${test.signals.length ? test.signals.map((signal) => `<figure><figcaption><strong>${escapeHtml(signal.name)}</strong><span>${signal.samples.length.toLocaleString('en-US')} samples</span></figcaption>${signalSvg(signal.name, signal.samples)}</figure>`).join('') : '<p class="muted">No signals stored.</p>'}
    </section>`;
  }).join('');
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>${escapeHtml(report.serialNumber)} - Test report</title><style>
    *{box-sizing:border-box}body{margin:0;background:#eef2f7;color:#1d2939;font:13px Arial,sans-serif}
    .tools{position:sticky;top:0;background:#fff;border-bottom:1px solid #dbe3ef;padding:14px 24px;display:flex;align-items:center;justify-content:space-between;gap:16px}
    button{background:#1677ff;color:white;border:0;border-radius:6px;padding:10px 18px;font:inherit;cursor:pointer}
    main{max-width:1120px;margin:24px auto;background:white;padding:36px}h1{font-size:24px;margin:0 0 8px}h2{font-size:20px;margin:0}h3{font-size:15px;margin:24px 0 12px}h4{margin:16px 0 8px}
    .report-heading{border-bottom:2px solid #1677ff;padding-bottom:20px;margin-bottom:24px}.muted{color:#667085}.report-heading p{margin:5px 0}
    .test+.test{break-before:page;margin-top:36px}.test-heading{display:flex;justify-content:space-between;align-items:center;gap:16px}
    .test-heading span{color:#667085;font-size:12px}dl{display:grid;grid-template-columns:1fr 1fr;gap:0 24px;margin:16px 0}
    dl>div{display:grid;grid-template-columns:160px 1fr;padding:7px 0;border-bottom:1px solid #edf0f5;gap:12px;break-inside:avoid}dt{color:#667085}dd{margin:0;overflow-wrap:anywhere}
    table{width:100%;border-collapse:collapse;table-layout:fixed;font-size:10px}th,td{padding:7px 5px;border:1px solid #e4eaf2;text-align:left;overflow-wrap:anywhere;vertical-align:top}th{background:#edf4ff;color:#234e89}thead{display:table-header-group}tr{break-inside:avoid}
    figure{margin:16px 0 24px;padding:14px;border:1px solid #e4eaf2;border-radius:8px;break-inside:avoid}figcaption{display:flex;justify-content:space-between;gap:16px;margin-bottom:8px}figcaption span{color:#667085;font-size:12px}svg{max-height:240px}
    @page{size:A4 landscape;margin:12mm}
    @media print{body{background:white;font-size:10px}.tools{display:none}main{max-width:none;padding:0;margin:0}.test+.test{margin-top:0}h1{font-size:20px}h2{font-size:17px}h3{margin-top:18px}dl>div{padding:5px 0}table{font-size:8px}th,td{padding:5px 4px}figure{padding:10px;margin:12px 0 18px}svg{max-height:190px}.report-heading{margin-bottom:18px;padding-bottom:14px}}
    @media screen and (max-width:700px){main{padding:18px;margin:12px}dl{grid-template-columns:1fr}.tools{flex-wrap:wrap}.test-heading{align-items:flex-start;flex-direction:column}}
    </style></head><body><div class="tools"><span>Test report · Choose <strong>Save as PDF</strong> in the print dialog.</span><button id="save-pdf" type="button">Print / Save as PDF</button></div>
    <main><header class="report-heading"><h1>Test report</h1><p><strong>${escapeHtml(report.serialNumber)}</strong> · ${escapeHtml(report.deviceType)}</p><p class="muted">${report.tests.length} test${report.tests.length === 1 ? '' : 's'} · Parameters and signal charts</p></header>${tests}</main></body></html>`;
}

export async function showPdfReport(target: Window, report: TestReport) {
  const html = reportHtml(report);
  target.document.open();
  target.document.write(html);
  target.document.close();
  target.document.getElementById('save-pdf')?.addEventListener('click', () => target.print());
  await target.document.fonts.ready;
  target.focus();
  // Keep the preview open so the report can be printed again after cancelling.
  target.setTimeout(() => { if (!target.closed) target.print(); }, 300);
}
