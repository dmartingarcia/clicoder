'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { config } from '@/lib/config';

type Translations = Record<string, Record<string, string>>;

interface I18nContextType {
  locale: string;
  setLocale: (locale: string, token?: string) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  ready: boolean;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

const SUPPORTED_LOCALES = ['es', 'en', 'fr', 'it', 'de'];
const DEFAULT_LOCALE = 'es';
const STORAGE_KEY = 'cie10_locale';
const TRANSLATIONS_CACHE_KEY = 'cie10_translations';

function interpolate(str: string, vars?: Record<string, string | number>): string {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? `{${key}}`));
}

function readCache(loc: string): Translations | null {
  try {
    const raw = localStorage.getItem(`${TRANSLATIONS_CACHE_KEY}_${loc}`);
    return raw ? (JSON.parse(raw) as Translations) : null;
  } catch {
    return null;
  }
}

function writeCache(loc: string, data: Translations): void {
  try {
    localStorage.setItem(`${TRANSLATIONS_CACHE_KEY}_${loc}`, JSON.stringify(data));
  } catch {
    // localStorage quota exceeded: best effort
  }
}

export function I18nProvider({ children }: { children: ReactNode }) {
  // Always start with SSR-compatible defaults: no localStorage reads at init time.
  const [locale, setLocaleState] = useState<string>(DEFAULT_LOCALE);
  const [translations, setTranslations] = useState<Translations>({});
  const [ready, setReady] = useState(false);

  const applyTranslations = useCallback(async (loc: string) => {
    const cached = readCache(loc);
    if (cached) {
      setTranslations(cached);
      setReady(true);
    }

    try {
      const res = await fetch(`${config.apiUrl}/translations/${loc}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data: Translations = await res.json();
      writeCache(loc, data);
      setTranslations(data);
    } catch (err) {
      console.error('[i18n] Failed to load translations:', err);
    } finally {
      setReady(true);
    }
  }, []);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const browser = navigator.language.split('-')[0];
    const loc =
      stored && SUPPORTED_LOCALES.includes(stored)
        ? stored
        : SUPPORTED_LOCALES.includes(browser)
          ? browser
          : DEFAULT_LOCALE;

    setLocaleState(loc);
    applyTranslations(loc);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const setLocale = useCallback(
    (loc: string, token?: string) => {
      if (!SUPPORTED_LOCALES.includes(loc)) return;
      localStorage.setItem(STORAGE_KEY, loc);
      setLocaleState(loc);
      applyTranslations(loc);

      if (token) {
        fetch(`${config.apiUrl}/users/locale`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
          body: JSON.stringify({ locale: loc }),
        }).catch(() => {});
      }
    },
    [applyTranslations]
  );

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>): string => {
      const [namespace, ...rest] = key.split('.');
      const k = rest.join('.');
      const value = translations[namespace]?.[k];
      if (value == null) return key;
      return interpolate(value, vars);
    },
    [translations]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t, ready }}>{children}</I18nContext.Provider>
  );
}

export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}
