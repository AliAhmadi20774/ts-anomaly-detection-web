export interface BackendHealth {
  status: 'ok';
}

export async function getBackendHealth(
  signal?: AbortSignal,
): Promise<BackendHealth> {
  const response = await fetch('/backend/health', { signal });

  if (!response.ok) {
    throw new Error(`The API returned HTTP ${response.status}.`);
  }

  const health: unknown = await response.json();
  if (
    typeof health !== 'object' ||
    health === null ||
    !('status' in health) ||
    health.status !== 'ok'
  ) {
    throw new Error('The API returned an unexpected health response.');
  }

  return { status: health.status };
}
