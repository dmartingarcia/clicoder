'use client';

import { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import { config } from '@/lib/config';

export interface AuthUser {
  id: string;
  first_name: string;
  last_name: string;
  username: string;
  email: string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  /** Non-null while waiting for the user to confirm their email */
  pendingEmail: string | null;
  /** False until localStorage has been read — avoids SSR/client mismatch */
  mounted: boolean;
  login: (email: string, password: string) => Promise<{ error?: string }>;
  register: (fields: { first_name: string; last_name: string; username: string; email: string; password: string }) => Promise<{ error?: string }>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const STORAGE_KEY = 'cie10_auth';

function loadFromStorage(): { user: AuthUser; token: string } | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  // Lazy initializer: safe to read localStorage on client, returns null on SSR
  const [auth, setAuth] = useState<{ user: AuthUser; token: string } | null>(loadFromStorage);
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const persist = useCallback((data: { user: AuthUser; token: string } | null) => {
    setAuth(data);
    if (data) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    try {
      const res = await fetch(`${config.apiUrl}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) return { error: data.error ?? 'Error al iniciar sesión' };
      persist({ user: data.user, token: data.token });
      return {};
    } catch {
      return { error: 'No se pudo conectar con el servidor' };
    }
  }, [persist]);

  const register = useCallback(async ({ first_name, last_name, username, email, password }: { first_name: string; last_name: string; username: string; email: string; password: string }) => {
    try {
      const res = await fetch(`${config.apiUrl}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ first_name, last_name, username, email, password }),
      });
      const data = await res.json();

      if (!res.ok) {
        const firstError = data.errors
          ? Object.values(data.errors as Record<string, string[]>).flat()[0]
          : 'Error al registrarse';
        return { error: firstError as string };
      }

      if (data.status === 'pending_confirmation') {
        setPendingEmail(email);
        return {};
      }

      persist({ user: data.user, token: data.token });
      return {};
    } catch {
      return { error: 'No se pudo conectar con el servidor' };
    }
  }, [persist]);

  const logout = useCallback(() => {
    persist(null);
    setPendingEmail(null);
  }, [persist]);

  return (
    <AuthContext.Provider value={{ user: auth?.user ?? null, token: auth?.token ?? null, pendingEmail, mounted, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
