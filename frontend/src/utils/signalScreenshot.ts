import type { EChartsType } from 'echarts/core';

/** Export the current canvas, vector drawings, measurements and legend without interactive controls. */
export async function signalScreenshot(chart: EChartsType, workspace: HTMLElement): Promise<Blob> {
  const width = chart.getWidth();
  const height = chart.getHeight();
  const origin = workspace.getBoundingClientRect();
  const canvas = document.createElement('canvas');
  canvas.width = width * 2;
  canvas.height = height * 2;
  const context = canvas.getContext('2d');
  if (!context) throw new Error('Could not create screenshot.');
  context.drawImage(chart.renderToCanvas({ backgroundColor: '#fff', pixelRatio: 2 }), 0, 0);
  context.scale(2, 2);
  const rect = (element: Element) => {
    const box = element.getBoundingClientRect();
    return { x: box.left - origin.left, y: box.top - origin.top, width: box.width, height: box.height };
  };
  const text = (element: Element) => {
    const style = getComputedStyle(element);
    return { ...rect(element), value: element.textContent ?? '', font: style.font, color: style.color };
  };
  // Snapshot geometry before awaiting image decoding so exports remain consistent during interaction.
  const vectors = [...workspace.querySelectorAll<SVGSVGElement>('.signal-annotation-overlay, .signal-measurement-overlay')].map((element) => {
    const copy = element.cloneNode(true) as SVGSVGElement;
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    copy.setAttribute('width', String(width));
    copy.setAttribute('height', String(height));
    return new XMLSerializer().serializeToString(copy);
  });
  const title = workspace.querySelector('.signal-test-name');
  const labels = [...workspace.querySelectorAll('.signal-toggle:not(.signal-toggle-all)')].map((element) => ({
    label: text(element.lastElementChild!), swatch: rect(element.firstElementChild!),
    color: getComputedStyle(element.firstElementChild!).backgroundColor, active: element.getAttribute('aria-pressed') === 'true',
  }));
  const readout = workspace.querySelector('.signal-measurement-readout');
  const card = readout ? { ...rect(readout), labels: [...readout.querySelectorAll('strong, [aria-label="Point A"], [aria-label="Point B"], dt, dd')].map(text) } : undefined;
  const timeRange = workspace.querySelector('.signal-time-range');
  const captions = [title, timeRange].filter((element): element is Element => Boolean(element)).map(text);
  for (const vector of vectors) {
    const url = URL.createObjectURL(new Blob([vector], { type: 'image/svg+xml;charset=utf-8' }));
    try {
      const image = new Image();
      await new Promise<void>((resolve, reject) => { image.onload = () => resolve(); image.onerror = () => reject(new Error('Could not render drawings.')); image.src = url; });
      context.drawImage(image, 0, 0, width, height);
    } finally { URL.revokeObjectURL(url); }
  }
  const drawText = (label: ReturnType<typeof text>) => {
    context.font = label.font || '12px sans-serif';
    context.fillStyle = label.color;
    context.textBaseline = 'middle';
    context.fillText(label.value, label.x, label.y + label.height / 2);
  };
  captions.forEach(drawText);
  labels.forEach(({ label, swatch, color, active }) => {
    context.fillStyle = color;
    context.fillRect(swatch.x, swatch.y, swatch.width, swatch.height);
    drawText(label);
    if (!active) { context.fillRect(label.x, label.y + label.height / 2, label.width, 1); }
  });
  if (card) {
    context.fillStyle = '#fffffff2';
    context.strokeStyle = '#d5e5ff';
    context.beginPath();
    context.roundRect(card.x, card.y, card.width, card.height, 8);
    context.fill();
    context.stroke();
    card.labels.forEach(drawText);
  }
  return new Promise<Blob>((resolve, reject) => canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('Could not save screenshot.')), 'image/png'));
}
