import { Button, Empty, Select, Slider } from 'antd';
import { useMemo, useState } from 'react';
import type { SignalTraceData } from '@/services/testRuns';
import { signalSvg } from '@/utils/signalChart';

function SignalPlot({ signal }: { signal: SignalTraceData }) {
  const last = Math.max(0, signal.samples.length - 1);
  const [range, setRange] = useState<[number, number]>([0, last]);
  const chart = useMemo(() => signalSvg(signal.name, signal.samples, range[0], range[1]), [signal, range]);
  if (!signal.samples.length) return <Empty description="No samples stored for this signal" />;
  return <>
    <div className="serial-signal-chart" dangerouslySetInnerHTML={{ __html: chart }} />
    <div className="serial-graph-range">
      <span>Samples {range[0].toLocaleString()}–{range[1].toLocaleString()} of {signal.samples.length.toLocaleString()}</span>
      <Button size="small" onClick={() => setRange([0, last])}>Reset zoom</Button>
    </div>
    <Slider range min={0} max={last || 1} value={range} disabled={last === 0}
      aria-label="Sample range" onChange={(value) => setRange(value as [number, number])} />
    <p className="serial-graph-note">Drag the handles to zoom. The chart preserves peaks; Excel includes every original sample.</p>
  </>;
}

export default function SignalGraphs({ signals }: { signals: SignalTraceData[] }) {
  const [selected, setSelected] = useState(signals[0]?.id);
  const signal = signals.find((item) => item.id === selected);
  if (!signals.length) return <Empty description="No signals stored for this test" />;
  return <>
    <Select aria-label="Signal" value={selected} onChange={setSelected} showSearch
      optionFilterProp="label" className="serial-signal-select"
      options={signals.map((item) => ({ value: item.id, label: `${item.name} (${item.samples.length.toLocaleString()} samples)` }))} />
    {signal && <SignalPlot key={signal.id} signal={signal} />}
  </>;
}
