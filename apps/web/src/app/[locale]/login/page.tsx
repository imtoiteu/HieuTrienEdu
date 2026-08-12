'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState, type FormEvent } from 'react';

import { Alert, Button, Card, Field, Input, Logo } from '@hietedu/ui';

import { ApiError } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { useI18n } from '@/lib/i18n';

const DEMO_ACCOUNTS = [
  { role: 'Student', email: 'student@hietrieneducation.vn' },
  { role: 'Parent', email: 'parent@hietrieneducation.vn' },
  { role: 'Teacher', email: 'hieu@hietrieneducation.vn' },
  { role: 'Admin', email: 'admin@hietrieneducation.vn' },
];
const DEMO_PASSWORD = 'HietEdu2026!';

export default function LoginPage() {
  const { t, locale } = useI18n();
  const { login } = useAuth();
  const router = useRouter();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const destinationFor = (role: string) => {
    if (role === 'teacher') return `/${locale}/teacher`;
    if (role === 'admin') return `/${locale}/admin`;
    if (role === 'parent') return `/${locale}/parent`;
    return `/${locale}/dashboard`;
  };

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const user = await login(email.trim(), password);
      router.push(destinationFor(user.role));
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(
          caught.isOffline
            ? t('error.offline')
            : caught.status === 401
              ? t('auth.error.invalid')
              : caught.message,
        );
      } else {
        setError(t('auth.error.generic'));
      }
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-lavender px-5 py-12">
      <div className="w-full max-w-md">
        <Link href={`/${locale}`} className="mb-8 flex justify-center">
          <Logo />
        </Link>

        <Card className="border-ink-900 shadow-pop">
          <h1 className="font-display text-3xl">{t('auth.login.title')}</h1>
          <p className="mt-2 text-ink-600">{t('auth.login.subtitle')}</p>

          <form onSubmit={handleSubmit} className="mt-7 space-y-5" noValidate>
            {error && <Alert tone="error">{error}</Alert>}

            <Field label={t('auth.email')} htmlFor="email" required>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={error ? true : undefined}
              />
            </Field>

            <Field label={t('auth.password')} htmlFor="password" required>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                aria-invalid={error ? true : undefined}
              />
            </Field>

            <Button type="submit" fullWidth size="lg" loading={submitting}>
              {t('auth.login.submit')}
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-ink-600">
            {t('auth.login.noAccount')}{' '}
            <Link href={`/${locale}/register`} className="font-bold text-brand-700 hover:underline">
              {t('common.register')}
            </Link>
          </p>
        </Card>

        {/* This is a demo build, so the demo credentials are shown rather than hidden — the
            alternative is a reviewer who cannot get in. */}
        <Card className="mt-5 bg-white/70">
          <p className="text-sm font-bold text-ink-800">{t('auth.demoAccounts')}</p>
          <p className="mt-1 text-xs text-ink-500">{t('auth.demoHint')}</p>
          <ul className="mt-3 space-y-1.5">
            {DEMO_ACCOUNTS.map((account) => (
              <li key={account.email} className="flex items-center justify-between gap-3 text-xs">
                <span className="font-semibold text-ink-700">{account.role}</span>
                <button
                  type="button"
                  onClick={() => {
                    setEmail(account.email);
                    setPassword(DEMO_PASSWORD);
                  }}
                  className="rounded-lg bg-ink-100 px-2 py-1 font-mono text-ink-700 transition-colors hover:bg-brand-100 hover:text-brand-800"
                >
                  {account.email}
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 font-mono text-xs text-ink-500">password: {DEMO_PASSWORD}</p>
        </Card>
      </div>
    </main>
  );
}
