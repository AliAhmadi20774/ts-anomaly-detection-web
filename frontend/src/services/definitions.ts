import { apiRequest } from './client';

export interface DeviceType {
  id: string;
  name: string;
}

export interface TestDefinition extends DeviceType {
  device_type: string;
  device_type_name: string;
  sample_rate_hz: number;
}

export interface SignalDefinition extends DeviceType {
  test: string;
  test_name: string;
  device_type_name: string;
}

export interface Page<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface ListParams {
  page?: number;
  page_size?: number;
  search?: string;
  device_type?: string;
  test?: string;
}

export interface SelectOption {
  value: string;
  label: string;
}

export type DeviceTypeInput = Pick<DeviceType, 'name'>;
export type TestDefinitionInput = Pick<TestDefinition, 'name' | 'device_type' | 'sample_rate_hz'>;
export type SignalDefinitionInput = Pick<SignalDefinition, 'name' | 'test'>;

export const deviceTypes = {
  list: (params: ListParams = {}) =>
    apiRequest<Page<DeviceType>>('/device-types/', { params: { ...params } }),
  create: (data: DeviceTypeInput) =>
    apiRequest<DeviceType>('/device-types/', { method: 'POST', data }),
  update: (id: string, data: DeviceTypeInput) =>
    apiRequest<DeviceType>(`/device-types/${id}/`, { method: 'PATCH', data }),
  remove: (id: string) => apiRequest<void>(`/device-types/${id}/`, { method: 'DELETE' }),
};

export const testDefinitions = {
  list: (params: ListParams = {}) =>
    apiRequest<Page<TestDefinition>>('/test-definitions/', { params: { ...params } }),
  create: (data: TestDefinitionInput) =>
    apiRequest<TestDefinition>('/test-definitions/', { method: 'POST', data }),
  update: (id: string, data: TestDefinitionInput) =>
    apiRequest<TestDefinition>(`/test-definitions/${id}/`, { method: 'PATCH', data }),
  remove: (id: string) => apiRequest<void>(`/test-definitions/${id}/`, { method: 'DELETE' }),
};

export const signalDefinitions = {
  list: (params: ListParams = {}) =>
    apiRequest<Page<SignalDefinition>>('/signal-definitions/', { params: { ...params } }),
  create: (data: SignalDefinitionInput) =>
    apiRequest<SignalDefinition>('/signal-definitions/', { method: 'POST', data }),
  update: (id: string, data: SignalDefinitionInput) =>
    apiRequest<SignalDefinition>(`/signal-definitions/${id}/`, { method: 'PATCH', data }),
  remove: (id: string) => apiRequest<void>(`/signal-definitions/${id}/`, { method: 'DELETE' }),
};

function includeSelected(options: SelectOption[], selected?: SelectOption): SelectOption[] {
  return selected && !options.some((option) => option.value === selected.value)
    ? [selected, ...options] : options;
}

export async function deviceOptions(search?: string, selected?: SelectOption) {
  const page = await deviceTypes.list({ search, page_size: 50 });
  return includeSelected(page.results.map((item) => ({
    value: item.id, label: item.name,
  })), selected);
}

export async function testOptions(search?: string, selected?: SelectOption) {
  const page = await testDefinitions.list({ search, page_size: 50 });
  return includeSelected(page.results.map((item) => ({
    value: item.id, label: `${item.device_type_name} / ${item.name}`,
  })), selected);
}
