'use client';

import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { useI18n } from '@/contexts/I18nContext';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Stethoscope, Loader2, MailCheck, ShieldCheck } from 'lucide-react';
import { PrivacyModal } from '@/components/PrivacyModal';

type Mode = 'login' | 'register';

export function AuthPage() {
  const { login, register, pendingEmail, clearPending } = useAuth();
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>('login');

  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPrivacy, setShowPrivacy] = useState(false);

  const handleSubmit = async (e: { preventDefault(): void }) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    const result =
      mode === 'login'
        ? await login(email, password)
        : await register({ first_name: firstName, last_name: lastName, username, email, password });
    if (result.error) setError(result.error);
    setLoading(false);
  };

  if (pendingEmail) {
    return (
      <div className="min-h-screen bg-linear-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
        <Card className="w-full max-w-md shadow-xl border-0 text-center">
          <CardContent className="pt-10 pb-10 px-8 flex flex-col items-center gap-4">
            <div className="h-16 w-16 rounded-2xl bg-blue-100 flex items-center justify-center">
              <MailCheck className="h-8 w-8 text-blue-600" />
            </div>
            <h2 className="text-xl font-bold text-gray-900">{t('auth.check_email_title')}</h2>
            <p className="text-sm text-gray-500 max-w-xs">
              {t('auth.check_email_body', { email: pendingEmail })}
            </p>
            <p className="text-xs text-gray-400">
              {t('auth.check_spam')}{' '}
              <button onClick={() => { clearPending(); setMode('login'); }} className="text-blue-600 hover:underline">
                {t('auth.back_to_login')}
              </button>.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-linear-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      {showPrivacy && <PrivacyModal onClose={() => setShowPrivacy(false)} />}

      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8 gap-3">
          <div className="h-14 w-14 rounded-2xl bg-blue-600 flex items-center justify-center shadow-lg">
            <Stethoscope className="h-8 w-8 text-white" />
          </div>
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">{t('app.title')}</h1>
            <p className="text-sm text-gray-500 mt-1">{t('app.subtitle')}</p>
          </div>
        </div>

        {/* Tab switcher */}
        <div className="flex border-b border-gray-200 mb-4 bg-white rounded-t-xl overflow-hidden">
          {(['login', 'register'] as Mode[]).map((m) => (
            <button
              key={m}
              onClick={() => { setMode(m); setError(''); }}
              className={`flex-1 py-3 text-sm font-medium transition-all border-b-2 -mb-px ${
                mode === m
                  ? 'border-blue-600 text-blue-600 bg-white'
                  : 'border-transparent text-gray-500 hover:text-gray-700 bg-gray-50'
              }`}
            >
              {t(m === 'login' ? 'auth.login' : 'auth.register')}
            </button>
          ))}
        </div>

        <Card className="shadow-xl border-0">
          <CardHeader className="pb-4">
            <CardTitle className="text-lg">
              {t(mode === 'login' ? 'auth.welcome_back' : 'auth.create_account')}
            </CardTitle>
            <CardDescription>
              {t(mode === 'login' ? 'auth.enter_credentials' : 'auth.complete_form')}
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'register' && (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-gray-700">{t('auth.first_name')}</label>
                      <Input type="text" placeholder="Juan" value={firstName} onChange={(e) => setFirstName(e.target.value)} required disabled={loading} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-gray-700">{t('auth.last_name')}</label>
                      <Input type="text" placeholder="García López" value={lastName} onChange={(e) => setLastName(e.target.value)} required disabled={loading} />
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-gray-700">{t('auth.username')}</label>
                    <Input type="text" placeholder="dr_garcia" value={username} onChange={(e) => setUsername(e.target.value)} required disabled={loading} />
                  </div>
                </>
              )}

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">{t('auth.email')}</label>
                <Input type="email" placeholder="doctor@hospital.com" value={email} onChange={(e) => setEmail(e.target.value)} required disabled={loading} />
              </div>

              <div className="space-y-1.5">
                <label className="text-sm font-medium text-gray-700">{t('auth.password')}</label>
                <Input
                  type="password"
                  placeholder={mode === 'register' ? t('auth.password_placeholder_register') : '••••••••'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  disabled={loading}
                />
              </div>

              {error && (
                <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-lg px-3 py-2">
                  {error}
                </p>
              )}

              {mode === 'register' && (
                <p className="text-xs text-gray-500 leading-relaxed">
                  {t('privacy.register_notice')}{' '}
                  <button
                    type="button"
                    onClick={() => setShowPrivacy(true)}
                    className="text-blue-600 hover:underline inline-flex items-center gap-1"
                  >
                    <ShieldCheck className="h-3 w-3" />
                    {t('privacy.learn_more')}
                  </button>
                </p>
              )}

              <Button type="submit" className="w-full bg-blue-600 hover:bg-blue-700" disabled={loading}>
                {loading && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
                {t(mode === 'login' ? 'auth.submit_login' : 'auth.submit_register')}
              </Button>
            </form>

            <p className="text-center text-sm text-gray-500 mt-4">
              {t(mode === 'login' ? 'auth.no_account' : 'auth.have_account')}{' '}
              <button
                onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}
                className="text-blue-600 hover:underline font-medium"
              >
                {t(mode === 'login' ? 'auth.sign_up' : 'auth.sign_in')}
              </button>
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
