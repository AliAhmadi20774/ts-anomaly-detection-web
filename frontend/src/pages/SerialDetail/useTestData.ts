import { useCallback, useMemo } from 'react';
import { type SignalTraceData, type TestRunDetail, testRuns } from '@/services/testRuns';

export default function useTestData(deviceId: string | undefined, canView: boolean) {
  const cache = useMemo(() => ({
    details: new Map<string, Promise<TestRunDetail>>(),
    signals: new Map<string, Promise<SignalTraceData[]>>(),
  }), [deviceId, canView]);

  const getDetail = useCallback((id: string): Promise<TestRunDetail> => {
    if (!canView) return Promise.reject(new Error('Test result access is unavailable for your account.'));
    const stored = cache.details.get(id);
    if (stored) return stored;
    const request = testRuns.detail(id).catch((error) => {
      cache.details.delete(id);
      throw error;
    });
    cache.details.set(id, request);
    return request;
  }, [cache, canView]);

  const getSignals = useCallback((id: string): Promise<SignalTraceData[]> => {
    if (!canView) return Promise.reject(new Error('Signal access is unavailable for your account.'));
    const stored = cache.signals.get(id);
    if (stored) return stored;
    const request = (async () => {
      const summaries = await testRuns.signals(id);
      const signals: SignalTraceData[] = [];
      // Limit concurrent large sample downloads, keeping the API's signal order.
      for (let index = 0; index < summaries.length; index += 4) {
        signals.push(...await Promise.all(summaries.slice(index, index + 4).map(async (summary) => {
          const trace = await testRuns.signalSamples(id, summary.id);
          if (trace.samples.length !== summary.sample_count || !trace.samples.every(Number.isFinite)) {
            throw new Error(`Incomplete or invalid samples for ${summary.name}. Please try again.`);
          }
          return trace;
        })));
      }
      return signals;
    })().catch((error) => {
      cache.signals.delete(id);
      throw error;
    });
    cache.signals.set(id, request);
    return request;
  }, [cache, canView]);

  return { getDetail, getSignals };
}
