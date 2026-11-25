import { Alert, Empty, message } from 'antd';
import { LineChart, type LineSeriesOption } from 'echarts/charts';
import { DataZoomComponent, GridComponent } from 'echarts/components';
import { init, use, type EChartsType } from 'echarts/core';
import { CanvasRenderer } from 'echarts/renderers';
import { useCallback, useEffect, useMemo, useRef, useState, type PointerEvent } from 'react';
import type { SignalTraceData } from '@/services/testRuns';
import { signalPoints } from '@/utils/signalChart';
import { signalScreenshot } from '@/utils/signalScreenshot';
import { downloadFile } from '@/utils/testReport';
import { SignalDrawingOverlay, SignalDrawingTools, useSignalDrawing } from './SignalDrawing';
import SignalMeasurement, { type Endpoint, type Measurement } from './SignalMeasurement';
import useHorizontalPan from './useHorizontalPan';

use([LineChart, GridComponent, DataZoomComponent, CanvasRenderer]);

const colors = ['#1677ff', '#d97706', '#0f9d83', '#a855f7', '#e54865', '#0891b2', '#64748b', '#8b6f00'];
const number = (value: number) => Number(value.toPrecision(8)).toString();
type Zoom = { id?: string; start?: number; end?: number };
type Selection = { x: number; y: number; endX: number; endY: number };
type Drag = Selection & ({ kind: 'select' | 'pan'; time: [number, number]; value: [number, number] }
  | { kind: 'measurement'; endpoint: Endpoint } | { kind: 'drawing' });
type SamplePoint = { signalId: string; sample: number };
const defaultGrid = { left: 84, right: 24, top: 60, bottom: 56 };
const shiftedWindow = ([start, end]: [number, number], delta: number) => {
  const next = Math.max(0, Math.min(100 - (end - start), start + delta));
  return { start: next, end: next + end - start };
};
const zoomedWindow = ([start, end]: [number, number], factor: number, anchor: number, minimum: number) => {
  const span = end - start;
  const nextSpan = Math.max(minimum, Math.min(100, span * factor));
  if (nextSpan >= 100 - 1e-9) return { start: 0, end: 100 };
  const nextStart = Math.max(0, Math.min(100 - nextSpan, start + (span - nextSpan) * anchor));
  return { start: nextStart, end: nextStart + nextSpan };
};

function nearestSample(chart: EChartsType, signal: SignalTraceData, sampleRate: number, x: number, y: number, clamp = false) {
  let [time, value] = chart.convertFromPixel({ gridIndex: 0 }, [x, y]) as number[];
  const end = (signal.samples.length - 1) / sampleRate;
  if (!clamp && (time < 0 || time > end)) return undefined;
  const [nextTime, nextValue] = chart.convertFromPixel({ gridIndex: 0 }, [x + 1, y + 1]) as number[];
  const timePerPixel = nextTime - time;
  const valuePerPixel = nextValue - value;
  time = Math.max(0, Math.min(end, time));
  // Snap to an original sample near the line, including peaks narrower than a pixel.
  const first = Math.max(0, Math.floor((time - 6 * timePerPixel) * sampleRate));
  const last = Math.min(signal.samples.length - 1, Math.ceil((time + 6 * timePerPixel) * sampleRate));
  let sample = first;
  let distance = Infinity;
  for (let index = first; index <= last; index += 1) {
    const candidate = ((index / sampleRate - time) / timePerPixel) ** 2
      + ((signal.samples[index] - value) / valuePerPixel) ** 2;
    if (candidate < distance) { distance = candidate; sample = index; }
  }
  return sample;
}

export default function SignalGraphs({ signals, sampleRate, testName }: { signals: SignalTraceData[]; sampleRate: number; testName: string }) {
  const host = useRef<HTMLDivElement>(null);
  const legend = useRef<HTMLDivElement>(null);
  const grid = useRef({ ...defaultGrid }).current;
  const chart = useRef<EChartsType | null>(null);
  const timeWindowRef = useRef<[number, number]>([0, 100]);
  const horizontalPan = useHorizontalPan(chart, timeWindowRef);
  const workspace = useRef<HTMLDivElement>(null);
  const drawing = useSignalDrawing(chart, grid);
  const [capturing, setCapturing] = useState(false);
  const redraw = useRef<(resetValueZoom?: boolean) => void>(() => {});
  const [selected, setSelected] = useState(() => signals.filter((signal) => signal.samples.length).map((signal) => signal.id));
  const selectedRef = useRef(selected);
  const [panning, setPanning] = useState(false);
  const [selection, setSelection] = useState<Selection>();
  const [hovered, setHovered] = useState<SamplePoint>();
  const hoveredRef = useRef<SamplePoint | undefined>(undefined);
  const [measurement, setMeasurement] = useState<Measurement>();
  const measurementRef = useRef<Measurement | undefined>(undefined);
  const [viewRevision, setViewRevision] = useState(0);
  const drag = useRef<Drag | undefined>(undefined);
  const [timeWindow, setTimeWindow] = useState<[number, number]>([0, 100]);
  const validRate = Number.isFinite(sampleRate) && sampleRate > 0;
  const traces = useMemo(() => signals.map((signal, index) => {
    let min = Infinity;
    let max = -Infinity;
    for (const value of signal.samples) { min = Math.min(min, value); max = Math.max(max, value); }
    return { ...signal, min, max, color: colors[index % colors.length] };
  }), [signals]);
  const sampleCount = Math.max(0, ...signals.map((signal) => signal.samples.length));
  const duration = validRate ? Math.max(0, sampleCount - 1) / sampleRate : 0;
  const timeMax = validRate ? Math.max(duration, 1 / sampleRate) : 1;
  const updateHover = useCallback((next?: SamplePoint) => {
    hoveredRef.current = next;
    setHovered((current) => current?.signalId === next?.signalId && current?.sample === next?.sample ? current : next);
  }, []);
  const updateMeasurement = useCallback((next?: Measurement) => {
    measurementRef.current = next;
    setMeasurement(next);
  }, []);
  const cancelDrag = useCallback(() => {
    drag.current = undefined; setSelection(undefined); setPanning(false); drawing.cancel();
  }, [drawing.cancel]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || (!horizontalPan.activeRef.current && !measurementRef.current && drawing.modeRef.current === 'pointer' && !drawing.menuOpenRef.current)) return;
      event.preventDefault();
      event.stopPropagation();
      if (horizontalPan.activeRef.current) horizontalPan.stop();
      else if (drawing.menuOpenRef.current) drawing.setMenuOpen(false);
      else {
        cancelDrag();
        if (drawing.modeRef.current !== 'pointer') drawing.setMode('pointer');
        else updateMeasurement();
      }
      updateHover();
      host.current?.closest<HTMLElement>('[role="dialog"]')?.focus({ preventScroll: true });
    };
    document.addEventListener('keydown', onKeyDown, true);
    return () => document.removeEventListener('keydown', onKeyDown, true);
  }, [cancelDrag, updateMeasurement, updateHover, drawing.modeRef, drawing.menuOpenRef, drawing.setMenuOpen, drawing.setMode, horizontalPan.activeRef, horizontalPan.stop]);

  useEffect(() => {
    if (!host.current || !validRate || !sampleCount) return;
    const instance = init(host.current, undefined, { renderer: 'canvas' });
    chart.current = instance;
    timeWindowRef.current = [0, 100];
    setTimeWindow([0, 100]);
    horizontalPan.stop();
    let seriesIds: (string | undefined)[] = [];
    const currentTime = (): [number, number] => {
      const zooms = instance.getOption().dataZoom as Zoom[];
      const zoom = zooms.find((item) => item.id === 'time-inside');
      return [zoom?.start ?? 0, zoom?.end ?? 100];
    };
    const draw = (resetValueZoom = false) => {
      updateHover();
      const visible = traces.filter((signal) => selectedRef.current.includes(signal.id));
      const [start, end] = currentTime();
      const firstSample = Math.max(0, Math.floor(start / 100 * timeMax * sampleRate) - 1);
      const lastSample = Math.ceil(end / 100 * timeMax * sampleRate) + 1;
      let low = Infinity;
      let high = -Infinity;
      const series: LineSeriesOption[] = visible.map((signal) => {
        low = Math.min(low, signal.min);
        high = Math.max(high, signal.max);
        const last = Math.min(lastSample, signal.samples.length - 1);
        const data = firstSample <= last
          ? signalPoints(signal.samples, firstSample, last, Math.max(300, instance.getWidth()))
            .map((point) => [point.sample / sampleRate, point.value])
          : [];
        return { id: signal.id, name: signal.name, type: 'line', data, showSymbol: data.length === 1,
          triggerEvent: 'line',
          symbolSize: 6, smooth: false, animation: false, lineStyle: { width: 1.6, color: signal.color },
          itemStyle: { color: signal.color }, emphasis: { disabled: true }, clip: true };
      });
      if (!Number.isFinite(low)) { low = 0; high = 1; }
      const padding = (high - low || Math.abs(high) || 1) * 0.06;
      instance.setOption({
        yAxis: { min: low - padding, max: high + padding }, series,
        ...(resetValueZoom ? { dataZoom: [{ id: 'value-inside', start: 0, end: 100 }] } : {}),
      }, { replaceMerge: ['series'] });
      seriesIds = (instance.getOption().series as { id?: string }[]).map((series) => series?.id);
      setViewRevision((revision) => revision + 1);
    };
    grid.top = Math.max(defaultGrid.top, (legend.current?.getBoundingClientRect().height ?? 0) + 24);
    instance.setOption({
      animation: false,
      grid,
      xAxis: { type: 'value', name: 'Time (s)', nameLocation: 'middle', nameGap: 30, min: 0, max: timeMax,
        axisLabel: { formatter: number, hideOverlap: true }, splitLine: { lineStyle: { color: '#eef1f5' } } },
      yAxis: { type: 'value', name: 'Signal value', nameLocation: 'middle', nameGap: 64, scale: true, axisLabel: { formatter: number },
        splitLine: { lineStyle: { color: '#e8edf3' } } },
      dataZoom: [
        { id: 'time-inside', type: 'inside', xAxisIndex: 0, filterMode: 'none', minValueSpan: 1 / sampleRate,
          zoomOnMouseWheel: false, moveOnMouseMove: false, moveOnMouseWheel: false },
        { id: 'value-inside', type: 'inside', yAxisIndex: 0, filterMode: 'none', zoomOnMouseWheel: false,
          moveOnMouseMove: false, moveOnMouseWheel: false },
      ],
      series: [],
    });
    redraw.current = draw;
    draw();
    const onZoom = () => {
      const current = currentTime();
      timeWindowRef.current = current;
      setTimeWindow(current);
      draw();
    };
    instance.on('datazoom', onZoom);
    const viewport = host.current.parentElement!;
    const onWheel = (event: WheelEvent) => {
      const rect = viewport.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      if (!instance.containPixel({ gridIndex: 0 }, [x, y]) || !event.deltaY) return;
      event.preventDefault();
      event.stopPropagation();
      horizontalPan.stop();
      if (drag.current) return;
      // Normalize mouse/trackpad units and cap individual wheel bursts. Reciprocal
      // factors make equal scrolls in opposite directions restore the same view.
      const pixels = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? rect.height : 1);
      const factor = Math.exp(Math.max(-120, Math.min(120, pixels)) * 0.0015);
      const zooms = instance.getOption().dataZoom as Zoom[];
      const zoom = (id: string, anchor: number, minimum: number) => {
        const window = zooms.find((item) => item.id === id);
        return { dataZoomId: id, ...zoomedWindow([window?.start ?? 0, window?.end ?? 100], factor, anchor, minimum) };
      };
      instance.dispatchAction({ type: 'dataZoom', batch: [
        zoom('time-inside', (x - grid.left) / (instance.getWidth() - grid.left - grid.right), Math.min(100, 100 / Math.max(1, sampleCount - 1))),
        zoom('value-inside', 1 - (y - grid.top) / (instance.getHeight() - grid.top - grid.bottom), 0.0001),
      ] });
    };
    viewport.addEventListener('wheel', onWheel, { capture: true, passive: false });
    const clearHover = () => updateHover();
    const onHover = (parameters: unknown) => {
      const event = parameters as { seriesIndex?: number; event?: { offsetX: number; offsetY: number } };
      if (drag.current || horizontalPan.activeRef.current || event.seriesIndex == null || !event.event) return clearHover();
      const { offsetX: x, offsetY: y } = event.event;
      if (!instance.containPixel({ gridIndex: 0 }, [x, y])) return clearHover();
      const signal = traces.find((trace) => trace.id === seriesIds[event.seriesIndex!]);
      if (!signal || !selectedRef.current.includes(signal.id)) return clearHover();
      const sample = nearestSample(instance, signal, sampleRate, x, y);
      if (sample === undefined) return clearHover();
      updateHover({ signalId: signal.id, sample });
    };
    instance.on('mousemove', onHover);
    instance.on('mouseout', clearHover);
    instance.getZr().on('globalout', clearHover);
    const observer = new ResizeObserver(() => {
      horizontalPan.stop();
      grid.top = Math.max(defaultGrid.top, (legend.current?.getBoundingClientRect().height ?? 0) + 24);
      instance.resize();
      instance.setOption({ grid });
      draw();
    });
    observer.observe(host.current);
    if (legend.current) observer.observe(legend.current);
    return () => {
      viewport.removeEventListener('wheel', onWheel, true);
      observer.disconnect();
      instance.off('datazoom', onZoom);
      instance.off('mousemove', onHover);
      instance.off('mouseout', clearHover);
      instance.getZr().off('globalout', clearHover);
      instance.dispose();
      chart.current = null;
      redraw.current = () => {};
    };
  }, [traces, sampleRate, sampleCount, timeMax, validRate, updateHover, grid, horizontalPan.activeRef, horizontalPan.stop]);

  useEffect(() => {
    selectedRef.current = selected;
    if (measurementRef.current && !selected.includes(measurementRef.current.signalId)) updateMeasurement();
    redraw.current(true);
  }, [selected, updateMeasurement]);

  const changePoint = (endpoint: Endpoint, sample: number) => {
    const current = measurementRef.current;
    const signal = current && traces.find((trace) => trace.id === current.signalId);
    if (current && signal) updateMeasurement({ ...current, [endpoint]: Math.max(0, Math.min(signal.samples.length - 1, sample)) });
  };

  const reset = () => chart.current?.dispatchAction({ type: 'dataZoom', batch: [
    { dataZoomId: 'time-inside', start: 0, end: 100 }, { dataZoomId: 'value-inside', start: 0, end: 100 },
  ] });
  const point = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - rect.left, y: event.clientY - rect.top };
  };
  const beginSelection = (event: PointerEvent<HTMLDivElement>) => {
    if (!chart.current) return;
    if (horizontalPan.activeRef.current) {
      event.preventDefault(); event.stopPropagation(); horizontalPan.stop(); return;
    }
    if (event.button !== 0 && event.button !== 1 && event.button !== 2) return;
    const { x, y } = point(event);
    if (!chart.current.containPixel({ gridIndex: 0 }, [x, y])) return;
    event.preventDefault();
    event.stopPropagation();
    if (event.button === 1) {
      cancelDrag();
      updateHover();
      horizontalPan.start(x, y);
      return;
    }
    const endpoint = (event.target as Element).closest('[data-measurement-point]')?.getAttribute('data-measurement-point') as Endpoint | null;
    const current = measurementRef.current;
    if (event.button === 0 && event.shiftKey) {
      const candidate = endpoint && current ? { signalId: current.signalId, sample: current[endpoint]! } : hoveredRef.current;
      if (candidate) {
        if (!current || current.b !== undefined) updateMeasurement({ signalId: candidate.signalId, a: candidate.sample });
        else if (current.signalId === candidate.signalId) updateMeasurement({ ...current, b: candidate.sample });
      }
      updateHover();
      return;
    }
    event.currentTarget.setPointerCapture(event.pointerId);
    if (event.button === 0 && endpoint && current) {
      drag.current = { kind: 'measurement', endpoint, x, y, endX: x, endY: y };
      setPanning(true);
      updateHover();
      return;
    }
    if (event.button === 0 && drawing.modeRef.current !== 'pointer') {
      drag.current = { kind: 'drawing', x, y, endX: x, endY: y };
      drawing.start(x, y);
      updateHover();
      return;
    }
    const zooms = chart.current.getOption().dataZoom as Zoom[];
    const windowFor = (id: string): [number, number] => {
      const zoom = zooms.find((item) => item.id === id);
      return [zoom?.start ?? 0, zoom?.end ?? 100];
    };
    drag.current = { x, y, endX: x, endY: y, kind: event.button === 2 ? 'pan' : 'select',
      time: windowFor('time-inside'), value: windowFor('value-inside') };
    if (event.button === 0) setSelection(drag.current);
    setPanning(event.button === 2);
    updateHover();
  };
  const moveSelection = (event: PointerEvent<HTMLDivElement>) => {
    if (horizontalPan.activeRef.current) {
      horizontalPan.move(point(event).x);
      event.preventDefault(); event.stopPropagation(); return;
    }
    if (!drag.current || !chart.current) return;
    event.preventDefault();
    event.stopPropagation();
    const { x, y } = point(event);
    drag.current = { ...drag.current, endX: x, endY: y };
    if (drag.current.kind === 'drawing') drawing.move(x, y);
    else if (drag.current.kind === 'measurement') {
      const current = measurementRef.current;
      const signal = current && traces.find((trace) => trace.id === current.signalId);
      if (signal) {
        const sample = nearestSample(chart.current, signal, sampleRate, x, y, true);
        if (sample !== undefined) changePoint(drag.current.endpoint, sample);
      }
    } else if (drag.current.kind === 'select') setSelection(drag.current);
    else {
      const { time, value } = drag.current;
      chart.current.dispatchAction({ type: 'dataZoom', batch: [
        { dataZoomId: 'time-inside', ...shiftedWindow(time, -(x - drag.current.x) / (chart.current.getWidth() - grid.left - grid.right) * (time[1] - time[0])) },
        { dataZoomId: 'value-inside', ...shiftedWindow(value, (y - drag.current.y) / (chart.current.getHeight() - grid.top - grid.bottom) * (value[1] - value[0])) },
      ] });
    }
  };
  const endSelection = (event: PointerEvent<HTMLDivElement>) => {
    const area = drag.current;
    if (area?.kind === 'drawing') drawing.finish();
    cancelDrag();
    if (!area || !chart.current) return;
    event.currentTarget.releasePointerCapture(event.pointerId);
    if (area.kind !== 'select' || Math.abs(area.endX - area.x) < 5 || Math.abs(area.endY - area.y) < 5) return;
    const clampPoint = (x: number, y: number) => [
      Math.max(grid.left, Math.min(chart.current!.getWidth() - grid.right, x)),
      Math.max(grid.top, Math.min(chart.current!.getHeight() - grid.bottom, y)),
    ];
    const from = chart.current.convertFromPixel({ gridIndex: 0 }, clampPoint(area.x, area.y)) as number[];
    const to = chart.current.convertFromPixel({ gridIndex: 0 }, clampPoint(area.endX, area.endY)) as number[];
    chart.current.dispatchAction({ type: 'dataZoom', batch: [
      { dataZoomId: 'time-inside', startValue: Math.max(0, Math.min(from[0], to[0])), endValue: Math.min(timeMax, Math.max(from[0], to[0])) },
      { dataZoomId: 'value-inside', startValue: Math.min(from[1], to[1]), endValue: Math.max(from[1], to[1]) },
    ] });
  };

  const screenshot = async () => {
    if (!chart.current || !workspace.current) return;
    setCapturing(true);
    try { downloadFile(await signalScreenshot(chart.current, workspace.current), `${testName}_signals.png`); }
    catch { message.error('Could not save screenshot.'); }
    finally { setCapturing(false); }
  };

  if (!signals.length) return <div className="signal-workspace-message"><Empty description="No signals stored for this test" /></div>;
  if (!validRate) return <div className="signal-workspace-message"><Alert type="error" showIcon title="A valid sample rate is required to plot signals against time." /></div>;
  const hoveredSignal = hovered && traces.find((signal) => signal.id === hovered.signalId);
  const measuredSignal = measurement && selected.includes(measurement.signalId) && traces.find((signal) => signal.id === measurement.signalId);
  const available = traces.filter((signal) => signal.samples.length);
  const allVisible = available.length > 0 && available.every((signal) => selected.includes(signal.id));

  return <div ref={workspace} className="signal-workspace">
      <div ref={legend} className="signal-legend" role="group" aria-label="Signals">
        <span className="signal-test-name">{testName}</span>
        {traces.map((signal) => {
          const visible = selected.includes(signal.id);
          return <button type="button" key={signal.id} className={`signal-toggle${visible ? ' is-visible' : ''}`}
            aria-pressed={visible} disabled={!signal.samples.length}
            onClick={() => setSelected((current) => current.includes(signal.id) ? current.filter((id) => id !== signal.id) : [...current, signal.id])}>
            <span className="signal-color" aria-hidden="true" style={{ background: visible ? signal.color : '#b5bdc9' }} />
            <span>{signal.name}</span>
          </button>;
        })}
        <button type="button" className="signal-toggle signal-toggle-all" disabled={!available.length}
          onClick={() => setSelected(allVisible ? [] : available.map((signal) => signal.id))}>
          {allVisible ? 'Hide all' : 'Show all'}
        </button>
        <SignalDrawingTools drawing={drawing} onScreenshot={screenshot} busy={capturing} disabled={!sampleCount} />
      </div>
      <div className={`signal-chart-viewport${panning ? ' is-panning' : ''}${drawing.mode === 'eraser' ? ' is-erasing' : ''}${horizontalPan.anchor ? ' is-horizontal-scrolling' : ''}`}
        onPointerDownCapture={beginSelection} onPointerMoveCapture={moveSelection} onPointerUpCapture={endSelection}
        onPointerCancel={cancelDrag} onLostPointerCapture={cancelDrag}
        onPointerLeave={horizontalPan.stop}
        onMouseDownCapture={(event) => { if (event.button === 1) event.preventDefault(); }}
        onAuxClick={(event) => { if (event.button === 1) event.preventDefault(); }}
        onContextMenu={(event) => event.preventDefault()} onDoubleClick={(event) => {
          if (event.button === 0 && drawing.modeRef.current === 'pointer' && !event.shiftKey && !(event.target as Element).closest('[data-measurement-point]')) reset();
        }}>
        <div ref={host} className="signal-chart-canvas" role="img" aria-label="Signal chart" />
        {horizontalPan.anchor && <svg className="signal-horizontal-anchor" role="img" aria-label="Horizontal scrolling" width="26" height="26"
          viewBox="0 0 26 26" style={{ left: horizontalPan.anchor.x - 13, top: horizontalPan.anchor.y - 13 }}>
          <circle cx="13" cy="13" r="12" fill="#fffffff2" stroke="#667085" />
          <path d="M9 9 5 13 9 17 M17 9 21 13 17 17" fill="none" stroke="#344054" strokeWidth="1.5" />
          <circle cx="13" cy="13" r="1.5" fill="#344054" />
        </svg>}
        {chart.current && <SignalDrawingOverlay items={drawing.items} draft={drawing.draft} chart={chart.current} grid={grid} revision={viewRevision} />}
        {measurement && measuredSignal && chart.current && <SignalMeasurement measurement={measurement} signal={measuredSignal}
          sampleRate={sampleRate} chart={chart.current} grid={grid} revision={viewRevision} onPointChange={changePoint} />}
        {!selected.length && <div className="signal-chart-empty"><Empty description={sampleCount ? 'No signals visible' : 'No samples stored for this test'} /></div>}
        {selection && <div className="signal-chart-selection" style={{ left: Math.min(selection.x, selection.endX), top: Math.min(selection.y, selection.endY),
          width: Math.abs(selection.endX - selection.x), height: Math.abs(selection.endY - selection.y) }} />}
      </div>
      {hovered && hoveredSignal && <div className="signal-hover-readout" role="tooltip" aria-label="Signal coordinates">
        <strong style={{ color: hoveredSignal.color }}>{hoveredSignal.name}</strong>
        <span>Time: {number(hovered.sample / sampleRate)} s</span>
        <span>Value: {number(hoveredSignal.samples[hovered.sample])}</span>
      </div>}
      <div className="signal-time-range">
        <span aria-label="Visible time range">Time: {number(timeWindow[0] / 100 * timeMax)}–{number(timeWindow[1] / 100 * timeMax)} s</span>
      </div>
  </div>;
}
