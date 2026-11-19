import { beforeEach, describe, expect, it, vi } from 'vitest';

const { mockGetUser, mockHistory } = vi.hoisted(() => ({
  mockGetUser: vi.fn(),
  mockHistory: {
    location: { pathname: '/device-types', search: '', hash: '' },
    replace: vi.fn(),
  },
}));

vi.mock('@umijs/max', () => ({
  history: mockHistory, Link: ({ children }: { children: unknown }) => children,
}));
vi.mock('@/services/auth', () => ({ getCurrentUser: mockGetUser }));
vi.mock('@/components/ErrorBoundary', () => ({
  default: ({ children }: { children: unknown }) => children,
}));
vi.mock('@/components/OfflineBanner', () => ({ default: () => null }));
vi.mock('@/components/RightContent/AvatarDropdown', () => ({ AvatarDropdown: () => null }));
vi.mock('./requestErrorConfig', () => ({ errorConfig: {} }));
vi.mock('../config/defaultSettings', () => ({ default: { navTheme: 'light' } }));

const user = {
  id: 1, username: '001', name: '001', is_superuser: true, permissions: [],
};

describe('Django session restoration', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockHistory.location = { pathname: '/device-types', search: '', hash: '' };
  });

  it('restores the current Django user and layout settings', async () => {
    mockGetUser.mockResolvedValue(user);
    const { getInitialState } = await import('./app');
    const state = await getInitialState();
    expect(state.currentUser).toEqual(user);
    expect(state.settings).toEqual({ navTheme: 'light' });
  });

  it('restores an existing session even on the sign-in page', async () => {
    mockHistory.location.pathname = '/user/login';
    mockGetUser.mockResolvedValue(user);
    const { getInitialState } = await import('./app');
    expect((await getInitialState()).currentUser).toEqual(user);
  });

  it('returns an unauthenticated state when no Django session exists', async () => {
    mockGetUser.mockRejectedValue(new Error('Sign in required'));
    const { getInitialState } = await import('./app');
    expect((await getInitialState()).currentUser).toBeUndefined();
  });

  it('can refresh user information after the session changes', async () => {
    mockGetUser.mockResolvedValue(user);
    const { getInitialState } = await import('./app');
    const state = await getInitialState();
    const updated = { ...user, name: 'Updated name' };
    mockGetUser.mockResolvedValue(updated);
    expect(await state.fetchUserInfo?.()).toEqual(updated);
  });
});
