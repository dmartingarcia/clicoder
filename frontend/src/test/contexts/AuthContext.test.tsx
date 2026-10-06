import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import React from 'react';
import '../helpers';

vi.mock('@/lib/config', () => ({
  config: { apiUrl: 'http://localhost:4000/api' },
}));

import { AuthProvider, useAuth } from '@/contexts/AuthContext';

function Probe({ onRender }: { onRender: (ctx: ReturnType<typeof useAuth>) => void }) {
  const ctx = useAuth();
  onRender(ctx);
  return null;
}

function renderProvider() {
  let capturedCtx!: ReturnType<typeof useAuth>;

  render(
    <AuthProvider>
      <Probe onRender={(ctx) => { capturedCtx = ctx; }} />
    </AuthProvider>
  );

  return () => capturedCtx;
}

function mockFetch(body: unknown, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response);
}

describe('AuthProvider', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    localStorage.clear();
  });

  describe('initial state', () => {
    it('starts with user=null and token=null when localStorage is empty', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));
      expect(getCtx().user).toBeNull();
      expect(getCtx().token).toBeNull();
    });

    it('restores user and token from localStorage on mount', async () => {
      const stored = {
        user: { id: 'u1', first_name: 'Ana', last_name: 'García', username: 'ana', email: 'ana@ex.com' },
        token: 'tok-stored',
      };
      localStorage.setItem('cie10_auth', JSON.stringify(stored));

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      expect(getCtx().user?.email).toBe('ana@ex.com');
      expect(getCtx().token).toBe('tok-stored');
    });

    it('starts with pendingEmail=null', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));
      expect(getCtx().pendingEmail).toBeNull();
    });
  });

  describe('login', () => {
    it('returns empty object and persists session on success', async () => {
      mockFetch({
        token: 'tok-ok',
        user: { id: 'u1', first_name: 'María', last_name: 'García', username: 'maria', email: 'maria@h.com' },
      }, 200);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().login('maria@h.com', 'pass1234');
      });

      expect(result).toEqual({});
      expect(getCtx().user?.email).toBe('maria@h.com');
      expect(getCtx().token).toBe('tok-ok');
    });

    it('persists session to localStorage on success', async () => {
      mockFetch({
        token: 'tok-local',
        user: { id: 'u1', first_name: 'A', last_name: 'B', username: 'ab', email: 'ab@ex.com' },
      }, 200);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      await act(async () => { await getCtx().login('ab@ex.com', 'pass'); });

      const stored = JSON.parse(localStorage.getItem('cie10_auth') ?? 'null');
      expect(stored?.token).toBe('tok-local');
    });

    it('returns an error object on 401', async () => {
      mockFetch({ error: 'Invalid credentials' }, 401);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().login('bad@ex.com', 'wrong');
      });

      expect(result.error).toBe('Invalid credentials');
      expect(getCtx().user).toBeNull();
    });

    it('returns network error when fetch throws', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().login('x@x.com', 'pass');
      });

      expect(result.error).toBe('No se pudo conectar con el servidor');
    });
  });

  describe('register', () => {
    const fields = { first_name: 'Ana', last_name: 'López', username: 'ana_lopez', email: 'ana@h.com', password: 'SecurePass1!' };

    it('sets pendingEmail on successful pending_confirmation response', async () => {
      mockFetch({ status: 'pending_confirmation' }, 201);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      await act(async () => { await getCtx().register(fields); });

      expect(getCtx().pendingEmail).toBe('ana@h.com');
    });

    it('returns empty object when registration succeeds', async () => {
      mockFetch({ status: 'pending_confirmation' }, 201);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().register(fields);
      });

      expect(result).toEqual({});
    });

    it('returns the first validation error on 422', async () => {
      mockFetch({ errors: { email: ['email ya registrado'] } }, 422);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().register(fields);
      });

      expect(result.error).toBe('email ya registrado');
    });

    it('returns generic error message when response has no errors field', async () => {
      mockFetch({ message: 'Something went wrong' }, 422);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().register(fields);
      });

      expect(result.error).toBe('Error al registrarse');
    });

    it('persists session on register success with user/token (not pending_confirmation)', async () => {
      mockFetch({
        user: { id: 'u2', first_name: 'Ana', last_name: 'López', username: 'ana_lopez', email: 'ana@h.com' },
        token: 'tok-register',
      }, 201);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().register(fields);
      });

      expect(result).toEqual({});
      expect(getCtx().user).not.toBeNull();
      expect(getCtx().token).toBe('tok-register');
    });

    it('returns network error when fetch throws', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('net fail'));

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      let result!: { error?: string };
      await act(async () => {
        result = await getCtx().register(fields);
      });

      expect(result.error).toBe('No se pudo conectar con el servidor');
    });
  });

  describe('logout', () => {
    it('clears user and token on logout', async () => {
      mockFetch({
        token: 'tok-x',
        user: { id: 'u1', first_name: 'A', last_name: 'B', username: 'ab', email: 'ab@ex.com' },
      }, 200);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      await act(async () => { await getCtx().login('ab@ex.com', 'pass'); });
      expect(getCtx().user).not.toBeNull();

      act(() => { getCtx().logout(); });

      expect(getCtx().user).toBeNull();
      expect(getCtx().token).toBeNull();
    });

    it('removes session from localStorage on logout', async () => {
      mockFetch({
        token: 'tok-x',
        user: { id: 'u1', first_name: 'A', last_name: 'B', username: 'ab', email: 'ab@ex.com' },
      }, 200);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));
      await act(async () => { await getCtx().login('ab@ex.com', 'pass'); });

      act(() => { getCtx().logout(); });

      expect(localStorage.getItem('cie10_auth')).toBeNull();
    });

    it('clears pendingEmail on logout', async () => {
      mockFetch({ status: 'pending_confirmation' }, 201);

      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));

      await act(async () => {
        await getCtx().register({ first_name: 'A', last_name: 'B', username: 'ab', email: 'ab@h.com', password: 'SecurePass1!' });
      });
      expect(getCtx().pendingEmail).toBe('ab@h.com');

      act(() => { getCtx().logout(); });
      expect(getCtx().pendingEmail).toBeNull();
    });
  });

  describe('useAuth outside provider', () => {
    it('throws when used outside AuthProvider', () => {
      const spy = vi.spyOn(console, 'error').mockImplementation(() => {});
      expect(() =>
        render(<Probe onRender={() => {}} />)
      ).toThrow('useAuth must be used within AuthProvider');
      spy.mockRestore();
    });
  });

  describe('localStorage error handling', () => {
    it('handles corrupt localStorage JSON gracefully (loadFromStorage catch)', async () => {
      localStorage.setItem('cie10_auth', 'NOT_VALID_JSON{{{');
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().mounted).toBe(true));
      expect(getCtx().user).toBeNull();
    });
  });

});
