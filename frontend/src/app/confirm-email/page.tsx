'use client';

import { Suspense, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSearchParams, useRouter } from 'next/navigation';
import { config } from '@/lib/config';

const STORAGE_KEY = 'cie10_auth';

function ConfirmEmailContent() {
  const params = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    const token = params.get('token');
    if (!token) {
      setStatus('error');
      setErrorMsg('Enlace de confirmación inválido.');
      return;
    }

    fetch(`${config.apiUrl}/auth/confirm/${token}`)
      .then(async (res) => {
        const data = await res.json();
        if (!res.ok) {
          setStatus('error');
          setErrorMsg(data.error ?? 'El enlace no es válido o ya fue utilizado.');
          return;
        }
        localStorage.setItem(STORAGE_KEY, JSON.stringify({ user: data.user, token: data.token }));
        setStatus('success');
        setTimeout(() => router.push('/'), 1500);
      })
      .catch(() => {
        setStatus('error');
        setErrorMsg('No se pudo conectar con el servidor.');
      });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <p className="text-gray-500 text-sm">Confirmando tu cuenta…</p>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center space-y-2">
          <p className="text-green-600 font-semibold text-lg">Cuenta confirmada</p>
          <p className="text-gray-500 text-sm">Entrando a la aplicación…</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center space-y-4">
        <p className="text-red-600 font-semibold">{errorMsg}</p>
        <Link href="/" className="text-blue-600 text-sm underline">Volver al inicio</Link>
      </div>
    </div>
  );
}

export default function ConfirmEmailPage() {
  return (
    <Suspense>
      <ConfirmEmailContent />
    </Suspense>
  );
}
