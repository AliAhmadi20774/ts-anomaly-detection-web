import { afterEach, describe, expect, it, vi } from 'vitest';
import { apiRequest } from './client';

afterEach(() => vi.unstubAllGlobals());

describe('API request bodies', () => {
  it('lets the browser set the multipart boundary and includes the CSRF cookie', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    vi.stubGlobal('document', { cookie: 'csrftoken=csrf-value' });
    const data = new FormData();
    data.append('files', new Blob(['sample']), 'sample.dat');
    await apiRequest('/dat/preview/', { method: 'POST', data });
    const options = fetch.mock.calls[0][1];
    expect(options.body).toBe(data);
    expect(options.headers['Content-Type']).toBeUndefined();
    expect(options.headers['X-CSRFToken']).toBe('csrf-value');
    expect(options.credentials).toBe('same-origin');
  });

  it('keeps existing JSON requests unchanged', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetch);
    vi.stubGlobal('document', { cookie: '' });
    await apiRequest('/device-types/', { method: 'POST', data: { name: 'Motor' } });
    expect(fetch.mock.calls[0][1].headers['Content-Type']).toBe('application/json');
    expect(fetch.mock.calls[0][1].body).toBe('{"name":"Motor"}');
  });
});
