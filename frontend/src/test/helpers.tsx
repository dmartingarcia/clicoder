import React, { ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { vi } from 'vitest';

// ── i18n mock ────────────────────────────────────────────────────────────────
// Simple identity t() that returns the key (or interpolated value)
export const mockT = vi.fn((key: string, vars?: Record<string, string | number>) => {
  if (!vars) return key;
  return key.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
});

vi.mock('@/contexts/I18nContext', () => ({
  useI18n: () => ({
    t: mockT,
    locale: 'es',
    setLocale: vi.fn(),
    ready: true,
  }),
  I18nProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

// ── sonner mock ───────────────────────────────────────────────────────────────
vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

// ── socket mock ───────────────────────────────────────────────────────────────
vi.mock('@/lib/socket', () => ({
  getSocket: vi.fn(() => ({
    channel: vi.fn(() => ({
      join: vi.fn(() => ({ receive: vi.fn(() => ({ receive: vi.fn() })) })),
      on: vi.fn(),
      push: vi.fn(() => ({ receive: vi.fn() })),
      leave: vi.fn(),
    })),
  })),
}));

// ── config mock ───────────────────────────────────────────────────────────────
vi.mock('@/lib/config', () => ({
  config: { apiUrl: 'http://localhost:4000' },
}));

// ── Custom render (wraps in nothing extra by default) ─────────────────────────
export function renderWithProviders(ui: React.ReactElement, options?: RenderOptions) {
  return render(ui, options);
}
