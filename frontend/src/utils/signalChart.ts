export function escapeHtml(value: string | number) {
  return String(value).replace(/[&<>"']/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]!);
}

/** Bucket extrema preserve short peaks that a fixed sample stride would miss. */
export function signalPoints(samples: number[], start = 0, end = samples.length - 1, buckets = 600) {
  const points: { sample: number; value: number }[] = [];
  const stride = Math.max(1, Math.ceil((end - start + 1) / buckets));
  for (let offset = start; offset <= end; offset += stride) {
    let low = offset;
    let high = offset;
    for (let index = offset + 1; index <= Math.min(end, offset + stride - 1); index += 1) {
      if (samples[index] < samples[low]) low = index;
      if (samples[index] > samples[high]) high = index;
    }
    for (const index of low === high ? [low] : [low, high].sort((a, b) => a - b)) {
      points.push({ sample: index, value: samples[index] });
    }
  }
  if (points[0]?.sample !== start && samples.length) points.unshift({ sample: start, value: samples[start] });
  if (points.at(-1)?.sample !== end && samples.length) points.push({ sample: end, value: samples[end] });
  return points;
}

export function signalSvg(name: string, samples: number[], start = 0, end = samples.length - 1) {
  if (!samples.length) return '<p>No samples stored.</p>';
  const points = signalPoints(samples, start, end);
  let low = Infinity;
  let high = -Infinity;
  points.forEach(({ value }) => { low = Math.min(low, value); high = Math.max(high, value); });
  const padding = (high - low || Math.abs(high) || 1) * 0.08;
  low -= padding;
  high += padding;
  const x = (sample: number) => 88 + ((sample - start) / (end - start || 1)) * 890;
  const y = (value: number) => 218 - ((value - low) / (high - low)) * 196;
  const format = (value: number) => Math.abs(value) >= 1e7 || (value !== 0 && Math.abs(value) < 0.0001)
    ? value.toExponential(3) : Number(value.toPrecision(5)).toLocaleString('en-US', { maximumFractionDigits: 6 });
  const horizontal = Array.from({ length: 5 }, (_, index) => {
    const value = low + ((high - low) * index) / 4;
    return `<line x1="88" x2="978" y1="${y(value)}" y2="${y(value)}" stroke="#e7edf5"/><text x="78" y="${y(value) + 4}" text-anchor="end">${format(value)}</text>`;
  }).join('');
  const tickSamples = [...new Set(Array.from({ length: 5 }, (_, index) => Math.round(start + ((end - start) * index) / 4)))];
  const ticks = tickSamples.map((sample) => `<text x="${x(sample)}" y="240" text-anchor="middle">${sample}</text>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${escapeHtml(name)} signal chart" viewBox="0 0 1000 270" width="100%" style="display:block;font:12px Arial,sans-serif;color:#667085" fill="#667085">
    <title>${escapeHtml(name)}</title>${horizontal}
    <line x1="88" x2="978" y1="218" y2="218" stroke="#cbd5e1"/>
    <polyline points="${points.map((point) => `${x(point.sample).toFixed(2)},${y(point.value).toFixed(2)}`).join(' ')}" stroke="#1677ff" fill="none" stroke-width="1.4" stroke-linejoin="round"/>
    ${points.length === 1 ? `<circle cx="${x(points[0].sample)}" cy="${y(points[0].value)}" r="3" fill="#1677ff"/>` : ''}
    ${ticks}<text x="533" y="264" text-anchor="middle">Sample index</text></svg>`;
}
