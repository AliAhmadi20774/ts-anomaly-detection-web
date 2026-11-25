import { CameraOutlined, ClearOutlined, EditOutlined, MinusOutlined, SelectOutlined } from '@ant-design/icons';
import { Dropdown } from 'antd';
import type { EChartsType } from 'echarts/core';
import { useCallback, useId, useMemo, useRef, useState, type RefObject } from 'react';

export type DrawingMode = 'pointer' | 'pen' | 'line' | 'eraser';
type Point = [number, number];
type Drawing = { id: number; kind: 'pen' | 'line'; points: Point[] };
type Grid = { left: number; right: number; top: number; bottom: number };

const color = '#e54865';
const pointDistance = (p: Point, a: Point, b: Point) => {
  const dx = b[0] - a[0];
  const dy = b[1] - a[1];
  const ratio = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy || 1)));
  return (p[0] - a[0] - ratio * dx) ** 2 + (p[1] - a[1] - ratio * dy) ** 2;
};
const segmentDistance = (a: Point, b: Point, c: Point, d: Point) => {
  const cross = (u: Point, v: Point) => u[0] * v[1] - u[1] * v[0];
  const ab: Point = [b[0] - a[0], b[1] - a[1]];
  const cd: Point = [d[0] - c[0], d[1] - c[1]];
  const ac: Point = [c[0] - a[0], c[1] - a[1]];
  const denominator = cross(ab, cd);
  if (denominator !== 0) {
    const t = cross(ac, cd) / denominator;
    const u = cross(ac, ab) / denominator;
    if (t >= 0 && t <= 1 && u >= 0 && u <= 1) return 0;
  }
  return Math.min(pointDistance(a, c, d), pointDistance(b, c, d), pointDistance(c, a, b), pointDistance(d, a, b));
};

export function useSignalDrawing(chart: RefObject<EChartsType | null>, grid: Grid) {
  const [mode, setModeState] = useState<DrawingMode>('pointer');
  const modeRef = useRef<DrawingMode>('pointer');
  const [menuOpen, setMenuOpenState] = useState(false);
  const menuOpenRef = useRef(false);
  const [items, setItems] = useState<Drawing[]>([]);
  const [draft, setDraftState] = useState<Drawing>();
  const draftRef = useRef<Drawing | undefined>(undefined);
  const previous = useRef<Point | undefined>(undefined);
  const sequence = useRef(0);
  const setDraft = useCallback((next?: Drawing) => { draftRef.current = next; setDraftState(next); }, []);
  const cancel = useCallback(() => { setDraft(); previous.current = undefined; }, [setDraft]);
  const setMenuOpen = useCallback((open: boolean) => { menuOpenRef.current = open; setMenuOpenState(open); }, []);
  const setMode = useCallback((next: DrawingMode) => {
    cancel();
    modeRef.current = next;
    setModeState(next);
    setMenuOpen(false);
  }, [cancel, setMenuOpen]);
  const pixel = useCallback((x: number, y: number): Point => [
    Math.max(grid.left, Math.min(chart.current!.getWidth() - grid.right, x)),
    Math.max(grid.top, Math.min(chart.current!.getHeight() - grid.bottom, y)),
  ], [chart, grid]);
  const erase = useCallback((from: Point, to: Point) => {
    const instance = chart.current;
    if (!instance) return;
    setItems((current) => current.filter((item) => {
      const points = item.points.map((point) => instance.convertToPixel({ gridIndex: 0 }, point) as Point);
      return !points.some((point, index) => segmentDistance(from, to, points[Math.max(0, index - 1)], point) <= 10 ** 2);
    }));
  }, [chart]);
  const start = useCallback((x: number, y: number) => {
    if (!chart.current) return;
    const point = pixel(x, y);
    previous.current = point;
    if (modeRef.current === 'eraser') erase(point, point);
    else if (modeRef.current === 'pen' || modeRef.current === 'line') {
      setDraft({ id: ++sequence.current, kind: modeRef.current,
        points: [chart.current.convertFromPixel({ gridIndex: 0 }, point) as Point] });
    }
  }, [chart, pixel, erase, setDraft]);
  const move = useCallback((x: number, y: number) => {
    if (!chart.current || !previous.current) return;
    const point = pixel(x, y);
    if (modeRef.current === 'eraser') erase(previous.current, point);
    else if (draftRef.current) {
      const current = draftRef.current;
      if (Math.hypot(point[0] - previous.current[0], point[1] - previous.current[1]) < 2) return;
      const data = chart.current.convertFromPixel({ gridIndex: 0 }, point) as Point;
      setDraft({ ...current, points: current.kind === 'line' ? [current.points[0], data] : [...current.points, data] });
    }
    previous.current = point;
  }, [chart, pixel, erase, setDraft]);
  const finish = useCallback(() => {
    const current = draftRef.current;
    if (current && (current.kind === 'pen' || current.points.length > 1)) setItems((items) => [...items, current]);
    cancel();
  }, [cancel]);
  return { mode, modeRef, setMode, menuOpen, menuOpenRef, setMenuOpen, items, draft, start, move, finish, cancel };
}

export function SignalDrawingOverlay({ items, draft, chart, grid, revision }: {
  items: Drawing[]; draft?: Drawing; chart: EChartsType; grid: Grid; revision: number;
}) {
  const clip = useId().replace(/:/g, '');
  const paths = useMemo(() => [...items, ...(draft ? [draft] : [])].map((item) => {
    const points = item.points.map((point) => chart.convertToPixel({ gridIndex: 0 }, point) as Point);
    return { ...item, path: points.map((point, index) => `${index ? 'L' : 'M'}${point[0]},${point[1]}`).join(' '), point: points[0] };
  }), [items, draft, chart, grid, revision]);
  return <svg className="signal-annotation-overlay" role="group" aria-label="Drawings">
    <defs><clipPath id={clip}><rect x={grid.left} y={grid.top} width={Math.max(0, chart.getWidth() - grid.left - grid.right)}
      height={Math.max(0, chart.getHeight() - grid.top - grid.bottom)} /></clipPath></defs>
    <g clipPath={`url(#${clip})`}>
      {paths.map((item) => item.points.length === 1
        ? <circle key={item.id} data-drawing-kind={item.kind} cx={item.point[0]} cy={item.point[1]} r={1.5} fill={color} />
        : <path key={item.id} data-drawing-kind={item.kind} d={item.path} fill="none" stroke={color} strokeWidth={2.2}
          strokeLinecap="round" strokeLinejoin="round" />)}
    </g>
  </svg>;
}

const icons = { pointer: <SelectOutlined aria-hidden="true" />, pen: <EditOutlined aria-hidden="true" />,
  line: <MinusOutlined aria-hidden="true" rotate={-35} />, eraser: <ClearOutlined aria-hidden="true" /> };
export function SignalDrawingTools({ drawing, onScreenshot, busy, disabled }: {
  drawing: ReturnType<typeof useSignalDrawing>; onScreenshot: () => void; busy: boolean; disabled: boolean;
}) {
  return <Dropdown trigger={['click']} open={drawing.menuOpen} onOpenChange={drawing.setMenuOpen}
    getPopupContainer={(trigger) => trigger.parentElement!}
    menu={{ selectedKeys: [drawing.mode], items: [
      { key: 'pointer', label: 'Pointer', icon: icons.pointer }, { key: 'pen', label: 'Pen', icon: icons.pen },
      { key: 'line', label: 'Line', icon: icons.line }, { key: 'eraser', label: 'Eraser', icon: icons.eraser },
      { type: 'divider' }, { key: 'screenshot', label: 'Screenshot', icon: <CameraOutlined aria-hidden="true" />, disabled: busy },
    ], onClick: ({ key }) => {
      drawing.setMenuOpen(false);
      if (key === 'screenshot') onScreenshot();
      else drawing.setMode(key as DrawingMode);
    } }}>
    <button type="button" className={`signal-drawing-toggle${drawing.mode !== 'pointer' ? ' is-active' : ''}`}
      aria-label="Drawing tools" aria-expanded={drawing.menuOpen} aria-busy={busy} data-tool={drawing.mode} disabled={disabled || busy}>
      {drawing.mode === 'pointer' ? icons.pen : icons[drawing.mode]}
    </button>
  </Dropdown>;
}
