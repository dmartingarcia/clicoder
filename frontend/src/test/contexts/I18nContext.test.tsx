import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, act, waitFor } from '@testing-library/react';
import React, { ReactNode } from 'react';

// ── Mock @/lib/config ────────────────────────────────────────────────────────
vi.mock('@/lib/config', () => ({
  config: { apiUrl: 'http://localhost:4000' },
}));

import { I18nProvider, useI18n } from '@/contexts/I18nContext';

// ── Helper component ──────────────────────────────────────────────────────────

function Probe({ onRender }: { onRender: (ctx: ReturnType<typeof useI18n>) => void }) {
  const ctx = useI18n();
  onRender(ctx);
  return null;
}

function renderProvider(children?: ReactNode) {
  let capturedCtx!: ReturnType<typeof useI18n>;
  render(
    <I18nProvider>
      <Probe onRender={(ctx) => { capturedCtx = ctx; }} />
      {children}
    </I18nProvider>
  );
  return () => capturedCtx;
}

function mockFetch(body: unknown, ok = true) {
  global.fetch = vi.fn().mockResolvedValue({ ok, json: async () => body } as Response);
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('I18nProvider', () => {
  // jsdom defaults to 'en'; override to an unsupported language so the
  // I18nProvider falls back to DEFAULT_LOCALE ('es') in all tests that
  // don't explicitly set localStorage.
  let originalLanguage: string;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    originalLanguage = navigator.language;
    Object.defineProperty(navigator, 'language', { value: 'zh-CN', configurable: true, writable: true });
    mockFetch({ auth: { login: 'Iniciar sesión' }, chat: { welcome_title: 'Bienvenido' } });
  });

  afterEach(() => {
    localStorage.clear();
    Object.defineProperty(navigator, 'language', { value: originalLanguage, configurable: true, writable: true });
  });

  describe('initial state', () => {
    it('starts with ready=false then ready=true after fetch', async () => {
      const getCtx = renderProvider();
      // Initially not ready
      expect(getCtx().ready).toBe(false);
      // After fetch resolves, ready=true
      await waitFor(() => expect(getCtx().ready).toBe(true));
    });

    it('starts with default locale "es"', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      expect(getCtx().locale).toBe('es');
    });
  });

  describe('locale detection from localStorage', () => {
    it('uses stored locale from localStorage if supported', async () => {
      localStorage.setItem('cie10_locale', 'en');
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      expect(getCtx().locale).toBe('en');
    });

    it('falls back to default when stored locale is unsupported', async () => {
      localStorage.setItem('cie10_locale', 'xx');
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      expect(getCtx().locale).toBe('es');
    });

    it('fetches correct locale when restored from localStorage', async () => {
      localStorage.setItem('cie10_locale', 'en');
      renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain('/translations/en');
    });
  });

  describe('translation loading', () => {
    it('fetches translations from the API on mount', async () => {
      renderProvider();
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());
      const [url] = (global.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(url).toContain('/translations/es');
    });

    it('caches translations to localStorage after fetch', async () => {
      const translations = { auth: { login: 'Iniciar sesión' } };
      mockFetch(translations);
      renderProvider();
      await waitFor(() => {
        const cached = localStorage.getItem('cie10_translations_es');
        return expect(cached).not.toBeNull();
      });
      const parsed = JSON.parse(localStorage.getItem('cie10_translations_es')!);
      expect(parsed).toEqual(translations);
    });

    it('serves cache immediately when available, ready=true before fetch resolves', async () => {
      const cached = { auth: { login: 'Cached login' } };
      // navigator.language is 'zh-CN' (unsupported) so locale will be 'es'
      localStorage.setItem('cie10_translations_es', JSON.stringify(cached));

      // Make fetch never resolve: cache should still set ready=true
      global.fetch = vi.fn().mockReturnValue(new Promise(() => {}));

      const getCtx = renderProvider();
      // Cache hit: setReady(true) is called synchronously before fetch resolves
      await waitFor(() => expect(getCtx().ready).toBe(true), { timeout: 500 });
    });

    it('sets ready=true even when fetch fails', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
    });
  });

  describe('t() function', () => {
    it('returns the translation for a valid key', async () => {
      mockFetch({ auth: { login: 'Iniciar sesión' } });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      await waitFor(() => expect(getCtx().t('auth.login')).toBe('Iniciar sesión'));
    });

    it('returns the key when namespace is missing', async () => {
      mockFetch({});
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      expect(getCtx().t('missing.key')).toBe('missing.key');
    });

    it('returns the key when the leaf key is missing', async () => {
      mockFetch({ auth: {} });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      expect(getCtx().t('auth.nonexistent')).toBe('auth.nonexistent');
    });

    it('interpolates variables in translation strings', async () => {
      mockFetch({ chat: { min_chars: 'Mínimo {min} caracteres, faltan {remaining}' } });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      const result = getCtx().t('chat.min_chars', { min: 20, remaining: 15 });
      expect(result).toBe('Mínimo 20 caracteres, faltan 15');
    });

    it('keeps placeholder for missing variable in interpolation', async () => {
      mockFetch({ chat: { msg: 'Hello {name}' } });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      const result = getCtx().t('chat.msg', {});
      expect(result).toBe('Hello {name}');
    });

    it('handles keys with multiple dots correctly', async () => {
      mockFetch({ cards: { 'summary_title': 'Resumen' } });
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));
      expect(getCtx().t('cards.summary_title')).toBe('Resumen');
    });
  });

  describe('setLocale', () => {
    it('changes the locale state', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));

      act(() => { getCtx().setLocale('en'); });
      await waitFor(() => expect(getCtx().locale).toBe('en'));
    });

    it('persists the locale to localStorage', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));

      act(() => { getCtx().setLocale('fr'); });
      expect(localStorage.getItem('cie10_locale')).toBe('fr');
    });

    it('does nothing for an unsupported locale', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));

      act(() => { getCtx().setLocale('zz'); });
      expect(getCtx().locale).toBe('es');
      expect(localStorage.getItem('cie10_locale')).toBeNull();
    });

    it('sends PUT request with token when token is provided', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));

      vi.clearAllMocks();
      mockFetch({});

      act(() => { getCtx().setLocale('en', 'my-token'); });
      await waitFor(() => {
        const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
        return expect(calls.length).toBeGreaterThan(0);
      });

      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      const putCall = calls.find((call) => {
        const [url, opts] = call as [string, RequestInit];
        return url.includes('/users/locale') && opts.method === 'PUT';
      });
      expect(putCall).toBeDefined();
      expect((putCall![1] as RequestInit).headers).toMatchObject({
        Authorization: 'Bearer my-token',
      });
    });

    it('does NOT send PUT request when no token is provided', async () => {
      const getCtx = renderProvider();
      await waitFor(() => expect(getCtx().ready).toBe(true));

      vi.clearAllMocks();
      mockFetch({});

      act(() => { getCtx().setLocale('en'); });
      await waitFor(() => expect(global.fetch).toHaveBeenCalled());

      const calls = (global.fetch as ReturnType<typeof vi.fn>).mock.calls;
      const putCall = calls.find((call) => (call as [string])[0].includes('/users/locale'));
      expect(putCall).toBeUndefined();
    });
  });
});
