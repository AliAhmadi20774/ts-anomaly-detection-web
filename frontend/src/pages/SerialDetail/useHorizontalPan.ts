import type { EChartsType } from 'echarts/core';
import { useCallback, useEffect, useRef, useState, type RefObject } from 'react';

export default function useHorizontalPan(chart: RefObject<EChartsType | null>, range: RefObject<[number, number]>) {
  const [anchor, setAnchor] = useState<{ x: number; y: number }>();
  const activeRef = useRef<{ x: number; y: number; pointerX: number } | undefined>(undefined);
  const stop = useCallback(() => { activeRef.current = undefined; setAnchor(undefined); }, []);
  const start = useCallback((x: number, y: number) => {
    activeRef.current = { x, y, pointerX: x };
    setAnchor({ x, y });
  }, []);
  const move = useCallback((x: number) => { if (activeRef.current) activeRef.current.pointerX = x; }, []);

  useEffect(() => {
    if (!anchor) return;
    let frame = 0;
    let previous = performance.now();
    const tick = (now: number) => {
      const current = activeRef.current;
      const instance = chart.current;
      if (!current || !instance || instance.isDisposed()) return;
      const elapsed = now - previous;
      if (elapsed >= 32) {
        previous = now;
        const offset = current.pointerX - current.x;
        const speed = Math.sign(offset) * Math.min(2, Math.max(0, Math.abs(offset) - 12) / 240);
        const [start, end] = range.current;
        const span = end - start;
        const next = Math.max(0, Math.min(100 - span, start + speed * span * Math.min(elapsed, 64) / 1000));
        if (Math.abs(next - start) > 1e-8) instance.dispatchAction({ type: 'dataZoom', dataZoomId: 'time-inside', start: next, end: next + span });
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    const onVisibility = () => { if (document.hidden) stop(); };
    window.addEventListener('blur', stop);
    document.addEventListener('visibilitychange', onVisibility);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('blur', stop);
      document.removeEventListener('visibilitychange', onVisibility);
    };
  }, [anchor, chart, range, stop]);
  return { anchor, activeRef, start, move, stop };
}
