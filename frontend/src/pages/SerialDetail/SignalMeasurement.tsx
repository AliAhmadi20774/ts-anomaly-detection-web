import type { EChartsType } from 'echarts/core';
import { useId, useMemo } from 'react';
import type { SignalTraceData } from '@/services/testRuns';

export type Measurement = { signalId: string; a: number; b?: number };
export type Endpoint = 'a' | 'b';
const number = (value: number) => Number(value.toPrecision(8)).toString();

export default function SignalMeasurement({ measurement, signal, sampleRate, chart, grid, revision, onPointChange }: {
  measurement: Measurement;
  signal: SignalTraceData & { color: string };
  sampleRate: number;
  chart: EChartsType;
  grid: { left: number; right: number; top: number; bottom: number };
  revision: number;
  onPointChange: (endpoint: Endpoint, sample: number) => void;
}) {
  const clipId = useId().replace(/:/g, '');
  const geometry = useMemo(() => {
    const project = (sample: number) => chart.convertToPixel({ gridIndex: 0 }, [sample / sampleRate, signal.samples[sample]]) as number[];
    return { a: project(measurement.a), b: measurement.b === undefined ? undefined : project(measurement.b),
      width: chart.getWidth() - grid.left - grid.right, height: chart.getHeight() - grid.top - grid.bottom };
  }, [chart, measurement, sampleRate, signal, grid, revision]);
  const deltaTime = measurement.b === undefined ? undefined : (measurement.b - measurement.a) / sampleRate;
  const deltaValue = measurement.b === undefined ? undefined : signal.samples[measurement.b] - signal.samples[measurement.a];
  const coordinate = (sample: number) => `${number(sample / sampleRate)} s · ${number(signal.samples[sample])}`;

  return <>
    <svg className="signal-measurement-overlay" aria-label="Measurement markers" role="group">
      <defs><clipPath id={clipId}><rect x={grid.left} y={grid.top} width={Math.max(0, geometry.width)} height={Math.max(0, geometry.height)} /></clipPath></defs>
      <g clipPath={`url(#${clipId})`}>
        {geometry.b && <line x1={geometry.a[0]} y1={geometry.a[1]} x2={geometry.b[0]} y2={geometry.b[1]}
          stroke={signal.color} strokeWidth={1.5} strokeDasharray="6 4" />}
        {(['a', 'b'] as const).map((endpoint) => {
          const position = geometry[endpoint];
          const sample = measurement[endpoint];
          if (!position || sample === undefined || !chart.containPixel({ gridIndex: 0 }, position)) return null;
          return <g key={endpoint}>
            <circle cx={position[0]} cy={position[1]} r={7} fill="#fff" stroke={signal.color} strokeWidth={2.5}
              data-measurement-point={endpoint} role="slider" tabIndex={0} aria-label={`Measurement point ${endpoint.toUpperCase()}`}
              aria-valuemin={0} aria-valuemax={signal.samples.length - 1} aria-valuenow={sample} aria-valuetext={coordinate(sample)}
              onKeyDown={(event) => {
                if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
                event.preventDefault();
                event.stopPropagation();
                onPointChange(endpoint, sample + (event.key === 'ArrowRight' ? 1 : -1) * (event.shiftKey ? 10 : 1));
              }} />
            <text x={position[0] + 11} y={position[1] - 11} fill={signal.color} fontSize={13} fontWeight={700}
              stroke="#fff" strokeWidth={3} paintOrder="stroke">{endpoint.toUpperCase()}</text>
          </g>;
        })}
      </g>
    </svg>
    <section className="signal-measurement-readout" style={{ top: grid.top + 12 }} aria-label="Signal measurement">
      <strong style={{ color: signal.color }}>{signal.name}</strong>
      <div aria-label="Point A">A: {coordinate(measurement.a)}</div>
      {measurement.b !== undefined && <>
        <div aria-label="Point B">B: {coordinate(measurement.b)}</div>
        <dl>
          <div><dt>Δt</dt><dd aria-label="Time difference">{number(deltaTime!)} s</dd></div>
          <div><dt>Δy</dt><dd aria-label="Value difference">{number(deltaValue!)}</dd></div>
          <div><dt>Average slope</dt><dd aria-label="Average slope">{deltaTime === 0 ? 'Undefined (Δt = 0)' : `${number(deltaValue! / deltaTime!)} value/s`}</dd></div>
        </dl>
      </>}
    </section>
  </>;
}
